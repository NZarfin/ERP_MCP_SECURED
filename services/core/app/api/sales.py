"""REST endpoints behind the future /sales page: a filterable list plus the order
lifecycle commands. `list_orders` is the one this pass's web UI actually calls; the
write endpoints exist for completeness/parity with the command layer (MCP tools will
reuse these same commands in Phase 2) and for tooling, not for a create/edit form in
this pass's UI.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TwoPhaseRequest, get_command_context, get_tenant_db, run_command
from app.commands.base import CommandContext
from app.modules.sales.commands.cancel_order import CancelOrder, CancelOrderInput
from app.modules.sales.commands.confirm_order import ConfirmOrder, ConfirmOrderInput
from app.modules.sales.commands.create_order import CreateOrder, CreateOrderInput
from app.modules.sales.commands.deliver_order import DeliverOrder, DeliverOrderInput
from app.modules.sales.queries.list_orders import ListOrdersFilters, ListOrdersResult, list_orders

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("/orders", response_model=ListOrdersResult)
async def get_orders(
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
    status: list[str] | None = Query(default=None),
    customer_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    search: str | None = None,
    sort: str = "-order_date",
    limit: int = 50,
    offset: int = 0,
) -> ListOrdersResult:
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
    return await list_orders(session, ctx.tenant_id, filters)


@router.post("/orders")
async def post_order(
    body: CreateOrderInput,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(CreateOrder, ctx, session, body)


@router.post("/orders/{order_id}/confirm")
async def post_confirm_order(
    order_id: uuid.UUID,
    body: TwoPhaseRequest,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(
        ConfirmOrder,
        ctx,
        session,
        ConfirmOrderInput(sales_order_id=order_id),
        mode=body.mode,
        confirm_token=body.confirm_token,
        idempotency_key=body.idempotency_key,
    )


@router.post("/orders/{order_id}/deliver")
async def post_deliver_order(
    order_id: uuid.UUID,
    body: TwoPhaseRequest,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(
        DeliverOrder,
        ctx,
        session,
        DeliverOrderInput(sales_order_id=order_id),
        mode=body.mode,
        confirm_token=body.confirm_token,
        idempotency_key=body.idempotency_key,
    )


@router.post("/orders/{order_id}/cancel")
async def post_cancel_order(
    order_id: uuid.UUID,
    body: TwoPhaseRequest,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(
        CancelOrder,
        ctx,
        session,
        CancelOrderInput(sales_order_id=order_id),
        mode=body.mode,
        confirm_token=body.confirm_token,
        idempotency_key=body.idempotency_key,
    )
