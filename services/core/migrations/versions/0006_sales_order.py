"""sales: sales_order, sales_order_line.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.rls import enable_rls

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales_order",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.UniqueConstraint("tenant_id", "id", name="uq_sales_order_tenant_id_id"),
    )
    op.create_index("ix_sales_order_tenant_id", "sales_order", ["tenant_id"])
    op.create_index("ix_sales_order_tenant_id_status", "sales_order", ["tenant_id", "status"])
    op.create_index(
        "ix_sales_order_tenant_id_order_date", "sales_order", ["tenant_id", "order_date"]
    )
    enable_rls("sales_order")

    op.create_table(
        "sales_order_line",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sales_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sales_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price_amount", sa.BigInteger(), nullable=False),
        sa.Column("line_total_amount", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_sales_order_line_tenant_id_id"),
    )
    op.create_index("ix_sales_order_line_tenant_id", "sales_order_line", ["tenant_id"])
    op.create_index(
        "ix_sales_order_line_tenant_id_sales_order_id",
        "sales_order_line",
        ["tenant_id", "sales_order_id"],
    )
    enable_rls("sales_order_line")


def downgrade() -> None:
    op.drop_table("sales_order_line")
    op.drop_table("sales_order")
