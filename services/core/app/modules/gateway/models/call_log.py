import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin

# One row per MCP tools/call, read or write -- distinct from audit_log, which only
# fires on a command's commit (ARCHITECTURE.md §9: "audit of every tool call").
# A rejected call (bad scope, missing entitlement, rate-limited) still gets a row
# here with success=False, which audit_log by design never records.


class GatewayCallLog(TenantMixin, Base):
    __tablename__ = "gateway_call_log"
    __table_args__ = (
        Index("ix_gateway_call_log_tenant_id", "tenant_id"),
        Index("ix_gateway_call_log_tenant_id_created_at", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    access_token_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
