import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin


class Product(TenantMixin, Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_product_tenant_id_id"),
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_id_sku"),
        Index("ix_product_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "kg", "bunch", "case"
    base_price_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # minor units
    base_price_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
