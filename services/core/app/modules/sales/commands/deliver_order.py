"""sales.deliver_order — confirmed -> delivered. Two-phase: writes stock moves
(GUARDRAILS.md §3 "touches stock"). Blocks the whole delivery if any line is short on
stock -- "ship what's on the order or don't ship it" is the simplest correct rule for
an MVP; partial shipments are a real feature to add later, not a default to fall into.
"""

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.inventory.models.location import Location
from app.modules.inventory.service import append_stock_move, get_stock_balance
from app.modules.sales.models.sales_order import SalesOrder, SalesOrderLine


class DeliverOrderInput(BaseModel):
    model_config = {"extra": "forbid"}

    sales_order_id: uuid.UUID
    location_id: uuid.UUID | None = None  # defaults to the tenant's first location
    delivery_date: date | None = None


class DeliverOrderResult(BaseModel):
    sales_order_id: uuid.UUID
    status: str


class DeliverOrder(Command[DeliverOrderInput, DeliverOrderResult]):
    name = "sales.deliver_order"
    result_type = DeliverOrderResult
    two_phase = True

    async def _load_order_with_lines(self, sales_order_id: uuid.UUID) -> SalesOrder:
        order = (
            await self.session.execute(
                select(SalesOrder).where(
                    SalesOrder.id == sales_order_id, SalesOrder.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalar_one_or_none()
        if order is None:
            raise ValidationFailedError(f"unknown sales_order_id {sales_order_id}")
        return order

    async def _resolve_location(self, location_id: uuid.UUID | None) -> uuid.UUID:
        stmt = select(Location.id).where(Location.tenant_id == self.ctx.tenant_id)
        stmt = (
            stmt.where(Location.id == location_id)
            if location_id is not None
            else stmt.order_by(Location.created_at.asc()).limit(1)
        )
        resolved = (await self.session.execute(stmt)).scalar_one_or_none()
        if resolved is None:
            raise ValidationFailedError("no location found for tenant")
        return resolved

    async def validate(self, input: DeliverOrderInput) -> None:
        order = await self._load_order_with_lines(input.sales_order_id)
        if order.status != "confirmed":
            raise ValidationFailedError(f"order is '{order.status}', expected 'confirmed'")

        lines = (
            (
                await self.session.execute(
                    select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
                )
            )
            .scalars()
            .all()
        )
        for line in lines:
            balance = await get_stock_balance(self.session, self.ctx.tenant_id, line.product_id)
            if balance < line.quantity:
                raise ValidationFailedError(
                    f"insufficient stock for product {line.product_id}: "
                    f"have {balance}, need {line.quantity}"
                )

    async def summarize(self, input: DeliverOrderInput) -> str:
        return f"Deliver sales order {input.sales_order_id}"

    async def apply(
        self, input: DeliverOrderInput
    ) -> tuple[DeliverOrderResult, list[OutboxEventDraft]]:
        order = await self._load_order_with_lines(input.sales_order_id)
        location_id = await self._resolve_location(input.location_id)
        lines = (
            (
                await self.session.execute(
                    select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
                )
            )
            .scalars()
            .all()
        )

        for line in lines:
            self.session.add(
                append_stock_move(
                    tenant_id=self.ctx.tenant_id,
                    product_id=line.product_id,
                    location_id=location_id,
                    quantity_delta=-line.quantity,
                    reason="delivery",
                    reference_type="sales_order",
                    reference_id=order.id,
                )
            )

        order.status = "delivered"
        await self.session.flush()

        result = DeliverOrderResult(sales_order_id=order.id, status=order.status)
        event = OutboxEventDraft(
            event_type="sales.order_delivered.v1", payload={"sales_order_id": str(order.id)}
        )
        return result, [event]
