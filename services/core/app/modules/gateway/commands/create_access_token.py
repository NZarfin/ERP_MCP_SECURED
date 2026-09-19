"""gateway.create_access_token — issues a bearer token for an MCP client (Claude
Desktop, claude.ai, or any MCP-compatible AI client) to authenticate as this
tenant. Single-phase: issuing credentials isn't money/stock/document-affecting
per GUARDRAILS.md §3's list, though it is security-sensitive -- the raw token is
returned exactly once here and never stored; only its sha256 hash is.
"""

import hashlib
import secrets
import uuid

from pydantic import BaseModel, Field

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.gateway.models.access_token import AccessToken

VALID_SCOPES = (
    "parties:write",
    "catalog:write",
    "sales:read",
    "sales:write",
    "purchasing:read",
    "purchasing:write",
)


class CreateAccessTokenInput(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(min_length=1)


class CreateAccessTokenResult(BaseModel):
    access_token_id: uuid.UUID
    name: str
    token: str  # the raw bearer token -- shown once, never retrievable again
    scopes: list[str]


class CreateAccessToken(Command[CreateAccessTokenInput, CreateAccessTokenResult]):
    name = "gateway.create_access_token"
    result_type = CreateAccessTokenResult

    async def validate(self, input: CreateAccessTokenInput) -> None:
        unknown = set(input.scopes) - set(VALID_SCOPES)
        if unknown:
            raise ValidationFailedError(f"unknown scope(s): {sorted(unknown)}")

    async def summarize(self, input: CreateAccessTokenInput) -> str:
        return f"Create access token '{input.name}' with scopes {input.scopes}"

    def redact_for_audit(self, result: CreateAccessTokenResult) -> dict[str, object]:
        redacted = result.model_dump(mode="json")
        redacted["token"] = "***redacted***"
        return redacted

    async def apply(
        self, input: CreateAccessTokenInput
    ) -> tuple[CreateAccessTokenResult, list[OutboxEventDraft]]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        token = AccessToken(
            tenant_id=self.ctx.tenant_id,
            name=input.name,
            token_hash=token_hash,
            scopes=input.scopes,
        )
        self.session.add(token)
        await self.session.flush()

        result = CreateAccessTokenResult(
            access_token_id=token.id, name=token.name, token=raw_token, scopes=input.scopes
        )
        event = OutboxEventDraft(
            event_type="gateway.access_token_created.v1",
            payload={"access_token_id": str(token.id), "name": token.name},
        )
        return result, [event]
