"""purchasing: purchase_order, purchase_order_line.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.rls import enable_rls

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchase_order",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("total_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_purchase_order_tenant_id_id"),
    )
    op.create_index("ix_purchase_order_tenant_id", "purchase_order", ["tenant_id"])
    op.create_index("ix_purchase_order_tenant_id_status", "purchase_order", ["tenant_id", "status"])
    op.create_index(
        "ix_purchase_order_tenant_id_order_date", "purchase_order", ["tenant_id", "order_date"]
    )
    enable_rls("purchase_order")

    op.create_table(
        "purchase_order_line",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "purchase_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price_amount", sa.BigInteger(), nullable=False),
        sa.Column("line_total_amount", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_purchase_order_line_tenant_id_id"),
    )
    op.create_index("ix_purchase_order_line_tenant_id", "purchase_order_line", ["tenant_id"])
    op.create_index(
        "ix_purchase_order_line_tenant_id_purchase_order_id",
        "purchase_order_line",
        ["tenant_id", "purchase_order_id"],
    )
    enable_rls("purchase_order_line")


def downgrade() -> None:
    op.drop_table("purchase_order_line")
    op.drop_table("purchase_order")
