import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin

JSONType = JSONB().with_variant(JSON(), "sqlite")


# draft -> confirmed -> delivered
#              \-> cancelled     (draft or confirmed can cancel; delivered cannot)
SALES_ORDER_STATUSES = ("draft", "confirmed", "delivered", "cancelled")


class SalesOrder(TenantMixin, Base):
    __tablename__ = "sales_order"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_sales_order_tenant_id_id"),
        Index("ix_sales_order_tenant_id", "tenant_id"),
        Index("ix_sales_order_tenant_id_status", "tenant_id", "status"),
        Index("ix_sales_order_tenant_id_order_date", "tenant_id", "order_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    custom: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class SalesOrderLine(TenantMixin, Base):
    __tablename__ = "sales_order_line"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_sales_order_line_tenant_id_id"),
        Index("ix_sales_order_line_tenant_id", "tenant_id"),
        Index("ix_sales_order_line_tenant_id_sales_order_id", "tenant_id", "sales_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[SalesOrder] = relationship(back_populates="lines")
