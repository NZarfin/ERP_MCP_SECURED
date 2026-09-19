import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin

JSONType = JSONB().with_variant(JSON(), "sqlite")

# Only sales_order is wired up to validate against its definitions this pass
# (ARCHITECTURE.md §4: "AI may propose a field via custom.define_field; it can never
# alter columns" -- proven end-to-end on one entity, not fanned out to every table yet).
SUPPORTED_ENTITIES = ("sales_order",)
SUPPORTED_FIELD_TYPES = ("text", "number", "boolean", "date", "select")


class CustomFieldDefinition(TenantMixin, Base):
    __tablename__ = "custom_field_definition"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entity", "key", name="uq_custom_field_definition_tenant_entity_key"
        ),
        Index("ix_custom_field_definition_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    validation: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False, default=dict)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
