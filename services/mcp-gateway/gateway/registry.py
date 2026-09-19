"""Shared plumbing every tool in gateway/tools/ calls: auth -> scope check ->
entitlement check -> rate limit -> the command/query layer -> a gateway_call_log
row. This is DRY at the Python level, not a generic tool handed to the LLM --
CLAUDE.md is explicit that a generic execute_command/execute_sql-style tool is
never allowed. Each command or query still gets its own domain-named
`@server.tool()` in gateway/tools/*.py; this module only removes the boilerplate
repeated across all of them.

Also installs the entitlement filter on `tools/list`: the high-level MCPServer
lists every registered tool with no per-caller filtering, so
`install_entitlement_filter` replaces that one handler (the lowlevel `Server`
explicitly supports replacing a handler after construction) with one that drops
any tool whose module the caller's tenant isn't entitled to -- ROADMAP.md Phase
2's "disabled module's tools are invisible" exit criterion, enforced for real.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import mcp_types as types
from app.api.deps import run_command
from app.commands.base import Command, CommandContext
from app.db.session import tenant_session
from app.modules.gateway.models.call_log import GatewayCallLog
from app.modules.gateway.models.entitlement import Entitlement
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .rate_limit import rate_limiter

# tool name -> sku, populated by register_tool_sku() as each gateway/tools/*.py module
# registers its tools. Read by install_entitlement_filter()'s tools/list handler.
TOOL_SKUS: dict[str, str] = {}


def register_tool_sku(tool_name: str, sku: str) -> None:
    TOOL_SKUS[tool_name] = sku


class GatewayAuthError(Exception):
    """Missing/invalid bearer token, missing scope, missing entitlement, or
    rate-limited -- everything that must reject a call before it reaches the
    command/query layer."""


def resolve_auth(ctx: Context) -> tuple[uuid.UUID, list[str], uuid.UUID | None]:
    request = ctx.request_context.request
    user = getattr(request, "user", None)
    if not isinstance(user, AuthenticatedUser):
        raise GatewayAuthError("not authenticated")
    access_token = user.access_token
    tenant_id = uuid.UUID(access_token.client_id)
    access_token_id = uuid.UUID(access_token.subject) if access_token.subject else None
    return tenant_id, list(access_token.scopes), access_token_id


async def _log_call(
    tenant_id: uuid.UUID,
    access_token_id: uuid.UUID | None,
    tool_name: str,
    mode: str | None,
    success: bool,
    error: str | None,
) -> None:
    async with tenant_session(tenant_id) as session:
        session.add(
            GatewayCallLog(
                tenant_id=tenant_id,
                access_token_id=access_token_id,
                tool_name=tool_name,
                mode=mode,
                success=success,
                error=error,
            )
        )


async def _check_entitlement(tenant_id: uuid.UUID, sku: str) -> bool:
    async with tenant_session(tenant_id) as session:
        return (
            await session.execute(
                select(Entitlement.id).where(
                    Entitlement.tenant_id == tenant_id, Entitlement.sku == sku
                )
            )
        ).scalar_one_or_none() is not None


async def call_command_tool(
    ctx: Context,
    command_cls: type[Command[Any, Any]],
    input_: BaseModel,
    *,
    required_scope: str,
    sku: str,
    mode: Literal["propose", "commit"] = "commit",
    confirm_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """`idempotency_key` matters for a two-phase command: `_consume_proposal`
    (services/core/app/commands/base.py) looks a pending proposal up by
    `(tenant_id, command_name, idempotency_key, confirm_token)`, so a commit call
    only finds the proposal its propose call created if both calls carry the same
    idempotency_key -- exactly the REST API's `TwoPhaseRequest.idempotency_key`
    contract (app/api/sales.py's post_confirm_order etc.). A REST client is
    expected to generate and remember its own key; an MCP caller (often an LLM
    mid-conversation, with no memory of an id it wasn't handed back) can't be
    relied on to do that, so on `mode="propose"` with no idempotency_key given,
    one is generated here and echoed back in the result under "idempotency_key" --
    the caller then just has to pass back what propose returned, not invent
    anything of its own.
    """
    tenant_id, scopes, access_token_id = resolve_auth(ctx)

    if required_scope not in scopes:
        await _log_call(tenant_id, access_token_id, command_cls.name, mode, False, "missing scope")
        raise GatewayAuthError(f"token lacks required scope '{required_scope}'")

    if not rate_limiter.check(str(tenant_id)):
        await _log_call(tenant_id, access_token_id, command_cls.name, mode, False, "rate limited")
        raise GatewayAuthError("rate limit exceeded")

    if not await _check_entitlement(tenant_id, sku):
        await _log_call(
            tenant_id, access_token_id, command_cls.name, mode, False, "missing entitlement"
        )
        raise GatewayAuthError(f"tenant not entitled to '{sku}'")

    if mode == "propose" and idempotency_key is None:
        idempotency_key = str(uuid.uuid4())

    cmd_ctx = CommandContext(
        tenant_id=tenant_id, actor=f"mcp:{access_token_id}", client="mcp-gateway"
    )
    try:
        async with tenant_session(tenant_id) as session:
            result = await run_command(
                command_cls,
                cmd_ctx,
                session,
                input_,
                mode=mode,
                confirm_token=confirm_token,
                idempotency_key=idempotency_key,
            )
    except Exception as exc:
        await _log_call(tenant_id, access_token_id, command_cls.name, mode, False, str(exc))
        raise
    await _log_call(tenant_id, access_token_id, command_cls.name, mode, True, None)
    if mode == "propose":
        result = {**result, "idempotency_key": idempotency_key}
    return result


async def call_query_tool(
    ctx: Context,
    tool_name: str,
    query_fn: Callable[[AsyncSession, uuid.UUID], Awaitable[BaseModel]],
    *,
    required_scope: str,
    sku: str,
) -> dict[str, Any]:
    """Like call_command_tool but for read-only queries: no command layer, no
    idempotency/mode, just the same auth chain and its own call-log row (read
    calls are never in audit_log, which only fires on a command commit).

    `query_fn` is a closure over the tool's own filters (e.g.
    `lambda session, tenant_id: list_orders(session, tenant_id, filters)`) -- the
    query functions themselves take `(session, tenant_id, filters)`, not just a
    tenant id, so the caller binds its filters before handing the closure here.
    """
    tenant_id, scopes, access_token_id = resolve_auth(ctx)

    if required_scope not in scopes:
        await _log_call(tenant_id, access_token_id, tool_name, None, False, "missing scope")
        raise GatewayAuthError(f"token lacks required scope '{required_scope}'")

    if not rate_limiter.check(str(tenant_id)):
        await _log_call(tenant_id, access_token_id, tool_name, None, False, "rate limited")
        raise GatewayAuthError("rate limit exceeded")

    if not await _check_entitlement(tenant_id, sku):
        await _log_call(tenant_id, access_token_id, tool_name, None, False, "missing entitlement")
        raise GatewayAuthError(f"tenant not entitled to '{sku}'")

    try:
        async with tenant_session(tenant_id) as session:
            result = await query_fn(session, tenant_id)
    except Exception as exc:
        await _log_call(tenant_id, access_token_id, tool_name, None, False, str(exc))
        raise
    await _log_call(tenant_id, access_token_id, tool_name, None, True, None)
    return result.model_dump(mode="json")


def install_entitlement_filter(server: MCPServer[Any]) -> None:
    async def filtered_list_tools(
        req_ctx: ServerRequestContext[Any] | Any,
        params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        request = getattr(req_ctx, "request", None)
        user = getattr(request, "user", None)
        all_tools = await server.list_tools()
        if not isinstance(user, AuthenticatedUser):
            return types.ListToolsResult(tools=[])
        tenant_id = uuid.UUID(user.access_token.client_id)

        async with tenant_session(tenant_id) as session:
            granted_skus = set(
                (
                    await session.execute(
                        select(Entitlement.sku).where(Entitlement.tenant_id == tenant_id)
                    )
                )
                .scalars()
                .all()
            )

        visible = [tool for tool in all_tools if TOOL_SKUS.get(tool.name) in granted_skus]
        return types.ListToolsResult(tools=visible)

    server._lowlevel_server.add_request_handler(  # noqa: SLF001 -- see module docstring
        "tools/list", types.PaginatedRequestParams, filtered_list_tools
    )
