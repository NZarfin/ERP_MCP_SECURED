"""purchasing.* as MCP tools -- mirrors gateway/tools/sales.py exactly, with supplier
in place of customer and receive_po in place of deliver_order. See sales.py's
module docstring for why idempotency_key is echoed back on propose and must be
passed back on commit.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.modules.purchasing.commands.cancel_po import CancelPo, CancelPoInput
from app.modules.purchasing.commands.confirm_po import ConfirmPo, ConfirmPoInput
from app.modules.purchasing.commands.create_po import CreatePo, CreatePoInput, CreatePoLineInput
from app.modules.purchasing.commands.receive_po import ReceivePo, ReceivePoInput
from app.modules.purchasing.queries.list_pos import ListPosFilters, SortField, list_pos
from mcp.server.mcpserver import Context, MCPServer
from mcp_types import ToolAnnotations

from ..registry import call_command_tool, call_query_tool, register_tool_sku

SKU = "core.purchasing"


def register(server: MCPServer[Any]) -> None:
    @server.tool(
        name="purchasing.create_po",
        description="Create a draft purchase order for a supplier.",
        annotations=ToolAnnotations(
            title="Create purchase order",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def create_po(
        ctx: Context,
        supplier_id: UUID,
        order_date: date,
        lines: list[CreatePoLineInput],
        currency: str = "EUR",
        notes: str | None = None,
    ) -> dict[str, Any]:
        input_ = CreatePoInput(
            supplier_id=supplier_id,
            order_date=order_date,
            currency=currency,
            lines=lines,
            notes=notes,
        )
        return await call_command_tool(
            ctx, CreatePo, input_, required_scope="purchasing:write", sku=SKU
        )

    @server.tool(
        name="purchasing.confirm_po",
        description=(
            "Confirm a draft purchase order, committing it. Two-phase: propose "
            "first, then commit with the returned confirm_token and "
            "idempotency_key."
        ),
        annotations=ToolAnnotations(
            title="Confirm purchase order",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def confirm_po(
        ctx: Context,
        purchase_order_id: UUID,
        mode: Literal["propose", "commit"] = "propose",
        confirm_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        input_ = ConfirmPoInput(purchase_order_id=purchase_order_id)
        return await call_command_tool(
            ctx,
            ConfirmPo,
            input_,
            required_scope="purchasing:write",
            sku=SKU,
            mode=mode,
            confirm_token=confirm_token,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="purchasing.receive_po",
        description=(
            "Receive a confirmed purchase order, writing stock moves in. "
            "Two-phase: propose first, then commit with the returned confirm_token "
            "and idempotency_key."
        ),
        annotations=ToolAnnotations(
            title="Receive purchase order",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def receive_po(
        ctx: Context,
        purchase_order_id: UUID,
        location_id: UUID | None = None,
        lot_code: str | None = None,
        best_before_date: date | None = None,
        mode: Literal["propose", "commit"] = "propose",
        confirm_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        input_ = ReceivePoInput(
            purchase_order_id=purchase_order_id,
            location_id=location_id,
            lot_code=lot_code,
            best_before_date=best_before_date,
        )
        return await call_command_tool(
            ctx,
            ReceivePo,
            input_,
            required_scope="purchasing:write",
            sku=SKU,
            mode=mode,
            confirm_token=confirm_token,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="purchasing.cancel_po",
        description=(
            "Cancel a draft or confirmed purchase order. Two-phase: propose "
            "first, then commit with the returned confirm_token and "
            "idempotency_key."
        ),
        annotations=ToolAnnotations(
            title="Cancel purchase order",
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
        ),
    )
    async def cancel_po(
        ctx: Context,
        purchase_order_id: UUID,
        mode: Literal["propose", "commit"] = "propose",
        confirm_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        input_ = CancelPoInput(purchase_order_id=purchase_order_id)
        return await call_command_tool(
            ctx,
            CancelPo,
            input_,
            required_scope="purchasing:write",
            sku=SKU,
            mode=mode,
            confirm_token=confirm_token,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="purchasing.list_pos",
        description="List and filter this tenant's purchase orders.",
        annotations=ToolAnnotations(
            title="List purchase orders", read_only_hint=True, destructive_hint=False
        ),
    )
    async def list_pos_tool(
        ctx: Context,
        status: list[str] | None = None,
        supplier_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        search: str | None = None,
        sort: SortField = "-order_date",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = ListPosFilters(
            status=status,
            supplier_id=supplier_id,
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
            "purchasing.list_pos",
            lambda session, tenant_id: list_pos(session, tenant_id, filters),
            required_scope="purchasing:read",
            sku=SKU,
        )

    register_tool_sku("purchasing.create_po", SKU)
    register_tool_sku("purchasing.confirm_po", SKU)
    register_tool_sku("purchasing.receive_po", SKU)
    register_tool_sku("purchasing.cancel_po", SKU)
    register_tool_sku("purchasing.list_pos", SKU)
