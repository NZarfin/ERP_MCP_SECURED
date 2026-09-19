"""parties: supplier table; catalog: product table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.rls import enable_rls

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supplier",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("vat_id", sa.String(32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_supplier_tenant_id_id"),
    )
    op.create_index("ix_supplier_tenant_id", "supplier", ["tenant_id"])
    enable_rls("supplier")

    op.create_table(
        "product",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("base_price_amount", sa.BigInteger(), nullable=False),
        sa.Column("base_price_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_product_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_id_sku"),
    )
    op.create_index("ix_product_tenant_id", "product", ["tenant_id"])
    enable_rls("product")


def downgrade() -> None:
    op.drop_table("product")
    op.drop_table("supplier")
