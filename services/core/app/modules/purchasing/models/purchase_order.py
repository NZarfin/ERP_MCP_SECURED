import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin

# draft -> confirmed -> received
#              \-> cancelled     (draft or confirmed can cancel; received cannot)
PURCHASE_ORDER_STATUSES = ("draft", "confirmed", "received", "cancelled")


class PurchaseOrder(TenantMixin, Base):
    __tablename__ = "purchase_order"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_purchase_order_tenant_id_id"),
        Index("ix_purchase_order_tenant_id", "tenant_id"),
        Index("ix_purchase_order_tenant_id_status", "tenant_id", "status"),
        Index("ix_purchase_order_tenant_id_order_date", "tenant_id", "order_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(TenantMixin, Base):
    __tablename__ = "purchase_order_line"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_purchase_order_line_tenant_id_id"),
        Index("ix_purchase_order_line_tenant_id", "tenant_id"),
        Index(
            "ix_purchase_order_line_tenant_id_purchase_order_id", "tenant_id", "purchase_order_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchase_order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
