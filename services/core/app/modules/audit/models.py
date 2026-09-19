"""Audit log, transactional outbox and command proposals.

These three tables are the backbone of the command layer (docs/GUARDRAILS.md §2-3):
every commit writes an audit_log row and zero or more outbox_event rows in the same
transaction as the domain change, and every two-phase command's `propose` call is
persisted here so `commit` can verify the confirm_token against exactly what was
proposed.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin

JSONType = JSONB().with_variant(JSON(), "sqlite")


class AuditLog(TenantMixin, Base):
    """Append-only. One row per executed command. Never updated, never deleted."""

    __tablename__ = "audit_log"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "command_name", "idempotency_key", name="uq_audit_log_idempotency"
        ),
        Index("ix_audit_log_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    client: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    command_name: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    input_json: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False)
    result_json: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutboxEvent(TenantMixin, Base):
    """Transactional outbox: written in the same tx as the domain change, relayed to
    NATS JetStream by a separate poller. Never published outside a DB transaction.
    """

    __tablename__ = "outbox_event"
    __table_args__ = (Index("ix_outbox_event_tenant_id", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommandProposal(TenantMixin, Base):
    """A pending `propose` call for a two-phase command. `commit` must present the
    matching confirm_token before its expiry, and the input hash must match exactly
    what was proposed (GUARDRAILS.md §3).
    """

    __tablename__ = "command_proposal"
    __table_args__ = (Index("ix_command_proposal_tenant_id", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    command_name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    confirm_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
