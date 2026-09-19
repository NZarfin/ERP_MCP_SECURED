import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin

JSONType = JSONB().with_variant(JSON(), "sqlite")

# What ARCHITECTURE.md §9 means by "scoped tokens" for Phase 2's bearer-token
# placeholder (real OAuth 2.1 against an IdP is a later, contained swap -- see
# services/mcp-gateway/README.md). The raw token is returned once by
# gateway.create_access_token and never stored; only its sha256 hash is.


class AccessToken(TenantMixin, Base):
    __tablename__ = "access_token"
    __table_args__ = (
        Index("ix_access_token_tenant_id", "tenant_id"),
        Index("ix_access_token_token_hash", "token_hash", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
