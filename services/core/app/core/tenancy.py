"""The one place tenancy is resolved: token/header -> tenant id -> DB session.

Per docs/ARCHITECTURE.md §3: "Tenancy is resolved in exactly one place ... so moving a
tenant between tiers is a data migration, not a rewrite." Everything else (commands,
queries, the MCP gateway, the web app) receives an already-scoped session and never
handles a tenant id string itself.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)


class NoTenantContextError(RuntimeError):
    """Raised when code tries to touch tenant-scoped state outside a tenant session."""


def require_current_tenant_id() -> UUID:
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise NoTenantContextError("No tenant is bound to the current context")
    return tenant_id
