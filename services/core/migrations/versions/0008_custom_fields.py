"""custom: custom_field_definition; sales_order gets a validated `custom` JSONB column.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.rls import enable_rls

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_field_definition",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column(
            "validation", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "entity", "key", name="uq_custom_field_definition_tenant_entity_key"
        ),
    )
    op.create_index(
        "ix_custom_field_definition_tenant_id", "custom_field_definition", ["tenant_id"]
    )
    enable_rls("custom_field_definition")

    op.add_column(
        "sales_order",
        sa.Column(
            "custom", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )


def downgrade() -> None:
    op.drop_column("sales_order", "custom")
    op.drop_table("custom_field_definition")
