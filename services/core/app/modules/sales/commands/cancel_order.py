"""sales.cancel_order — draft/confirmed -> cancelled. Two-phase: cancelling a
confirmed order reverses a commitment (GUARDRAILS.md §3); a delivered order is a fact,
not something a cancel undoes (that's a return/credit flow, out of scope here).
"""

import uuid

from pydantic import BaseModel
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.sales.models.sales_order import SalesOrder


class CancelOrderInput(BaseModel):
    model_config = {"extra": "forbid"}

    sales_order_id: uuid.UUID


class CancelOrderResult(BaseModel):
    sales_order_id: uuid.UUID
    status: str


class CancelOrder(Command[CancelOrderInput, CancelOrderResult]):
    name = "sales.cancel_order"
    result_type = CancelOrderResult
    two_phase = True

    async def _load_order(self, sales_order_id: uuid.UUID) -> SalesOrder:
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

    async def validate(self, input: CancelOrderInput) -> None:
        order = await self._load_order(input.sales_order_id)
        if order.status not in ("draft", "confirmed"):
            raise ValidationFailedError(
                f"order is '{order.status}', can only cancel 'draft' or 'confirmed'"
            )

    async def summarize(self, input: CancelOrderInput) -> str:
        return f"Cancel sales order {input.sales_order_id}"

    async def apply(
        self, input: CancelOrderInput
    ) -> tuple[CancelOrderResult, list[OutboxEventDraft]]:
        order = await self._load_order(input.sales_order_id)
        order.status = "cancelled"
        await self.session.flush()

        result = CancelOrderResult(sales_order_id=order.id, status=order.status)
        event = OutboxEventDraft(
            event_type="sales.order_cancelled.v1", payload={"sales_order_id": str(order.id)}
        )
        return result, [event]
