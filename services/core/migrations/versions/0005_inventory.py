"""inventory: location, stock_move (append-only ledger).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.rls import enable_rls

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "location",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_location_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_location_tenant_id_code"),
    )
    op.create_index("ix_location_tenant_id", "location", ["tenant_id"])
    enable_rls("location")

    op.create_table(
        "stock_move",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 3), nullable=False),
        sa.Column("lot_code", sa.String(64), nullable=True),
        sa.Column("best_before_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("reference_type", sa.String(32), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_stock_move_tenant_id", "stock_move", ["tenant_id"])
    op.create_index("ix_stock_move_tenant_id_product_id", "stock_move", ["tenant_id", "product_id"])
    enable_rls("stock_move")


def downgrade() -> None:
    op.drop_table("stock_move")
    op.drop_table("location")
