"""Structural MCP gateway evals -- the checks from docs/GUARDRAILS.md §8 that
don't need an LLM: right tools visible for the caller's entitlements, no commit
without a matching confirm_token, cross-tenant isolation, rate limiting. This is
a deliberate scope cut from full "MCP tool-selection evals" (driving a real LLM
and checking it picks the right tool from a prompt) -- that needs an LLM API key
in CI, which this repo does not add without asking (see the Phase 2 plan). What's
here proves the gateway's own contract holds against a real MCP client and a
real database; a future pass adds the LLM-driven layer on top of it.

Each test gets its own fresh tenant (same reasoning as
services/core/tests/conftest.py): no shared seed state, nothing to clean up, and
RLS makes a stray row from a failed test invisible to every other tenant.
"""

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack
from typing import Any

import pytest
import pytest_asyncio
from app.commands.base import CommandContext
from app.db.session import tenant_session
from app.modules.gateway.commands.create_access_token import (
    VALID_SCOPES,
    CreateAccessToken,
    CreateAccessTokenInput,
    CreateAccessTokenResult,
)
from app.modules.gateway.commands.grant_entitlement import GrantEntitlement, GrantEntitlementInput
from mcp import types as client_types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

ALL_SKUS = ("core.parties", "core.catalog", "core.sales", "core.purchasing")

# module-scoped: see services/mcp-gateway/tests/test_auth.py's comment on the same
# marker -- app.db.session.engine is one pool shared across every test in this
# file, and pytest-asyncio's default per-function loop makes a pooled connection
# unusable across test boundaries.
pytestmark = pytest.mark.asyncio(loop_scope="module")


async def _provision_tenant(tenant_id: uuid.UUID, *, skus: tuple[str, ...] = ALL_SKUS) -> str:
    """Grants the given entitlements and returns a raw bearer token with every
    scope -- the tests below narrow what they exercise via which tools they call,
    not via the token's own scopes."""
    ctx = CommandContext(tenant_id=tenant_id, actor="eval", client="evals")
    async with tenant_session(tenant_id) as session:
        for sku in skus:
            await GrantEntitlement(ctx, session).execute(
                GrantEntitlementInput(sku=sku), idempotency_key=str(uuid.uuid4())
            )
        result = await CreateAccessToken(ctx, session).execute(
            CreateAccessTokenInput(name="eval-token", scopes=list(VALID_SCOPES)),
            idempotency_key=str(uuid.uuid4()),
        )
        assert isinstance(result, CreateAccessTokenResult)
        return result.token


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest_asyncio.fixture(loop_scope="module")
async def token(tenant_id: uuid.UUID) -> str:
    return await _provision_tenant(tenant_id)


