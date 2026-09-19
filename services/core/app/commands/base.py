"""The command layer: the only write path in the system (CLAUDE.md rule 1,
ARCHITECTURE.md §4). The MCP gateway, the web app, the automation engine and plugins
(via core's public API) all call the same `Command` subclasses -- there is no second
way to write a row, so there is no way to route around a guardrail below.

    Command(input, actor, tenant, idempotency_key, mode: propose|commit)
      -> authorize (role + scope + entitlement)
      -> validate  (schema + domain invariants)
      -> propose:  return Proposal(diff, human summary, confirm_token, expires_at)  # no writes
      -> commit:   one DB transaction -> rows + audit entry + outbox event
      -> Result
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog, CommandProposal, OutboxEvent

PROPOSAL_TTL = timedelta(minutes=10)


class CommandError(Exception):
    """Base class for errors a command wants surfaced to the caller as-is (not a bug)."""


class NotAuthorizedError(CommandError):
    pass


class ValidationFailedError(CommandError):
    pass


class ProposalRequiredError(CommandError):
    """A two-phase command was called with mode="commit" but no/invalid confirm_token."""


class ProposalExpiredOrMismatchedError(CommandError):
    pass


@dataclass(frozen=True, slots=True)
class CommandContext:
    tenant_id: uuid.UUID
    actor: str
    client: str = "system"
    correlation_id: str = ""

    def __post_init__(self) -> None:
        if not self.correlation_id:
            object.__setattr__(self, "correlation_id", str(uuid.uuid4()))


@dataclass(frozen=True, slots=True)
class OutboxEventDraft:
    event_type: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class Proposal:
    confirm_token: str
    summary: str
    diff: dict[str, object]
    expires_at: datetime


def _canonical_hash(input_model: BaseModel) -> str:
    canonical = json.dumps(input_model.model_dump(mode="json"), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class Command[InputT: BaseModel, ResultT: BaseModel](ABC):
    """Subclass per domain command, e.g. `parties.create_customer`.

    Set `name` and, for anything touching money, stock, legal documents or outbound
    messages, `two_phase = True` (GUARDRAILS.md §3).
    """

    name: str
    result_type: type[ResultT]
    two_phase: bool = False

    def __init__(self, ctx: CommandContext, session: AsyncSession) -> None:
        self.ctx = ctx
        self.session = session

    async def authorize(self, input: InputT) -> None:  # noqa: B027
        """Override to check role/scope/entitlement. Default: no extra checks."""

    @abstractmethod
    async def validate(self, input: InputT) -> None:
        """Raise ValidationFailedError for domain invariant violations."""

    @abstractmethod
    async def summarize(self, input: InputT) -> str:
        """Human-readable summary shown on a proposal card."""

    @abstractmethod
    async def apply(self, input: InputT) -> tuple[ResultT, list[OutboxEventDraft]]:
        """Perform the domain writes. Called inside the caller's transaction. Must not
        commit/rollback itself -- `tenant_session` owns the transaction boundary.
        """

    def redact_for_audit(self, result: ResultT) -> dict[str, object]:
        """What gets written to audit_log.result_json. Default: the result as-is.

        Override for a command whose result carries a secret (e.g.
        gateway.create_access_token's raw bearer token) -- CLAUDE.md's "Never: Log
        ... tokens ... at INFO level" applies to the audit log too. A command that
        overrides this makes idempotent retry return the redacted value, not the
        original secret: a retry after the fact is "this was already issued", not
        a way to re-read it.
        """
        return result.model_dump(mode="json")

    async def _find_prior_result(self, idempotency_key: str) -> ResultT | None:
        stmt = select(AuditLog).where(
            AuditLog.tenant_id == self.ctx.tenant_id,
            AuditLog.command_name == self.name,
            AuditLog.idempotency_key == idempotency_key,
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self.result_type.model_validate(row.result_json)

    async def execute(
        self,
        input: InputT,
        *,
        idempotency_key: str,
        mode: Literal["propose", "commit"] = "commit",
        confirm_token: str | None = None,
    ) -> Proposal | ResultT:
        if not self.two_phase and mode == "propose":
            raise ValidationFailedError(f"{self.name} is not a two-phase command")

        prior = await self._find_prior_result(idempotency_key)
        if prior is not None and mode == "commit":
            return prior

        await self.authorize(input)
        await self.validate(input)

        if mode == "propose":
            return await self._propose(input, idempotency_key)

        if self.two_phase:
            await self._consume_proposal(input, idempotency_key, confirm_token)

        result, event_drafts = await self.apply(input)

        self.session.add(
            AuditLog(
                tenant_id=self.ctx.tenant_id,
                actor=self.ctx.actor,
                client=self.ctx.client,
                command_name=self.name,
                idempotency_key=idempotency_key,
                correlation_id=self.ctx.correlation_id,
                input_json=input.model_dump(mode="json"),
                result_json=self.redact_for_audit(result),
            )
        )
        for draft in event_drafts:
            self.session.add(
                OutboxEvent(
                    tenant_id=self.ctx.tenant_id,
                    event_type=draft.event_type,
                    payload_json=draft.payload,
                    correlation_id=self.ctx.correlation_id,
                )
            )
        return result

    async def _propose(self, input: InputT, idempotency_key: str) -> Proposal:
        input_hash = _canonical_hash(input)
        confirm_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + PROPOSAL_TTL
        summary = await self.summarize(input)
        self.session.add(
            CommandProposal(
                tenant_id=self.ctx.tenant_id,
                command_name=self.name,
                actor=self.ctx.actor,
                idempotency_key=idempotency_key,
                input_hash=input_hash,
                input_json=input.model_dump(mode="json"),
                summary=summary,
                confirm_token=confirm_token,
                status="pending",
                expires_at=expires_at,
            )
        )
        return Proposal(
            confirm_token=confirm_token, summary=summary, diff={}, expires_at=expires_at
        )

    async def _consume_proposal(
        self, input: InputT, idempotency_key: str, confirm_token: str | None
    ) -> None:
        if not confirm_token:
            raise ProposalRequiredError(f"{self.name} requires a confirm_token from propose")
        stmt = select(CommandProposal).where(
            CommandProposal.tenant_id == self.ctx.tenant_id,
            CommandProposal.command_name == self.name,
            CommandProposal.idempotency_key == idempotency_key,
            CommandProposal.confirm_token == confirm_token,
        )
        proposal = (await self.session.execute(stmt)).scalar_one_or_none()
        if proposal is None or proposal.status != "pending":
            raise ProposalExpiredOrMismatchedError("No matching pending proposal")
        if proposal.expires_at < datetime.now(UTC):
            raise ProposalExpiredOrMismatchedError("Proposal expired")
        if proposal.input_hash != _canonical_hash(input):
            raise ProposalExpiredOrMismatchedError("Input no longer matches the proposed change")
        proposal.status = "committed"
