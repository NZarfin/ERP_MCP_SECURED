"""purchasing.list_pos — the read path behind the /purchases page's filter bar.
Mirrors sales.queries.list_orders exactly, with supplier in place of customer.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import from_minor_units
from app.modules.parties.models.supplier import Supplier
from app.modules.purchasing.models.purchase_order import PurchaseOrder, PurchaseOrderLine

SortField = Literal["order_date", "-order_date", "total_amount", "-total_amount"]


class ListPosFilters(BaseModel):
    model_config = {"extra": "forbid"}

    status: list[str] | None = None
    supplier_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    search: str | None = None
    sort: SortField = "-order_date"
    limit: int = 50
    offset: int = 0


class PurchaseOrderSummary(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    status: str
    order_date: date
    currency: str
    total_amount: Decimal
    line_count: int
    created_at: datetime


class ListPosResult(BaseModel):
    items: list[PurchaseOrderSummary]
    total: int


def _apply_filters(stmt: Select[Any], filters: ListPosFilters) -> Select[Any]:
    if filters.status:
        stmt = stmt.where(PurchaseOrder.status.in_(filters.status))
    if filters.supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == filters.supplier_id)
    if filters.date_from:
        stmt = stmt.where(PurchaseOrder.order_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(PurchaseOrder.order_date <= filters.date_to)
    if filters.amount_min is not None:
        stmt = stmt.where(PurchaseOrder.total_amount >= int(filters.amount_min * 100))
    if filters.amount_max is not None:
        stmt = stmt.where(PurchaseOrder.total_amount <= int(filters.amount_max * 100))
    if filters.search:
        pattern = f"%{filters.search}%"
        stmt = stmt.where(Supplier.name.ilike(pattern))
    return stmt


async def list_pos(
    session: AsyncSession, tenant_id: uuid.UUID, filters: ListPosFilters
) -> ListPosResult:
    line_count = (
        select(func.count(PurchaseOrderLine.id))
        .where(PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .correlate(PurchaseOrder)
        .scalar_subquery()
    )
    base = (
        select(PurchaseOrder, Supplier.name, line_count.label("line_count"))
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(PurchaseOrder.tenant_id == tenant_id)
    )
    base = _apply_filters(base, filters)

    count_stmt = select(func.count()).select_from(
        base.with_only_columns(PurchaseOrder.id).subquery()
    )
    total = (await session.execute(count_stmt)).scalar_one()

    sort_column: ColumnElement[Any]
    if filters.sort == "order_date":
        sort_column = PurchaseOrder.order_date.asc()
    elif filters.sort == "-order_date":
        sort_column = PurchaseOrder.order_date.desc()
    elif filters.sort == "total_amount":
        sort_column = PurchaseOrder.total_amount.asc()
    else:
        sort_column = PurchaseOrder.total_amount.desc()
    page_stmt = base.order_by(sort_column).limit(filters.limit).offset(filters.offset)

    rows = (await session.execute(page_stmt)).all()
    items = [
        PurchaseOrderSummary(
            id=order.id,
            supplier_id=order.supplier_id,
            supplier_name=supplier_name,
            status=order.status,
            order_date=order.order_date,
            currency=order.currency,
            total_amount=from_minor_units(order.total_amount),
            line_count=line_count,
            created_at=order.created_at,
        )
        for order, supplier_name, line_count in rows
    ]
    return ListPosResult(items=items, total=total)
