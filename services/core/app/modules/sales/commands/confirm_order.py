"""sales.confirm_order — draft -> confirmed. This is the commitment point, so it's
two-phase (GUARDRAILS.md §3), even though it doesn't move money or stock itself yet.
"""

import uuid

from pydantic import BaseModel
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.sales.models.sales_order import SalesOrder


class ConfirmOrderInput(BaseModel):
    model_config = {"extra": "forbid"}

    sales_order_id: uuid.UUID


class ConfirmOrderResult(BaseModel):
    sales_order_id: uuid.UUID
    status: str


class ConfirmOrder(Command[ConfirmOrderInput, ConfirmOrderResult]):
    name = "sales.confirm_order"
    result_type = ConfirmOrderResult
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

    async def validate(self, input: ConfirmOrderInput) -> None:
        order = await self._load_order(input.sales_order_id)
        if order.status != "draft":
            raise ValidationFailedError(f"order is '{order.status}', expected 'draft'")

    async def summarize(self, input: ConfirmOrderInput) -> str:
        return f"Confirm sales order {input.sales_order_id}"

    async def apply(
        self, input: ConfirmOrderInput
    ) -> tuple[ConfirmOrderResult, list[OutboxEventDraft]]:
        order = await self._load_order(input.sales_order_id)
        order.status = "confirmed"
        await self.session.flush()

        result = ConfirmOrderResult(sales_order_id=order.id, status=order.status)
        event = OutboxEventDraft(
            event_type="sales.order_confirmed.v1", payload={"sales_order_id": str(order.id)}
        )
        return result, [event]
