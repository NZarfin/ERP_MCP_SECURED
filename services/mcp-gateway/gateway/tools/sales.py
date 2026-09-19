"""sales.* as MCP tools: create_order (single-phase draft) plus confirm/deliver/
cancel (two-phase, GUARDRAILS.md §3 -- each takes mode/confirm_token/idempotency_key
exactly like the REST API's TwoPhaseRequest body) and list_orders (read-only).

idempotency_key matters here: a propose call and its matching commit call must
carry the *same* idempotency_key (the caller picks it and repeats it), because
that's how the command layer finds the pending proposal a confirm_token belongs
to (see call_command_tool's docstring in ../registry.py). Omitting it on both
calls of a round trip -- letting each get its own random key -- means commit can
never find propose's proposal and always fails with "no matching pending
proposal".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.modules.sales.commands.cancel_order import CancelOrder, CancelOrderInput
from app.modules.sales.commands.confirm_order import ConfirmOrder, ConfirmOrderInput
from app.modules.sales.commands.create_order import (
    CreateOrder,
    CreateOrderInput,
    CreateOrderLineInput,
)
from app.modules.sales.commands.deliver_order import DeliverOrder, DeliverOrderInput
from app.modules.sales.queries.list_orders import ListOrdersFilters, SortField, list_orders
from mcp.server.mcpserver import Context, MCPServer
from mcp_types import ToolAnnotations

from ..registry import call_command_tool, call_query_tool, register_tool_sku

SKU = "core.sales"


def register(server: MCPServer[Any]) -> None:
    @server.tool(
        name="sales.create_order",
        description="Create a draft sales order for a customer.",
        annotations=ToolAnnotations(
            title="Create sales order",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def create_order(
        ctx: Context,
        customer_id: UUID,
        order_date: date,
        lines: list[CreateOrderLineInput],
        currency: str = "EUR",
        notes: str | None = None,
        custom: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        input_ = CreateOrderInput(
            customer_id=customer_id,
            order_date=order_date,
            currency=currency,
            lines=lines,
            notes=notes,
            custom=custom or {},
        )
        return await call_command_tool(
            ctx, CreateOrder, input_, required_scope="sales:write", sku=SKU
        )

    @server.tool(
        name="sales.confirm_order",
        description=(
            "Confirm a draft sales order, committing it. Two-phase: call with "
            "mode='propose' first to get a confirm_token, idempotency_key and "
            "human-readable summary, then call again with mode='commit' and both "
            "of those values."
        ),
        annotations=ToolAnnotations(
            title="Confirm sales order",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def confirm_order(
        ctx: Context,
        sales_order_id: UUID,
        mode: Literal["propose", "commit"] = "propose",
        confirm_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        input_ = ConfirmOrderInput(sales_order_id=sales_order_id)
        return await call_command_tool(
            ctx,
            ConfirmOrder,
            input_,
            required_scope="sales:write",
            sku=SKU,
            mode=mode,
            confirm_token=confirm_token,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="sales.deliver_order",
        description=(
            "Deliver a confirmed sales order, writing stock moves out. Two-phase: "
            "propose first, then commit with the returned confirm_token and "
            "idempotency_key."
        ),
        annotations=ToolAnnotations(
            title="Deliver sales order",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def deliver_order(
        ctx: Context,
        sales_order_id: UUID,
        location_id: UUID | None = None,
        delivery_date: date | None = None,
        mode: Literal["propose", "commit"] = "propose",
        confirm_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        input_ = DeliverOrderInput(
            sales_order_id=sales_order_id, location_id=location_id, delivery_date=delivery_date
        )
        return await call_command_tool(
            ctx,
            DeliverOrder,
            input_,
            required_scope="sales:write",
            sku=SKU,
            mode=mode,
            confirm_token=confirm_token,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="sales.cancel_order",
        description=(
            "Cancel a draft or confirmed sales order. Two-phase: propose first, "
            "then commit with the returned confirm_token and idempotency_key."
        ),
        annotations=ToolAnnotations(
            title="Cancel sales order",
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
        ),
    )
    async def cancel_order(
        ctx: Context,
        sales_order_id: UUID,
        mode: Literal["propose", "commit"] = "propose",
        confirm_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        input_ = CancelOrderInput(sales_order_id=sales_order_id)
        return await call_command_tool(
            ctx,
            CancelOrder,
            input_,
            required_scope="sales:write",
            sku=SKU,
            mode=mode,
            confirm_token=confirm_token,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="sales.list_orders",
        description="List and filter this tenant's sales orders.",
        annotations=ToolAnnotations(
            title="List sales orders", read_only_hint=True, destructive_hint=False
        ),
    )
    async def list_orders_tool(
        ctx: Context,
        status: list[str] | None = None,
        customer_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        search: str | None = None,
        sort: SortField = "-order_date",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = ListOrdersFilters(
            status=status,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return await call_query_tool(
            ctx,
            "sales.list_orders",
            lambda session, tenant_id: list_orders(session, tenant_id, filters),
            required_scope="sales:read",
            sku=SKU,
        )

    register_tool_sku("sales.create_order", SKU)
    register_tool_sku("sales.confirm_order", SKU)
    register_tool_sku("sales.deliver_order", SKU)
    register_tool_sku("sales.cancel_order", SKU)
    register_tool_sku("sales.list_orders", SKU)
