"""purchasing.cancel_po — draft/confirmed -> cancelled. Two-phase, mirrors
sales.cancel_order.
"""

import uuid

from pydantic import BaseModel
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.purchasing.models.purchase_order import PurchaseOrder


class CancelPoInput(BaseModel):
    model_config = {"extra": "forbid"}

    purchase_order_id: uuid.UUID


class CancelPoResult(BaseModel):
    purchase_order_id: uuid.UUID
    status: str


class CancelPo(Command[CancelPoInput, CancelPoResult]):
    name = "purchasing.cancel_po"
    result_type = CancelPoResult
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

    async def validate(self, input: CancelPoInput) -> None:
        order = await self._load_order(input.purchase_order_id)
        if order.status not in ("draft", "confirmed"):
            raise ValidationFailedError(
                f"PO is '{order.status}', can only cancel 'draft' or 'confirmed'"
            )

    async def summarize(self, input: CancelPoInput) -> str:
        return f"Cancel PO {input.purchase_order_id}"

    async def apply(self, input: CancelPoInput) -> tuple[CancelPoResult, list[OutboxEventDraft]]:
        order = await self._load_order(input.purchase_order_id)
        order.status = "cancelled"
        await self.session.flush()

        result = CancelPoResult(purchase_order_id=order.id, status=order.status)
        event = OutboxEventDraft(
            event_type="purchasing.po_cancelled.v1", payload={"purchase_order_id": str(order.id)}
        )
        return result, [event]