class GatewayClient:
    """One MCP session for the client's whole lifetime, reused across every
    call -- matching how a real client (Claude Desktop, an eval run) actually
    talks to a tenant: one conversation, many tool calls, not a fresh
    initialize/terminate handshake per call. `async with GatewayClient(...)`
    opens the session; every `list_tools`/`call_tool` reuses it.
    """

    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def __aenter__(self) -> GatewayClient:
        http_client = await self._stack.enter_async_context(
            create_mcp_http_client(headers={"Authorization": f"Bearer {self._token}"})
        )
        read, write = await self._stack.enter_async_context(
            streamable_http_client(self._url, http_client=http_client)
        )
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._stack.aclose()

    async def list_tools(self) -> list[str]:
        assert self._session is not None
        result = await self._session.list_tools()
        return sorted(t.name for t in result.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> client_types.CallToolResult:
        assert self._session is not None
        return await self._session.call_tool(name, arguments)


EXPECTED_TOOLS = {
    "parties.create_customer",
    "parties.create_supplier",
    "catalog.create_product",
    "sales.create_order",
    "sales.confirm_order",
    "sales.deliver_order",
    "sales.cancel_order",
    "sales.list_orders",
    "purchasing.create_po",
    "purchasing.confirm_po",
    "purchasing.receive_po",
    "purchasing.cancel_po",
    "purchasing.list_pos",
}


async def test_tools_list_shows_only_entitled_tools(gateway_url: str, token: str) -> None:
    async with GatewayClient(gateway_url, token) as client:
        tools = await client.list_tools()
        assert set(tools) == EXPECTED_TOOLS


async def test_tools_list_hides_modules_without_entitlement(gateway_url: str) -> None:
    tenant = uuid.uuid4()
    token = await _provision_tenant(tenant, skus=("core.parties", "core.catalog"))

    async with GatewayClient(gateway_url, token) as client:
        tools = await client.list_tools()

        assert set(tools) == {
            "parties.create_customer",
            "parties.create_supplier",
            "catalog.create_product",
        }
        assert not any(name.startswith(("sales.", "purchasing.")) for name in tools)

        rejected = await client.call_tool("sales.list_orders", {})
        assert rejected.is_error


async def test_propose_commit_round_trip(gateway_url: str, token: str) -> None:
    async with GatewayClient(gateway_url, token) as client:
        customer = await client.call_tool("parties.create_customer", {"name": "Eval Customer"})
        assert not customer.is_error
        customer_id = customer.structured_content["customer_id"]

        product = await client.call_tool(
            "catalog.create_product",
            {
                "sku": f"EVAL-{uuid.uuid4().hex[:8]}",
                "name": "Eval Product",
                "unit": "kg",
                "base_price": "2.00",
            },
        )
        assert not product.is_error
        product_id = product.structured_content["product_id"]

        order = await client.call_tool(
            "sales.create_order",
            {
                "customer_id": customer_id,
                "order_date": "2026-01-01",
                "lines": [{"product_id": product_id, "quantity": "5"}],
            },
        )
        assert not order.is_error
        order_id = order.structured_content["sales_order_id"]
        assert order.structured_content["status"] == "draft"

        propose = await client.call_tool(
            "sales.confirm_order", {"sales_order_id": order_id, "mode": "propose"}
        )
        assert not propose.is_error
        confirm_token = propose.structured_content["confirm_token"]
        idempotency_key = propose.structured_content["idempotency_key"]
        assert confirm_token and idempotency_key

        commit = await client.call_tool(
            "sales.confirm_order",
            {
                "sales_order_id": order_id,
                "mode": "commit",
                "confirm_token": confirm_token,
                "idempotency_key": idempotency_key,
            },
        )
        assert not commit.is_error
        assert commit.structured_content["status"] == "confirmed"


async def test_commit_without_confirm_token_is_rejected(gateway_url: str, token: str) -> None:
    async with GatewayClient(gateway_url, token) as client:
        customer = await client.call_tool("parties.create_customer", {"name": "Eval Customer 2"})
        product = await client.call_tool(
            "catalog.create_product",
            {
                "sku": f"EVAL-{uuid.uuid4().hex[:8]}",
                "name": "Eval Product 2",
                "unit": "kg",
                "base_price": "2.00",
            },
        )
        order = await client.call_tool(
            "sales.create_order",
            {
                "customer_id": customer.structured_content["customer_id"],
                "order_date": "2026-01-01",
                "lines": [
                    {"product_id": product.structured_content["product_id"], "quantity": "1"}
                ],
            },
        )
        order_id = order.structured_content["sales_order_id"]

        rejected = await client.call_tool(
            "sales.confirm_order", {"sales_order_id": order_id, "mode": "commit"}
        )
        assert rejected.is_error


async def test_cross_tenant_isolation(gateway_url: str) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    token_a = await _provision_tenant(tenant_a)
    token_b = await _provision_tenant(tenant_b)

    async with GatewayClient(gateway_url, token_a) as client_a:
        customer = await client_a.call_tool("parties.create_customer", {"name": "Tenant A Only"})
        assert not customer.is_error
        customer_id = customer.structured_content["customer_id"]

    async with GatewayClient(gateway_url, token_b) as client_b:
        orders_from_b = await client_b.call_tool("sales.list_orders", {"search": "Tenant A Only"})
        assert not orders_from_b.is_error
        assert orders_from_b.structured_content["total"] == 0

        cross_tenant_attempt = await client_b.call_tool(
            "sales.create_order",
            {
                "customer_id": customer_id,
                "order_date": "2026-01-01",
                "lines": [{"product_id": str(uuid.uuid4()), "quantity": "1"}],
            },
        )
        assert cross_tenant_attempt.is_error


async def test_rate_limit_trips_within_a_burst(gateway_url: str, token: str) -> None:
    async with GatewayClient(gateway_url, token) as client:
        results = [await client.call_tool("sales.list_orders", {"limit": 1}) for _ in range(35)]
        assert any(r.is_error for r in results)
