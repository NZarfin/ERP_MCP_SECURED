"""inventory.adjust_stock — manual stock corrections (e.g. spoilage/wastage write-offs
for perishable produce). Two-phase: GUARDRAILS.md §3 flags anything touching stock.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.inventory.service import append_stock_move


class AdjustStockInput(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: uuid.UUID
    location_id: uuid.UUID
    quantity_delta: Decimal  # negative for a write-off, positive for a found-stock correction
    reason_note: str = Field(min_length=1, max_length=255)
    lot_code: str | None = None
    best_before_date: date | None = None


class AdjustStockResult(BaseModel):
    stock_move_id: uuid.UUID
    quantity_delta: Decimal


class AdjustStock(Command[AdjustStockInput, AdjustStockResult]):
    name = "inventory.adjust_stock"
    result_type = AdjustStockResult
    two_phase = True

    async def validate(self, input: AdjustStockInput) -> None:
        if input.quantity_delta == 0:
            raise ValidationFailedError("quantity_delta must not be zero")

    async def summarize(self, input: AdjustStockInput) -> str:
        direction = "write off" if input.quantity_delta < 0 else "add"
        return f"Stock adjustment: {direction} {abs(input.quantity_delta)} ({input.reason_note})"

    async def apply(
        self, input: AdjustStockInput
    ) -> tuple[AdjustStockResult, list[OutboxEventDraft]]:
        move = append_stock_move(
            tenant_id=self.ctx.tenant_id,
            product_id=input.product_id,
            location_id=input.location_id,
            quantity_delta=input.quantity_delta,
            reason="adjustment",
            lot_code=input.lot_code,
            best_before_date=input.best_before_date,
        )
        self.session.add(move)
        await self.session.flush()

        result = AdjustStockResult(stock_move_id=move.id, quantity_delta=input.quantity_delta)
        event = OutboxEventDraft(
            event_type="inventory.stock_adjusted.v1",
            payload={
                "product_id": str(input.product_id),
                "quantity_delta": str(input.quantity_delta),
                "reason_note": input.reason_note,
            },
        )
        return result, [event]
