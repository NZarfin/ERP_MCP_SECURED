import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin

# ARCHITECTURE.md §4: "inventory — locations, stock moves (append-only ledger), lots /
# best-before dates". There is deliberately no mutable "current stock" table: balance
# is SUM(quantity_delta) grouped by product/location (see queries/get_stock_balance.py)
# -- fine at prototype scale, and it means a correction is always a new row, never an
# UPDATE, matching how the rest of this system treats financial/stock history.


class StockMove(TenantMixin, Base):
    __tablename__ = "stock_move"
    __table_args__ = (
        Index("ix_stock_move_tenant_id", "tenant_id"),
        Index("ix_stock_move_tenant_id_product_id", "tenant_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    lot_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    best_before_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # receipt/delivery/adjustment
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
