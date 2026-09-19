"""The tenancy seam.

`tenant_session` is the only supported way to get a database session anywhere in this
service: the MCP gateway, the REST API, the automation engine and tests all go through
it. It opens one transaction and scopes it to a tenant via `set_config(...,  true)`
(the parameterized equivalent of `SET LOCAL`, since PostgreSQL's `SET` does not accept
bind parameters). Every tenant table's Row-Level Security policy reads
`current_setting('app.tenant_id')`, so a session that never called this function can
read or write nothing in a tenant table -- there is no way to "forget" the tenant.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.tenancy import current_tenant_id

_settings = get_settings()

engine: AsyncEngine = create_async_engine(_settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def tenant_session(
    tenant_id: UUID, *, session_factory: async_sessionmaker[AsyncSession] = SessionFactory
) -> AsyncIterator[AsyncSession]:
    token = current_tenant_id.set(tenant_id)
    try:
        async with session_factory() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            yield session
    finally:
        current_tenant_id.reset(token)
