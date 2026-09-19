"""Shared FastAPI dependencies for app/api/* routers.

`get_tenant_db` is the REST API's half of the tenancy seam described in
app/db/session.py -- the only place an HTTP request resolves a tenant id. Same
placeholder `X-Tenant-Id` header as before; real OAuth 2.1 scoped tokens are Phase 2
(docs/ROADMAP.md), out of scope here.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.base import Command, CommandContext
from app.db.session import tenant_session


async def get_tenant_db(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
) -> AsyncIterator[AsyncSession]:
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-Id must be a UUID") from exc
    async with tenant_session(tenant_id) as session:
        yield session


async def get_command_context(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_actor: str = Header(default="api-client", alias="X-Actor"),
) -> CommandContext:
    return CommandContext(tenant_id=uuid.UUID(x_tenant_id), actor=x_actor, client="rest-api")


class TwoPhaseRequest(BaseModel):
    """Body for any endpoint backed by a two-phase command (GUARDRAILS.md §3)."""

    model_config = {"extra": "forbid"}

    mode: Literal["propose", "commit"] = "commit"
    confirm_token: str | None = None
    idempotency_key: str | None = None


async def run_command(
    command_cls: type[Command[Any, Any]],
    ctx: CommandContext,
    session: AsyncSession,
    input_: BaseModel,
    *,
    mode: Literal["propose", "commit"] = "commit",
    confirm_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Runs any command (single- or two-phase) and returns a JSON-ready dict --
    either the Proposal (mode="propose") or the command's own Result (mode="commit").
    """
    result = await command_cls(ctx, session).execute(
        input_,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
        mode=mode,
        confirm_token=confirm_token,
    )
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    return {
        "confirm_token": result.confirm_token,
        "summary": result.summary,
        "expires_at": result.expires_at.isoformat(),
    }
