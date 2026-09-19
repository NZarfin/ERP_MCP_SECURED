import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TenantMixin:
    """Mixin for every tenant-owned table.

    Per CLAUDE.md: "Every tenant table has tenant_id, RLS policy, and an index
    starting with tenant_id." The RLS policy and index are added in the migration
    that creates the table (see migrations/rls.py); this mixin only guarantees the
    column exists and is never nullable, so a table cannot be created without it.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


def tenant_table_names(base: type[Base] = Base) -> set[str]:
    """Every table that declares a tenant_id column, used by the RLS coverage test."""
    return {table.name for table in base.metadata.tables.values() if "tenant_id" in table.columns}
