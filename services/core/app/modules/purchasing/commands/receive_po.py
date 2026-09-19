"""purchasing.receive_po — confirmed -> received. Two-phase: writes stock moves in
(GUARDRAILS.md §3). `lot_code`/`best_before_date` apply to the whole receipt (one
supplier delivery = one lot) -- simple and realistic enough for perishable produce
without needing per-line lot matching in the MVP.
"""

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.inventory.models.location import Location
from app.modules.inventory.service import append_stock_move
from app.modules.purchasing.models.purchase_order import PurchaseOrder, PurchaseOrderLine


class ReceivePoInput(BaseModel):
    model_config = {"extra": "forbid"}

    purchase_order_id: uuid.UUID
    location_id: uuid.UUID | None = None  # defaults to the tenant's first location
    lot_code: str | None = None
    best_before_date: date | None = None


class ReceivePoResult(BaseModel):
    purchase_order_id: uuid.UUID
    status: str


class ReceivePo(Command[ReceivePoInput, ReceivePoResult]):
    name = "purchasing.receive_po"
    result_type = ReceivePoResult
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

    async def validate(self, input: ReceivePoInput) -> None:
        order = await self._load_order(input.purchase_order_id)
        if order.status != "confirmed":
            raise ValidationFailedError(f"PO is '{order.status}', expected 'confirmed'")

    async def summarize(self, input: ReceivePoInput) -> str:
        return f"Receive PO {input.purchase_order_id}"

    async def apply(self, input: ReceivePoInput) -> tuple[ReceivePoResult, list[OutboxEventDraft]]:
        order = await self._load_order(input.purchase_order_id)
        location_id = await self._resolve_location(input.location_id)
        lines = (
            (
                await self.session.execute(
                    select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)
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
                    quantity_delta=line.quantity,
                    reason="receipt",
                    reference_type="purchase_order",
                    reference_id=order.id,
                    lot_code=input.lot_code,
                    best_before_date=input.best_before_date,
                )
            )

        order.status = "received"
        await self.session.flush()

        result = ReceivePoResult(purchase_order_id=order.id, status=order.status)
        event = OutboxEventDraft(
            event_type="purchasing.po_received.v1", payload={"purchase_order_id": str(order.id)}
        )
        return result, [event]
