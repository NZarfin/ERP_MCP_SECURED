"""REST endpoints behind the future /purchases page. Mirrors app/api/sales.py."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TwoPhaseRequest, get_command_context, get_tenant_db, run_command
from app.commands.base import CommandContext
from app.modules.purchasing.commands.cancel_po import CancelPo, CancelPoInput
from app.modules.purchasing.commands.confirm_po import ConfirmPo, ConfirmPoInput
from app.modules.purchasing.commands.create_po import CreatePo, CreatePoInput
from app.modules.purchasing.commands.receive_po import ReceivePo, ReceivePoInput
from app.modules.purchasing.queries.list_pos import ListPosFilters, ListPosResult, list_pos

router = APIRouter(prefix="/api/purchasing", tags=["purchasing"])


@router.get("/pos", response_model=ListPosResult)
async def get_pos(
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
    status: list[str] | None = Query(default=None),
    supplier_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    search: str | None = None,
    sort: str = "-order_date",
    limit: int = 50,
    offset: int = 0,
) -> ListPosResult:
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
    return await list_pos(session, ctx.tenant_id, filters)


@router.post("/pos")
async def post_po(
    body: CreatePoInput,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(CreatePo, ctx, session, body)


@router.post("/pos/{po_id}/confirm")
async def post_confirm_po(
    po_id: uuid.UUID,
    body: TwoPhaseRequest,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(
        ConfirmPo,
        ctx,
        session,
        ConfirmPoInput(purchase_order_id=po_id),
        mode=body.mode,
        confirm_token=body.confirm_token,
        idempotency_key=body.idempotency_key,
    )


@router.post("/pos/{po_id}/receive")
async def post_receive_po(
    po_id: uuid.UUID,
    body: TwoPhaseRequest,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(
        ReceivePo,
        ctx,
        session,
        ReceivePoInput(purchase_order_id=po_id),
        mode=body.mode,
        confirm_token=body.confirm_token,
        idempotency_key=body.idempotency_key,
    )


@router.post("/pos/{po_id}/cancel")
async def post_cancel_po(
    po_id: uuid.UUID,
    body: TwoPhaseRequest,
    session: AsyncSession = Depends(get_tenant_db),
    ctx: CommandContext = Depends(get_command_context),
) -> dict[str, Any]:
    return await run_command(
        CancelPo,
        ctx,
        session,
        CancelPoInput(purchase_order_id=po_id),
        mode=body.mode,
        confirm_token=body.confirm_token,
        idempotency_key=body.idempotency_key,
    )
