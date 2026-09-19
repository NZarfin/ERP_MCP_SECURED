"""gateway: access_token, entitlement, gateway_call_log.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.rls import enable_rls

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_token",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "scopes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_access_token_tenant_id", "access_token", ["tenant_id"])
    op.create_index("ix_access_token_token_hash", "access_token", ["token_hash"], unique=True)
    enable_rls("access_token")

    op.create_table(
        "entitlement",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_entitlement_tenant_id_sku"),
    )
    op.create_index("ix_entitlement_tenant_id", "entitlement", ["tenant_id"])
    enable_rls("entitlement")

    op.create_table(
        "gateway_call_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(20), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_gateway_call_log_tenant_id", "gateway_call_log", ["tenant_id"])
    op.create_index(
        "ix_gateway_call_log_tenant_id_created_at",
        "gateway_call_log",
        ["tenant_id", "created_at"],
    )
    enable_rls("gateway_call_log")


def downgrade() -> None:
    op.drop_table("gateway_call_log")
    op.drop_table("entitlement")
    op.drop_table("access_token")
