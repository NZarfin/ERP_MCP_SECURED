import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin

# Which modules' tools a tenant's gateway session can see and call
# (ARCHITECTURE.md §9: "Disabled module ⇒ tools not listed and calls rejected").
# SKUs match the tool groups in services/mcp-gateway/app/tools/: core.parties,
# core.catalog, core.sales, core.purchasing. Real paid-plugin SKUs (mod_whatsapp,
# etc., per docs/PLUGIN_CONTRACT.md) land the same way once those plugins exist.


class Entitlement(TenantMixin, Base):
    __tablename__ = "entitlement"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_entitlement_tenant_id_sku"),
        Index("ix_entitlement_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
