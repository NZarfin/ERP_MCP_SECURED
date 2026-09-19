"""purchasing.confirm_po — draft -> confirmed. Two-phase, the commitment point."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.purchasing.models.purchase_order import PurchaseOrder


class ConfirmPoInput(BaseModel):
    model_config = {"extra": "forbid"}

    purchase_order_id: uuid.UUID


class ConfirmPoResult(BaseModel):
    purchase_order_id: uuid.UUID
    status: str


class ConfirmPo(Command[ConfirmPoInput, ConfirmPoResult]):
    name = "purchasing.confirm_po"
    result_type = ConfirmPoResult
    two_phase = True

    async def _load_order(self, purchase_order_id: uuid.UUID) -> PurchaseOrder:
        order = (
            await self.session.execute(
                select(PurchaseOrder).where(
                    PurchaseOrder.id == purchase_order_id,
                    PurchaseOrder.tenant_id == self.ctx.tenant_id,
                )
            )
        ).scalar_one_or_none()
        if order is None:
            raise ValidationFailedError(f"unknown purchase_order_id {purchase_order_id}")
        return order

    async def validate(self, input: ConfirmPoInput) -> None:
        order = await self._load_order(input.purchase_order_id)
        if order.status != "draft":
            raise ValidationFailedError(f"PO is '{order.status}', expected 'draft'")

    async def summarize(self, input: ConfirmPoInput) -> str:
        return f"Confirm PO {input.purchase_order_id}"

    async def apply(self, input: ConfirmPoInput) -> tuple[ConfirmPoResult, list[OutboxEventDraft]]:
        order = await self._load_order(input.purchase_order_id)
        order.status = "confirmed"
        await self.session.flush()

        result = ConfirmPoResult(purchase_order_id=order.id, status=order.status)
        event = OutboxEventDraft(
            event_type="purchasing.po_confirmed.v1", payload={"purchase_order_id": str(order.id)}
        )
        return result, [event]
