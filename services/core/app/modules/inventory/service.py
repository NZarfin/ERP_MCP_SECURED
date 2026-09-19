"""Internal helper shared by commands that move stock (sales.deliver_order,
purchasing.receive_po, inventory.adjust_stock). Not a Command itself: it writes into
the caller's transaction and the caller's apply() is what gets the single audit log
entry, matching "one command = one audit entry" -- stock moves are domain writes a
command makes, not commands of their own.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models.stock_move import StockMove


def append_stock_move(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    location_id: uuid.UUID,
    quantity_delta: Decimal,
    reason: str,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    lot_code: str | None = None,
    best_before_date: date | None = None,
) -> StockMove:
    return StockMove(
        tenant_id=tenant_id,
        product_id=product_id,
        location_id=location_id,
        quantity_delta=quantity_delta,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        lot_code=lot_code,
        best_before_date=best_before_date,
    )


async def get_stock_balance(
    session: AsyncSession, tenant_id: uuid.UUID, product_id: uuid.UUID
) -> Decimal:
    """Current on-hand quantity across all locations: SUM(quantity_delta). RLS already
    scopes this to `tenant_id`'s rows; the explicit filter documents the invariant.
    """
    stmt = select(func.coalesce(func.sum(StockMove.quantity_delta), 0)).where(
        StockMove.tenant_id == tenant_id, StockMove.product_id == product_id
    )
    return Decimal((await session.execute(stmt)).scalar_one())
