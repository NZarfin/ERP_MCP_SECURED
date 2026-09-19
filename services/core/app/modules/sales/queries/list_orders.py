"""sales.list_orders — the read path behind the /sales page's filter bar. Read-only:
no command layer involvement (queries never write), but the same tenant-scoped
session as everything else, so RLS is the only isolation mechanism either path relies
on.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import from_minor_units
from app.modules.parties.models.customer import Customer
from app.modules.sales.models.sales_order import SalesOrder, SalesOrderLine

SortField = Literal["order_date", "-order_date", "total_amount", "-total_amount"]


class ListOrdersFilters(BaseModel):
    model_config = {"extra": "forbid"}

    status: list[str] | None = None
    customer_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    search: str | None = None
    sort: SortField = "-order_date"
    limit: int = 50
    offset: int = 0


class SalesOrderSummary(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    status: str
    order_date: date
    currency: str
    total_amount: Decimal
    line_count: int
    created_at: datetime


class ListOrdersResult(BaseModel):
    items: list[SalesOrderSummary]
    total: int


def _apply_filters(stmt: Select[Any], filters: ListOrdersFilters) -> Select[Any]:
    if filters.status:
        stmt = stmt.where(SalesOrder.status.in_(filters.status))
    if filters.customer_id:
        stmt = stmt.where(SalesOrder.customer_id == filters.customer_id)
    if filters.date_from:
        stmt = stmt.where(SalesOrder.order_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(SalesOrder.order_date <= filters.date_to)
    if filters.amount_min is not None:
        stmt = stmt.where(SalesOrder.total_amount >= int(filters.amount_min * 100))
    if filters.amount_max is not None:
        stmt = stmt.where(SalesOrder.total_amount <= int(filters.amount_max * 100))
    if filters.search:
        pattern = f"%{filters.search}%"
        stmt = stmt.where(Customer.name.ilike(pattern))
    return stmt


async def list_orders(
    session: AsyncSession, tenant_id: uuid.UUID, filters: ListOrdersFilters
) -> ListOrdersResult:
    line_count = (
        select(func.count(SalesOrderLine.id))
        .where(SalesOrderLine.sales_order_id == SalesOrder.id)
        .correlate(SalesOrder)
        .scalar_subquery()
    )
    base = (
        select(SalesOrder, Customer.name, line_count.label("line_count"))
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .where(SalesOrder.tenant_id == tenant_id)
    )
    base = _apply_filters(base, filters)

    count_stmt = select(func.count()).select_from(base.with_only_columns(SalesOrder.id).subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    sort_column: ColumnElement[Any]
    if filters.sort == "order_date":
        sort_column = SalesOrder.order_date.asc()
    elif filters.sort == "-order_date":
        sort_column = SalesOrder.order_date.desc()
    elif filters.sort == "total_amount":
        sort_column = SalesOrder.total_amount.asc()
    else:
        sort_column = SalesOrder.total_amount.desc()
    page_stmt = base.order_by(sort_column).limit(filters.limit).offset(filters.offset)

    rows = (await session.execute(page_stmt)).all()
    items = [
        SalesOrderSummary(
            id=order.id,
            customer_id=order.customer_id,
            customer_name=customer_name,
            status=order.status,
            order_date=order.order_date,
            currency=order.currency,
            total_amount=from_minor_units(order.total_amount),
            line_count=line_count,
            created_at=order.created_at,
        )
        for order, customer_name, line_count in rows
    ]
    return ListOrdersResult(items=items, total=total)
