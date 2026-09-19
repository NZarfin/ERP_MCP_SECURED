"""Test fixtures.

Assumes the database pointed to by ERP_DATABASE_URL / ERP_MIGRATOR_DATABASE_URL has
already had `alembic upgrade head` run against it (that's a separate CI stage per
CICD.md -- "Migrations" runs before "Tests"). Tests never create tables themselves;
that would let a test accidentally hide a migration bug.

Each test gets fresh random tenant ids, so tests never need to share state or clean
up between runs -- RLS means a stray row from a failed test is invisible to every
other tenant anyway.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import psycopg
import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.db.session import tenant_session
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def tenant_a() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def tenant_b() -> uuid.UUID:
    return uuid.uuid4()


@pytest_asyncio.fixture
async def session_a(tenant_a: uuid.UUID) -> AsyncIterator[AsyncSession]:
    async with tenant_session(tenant_a) as session:
        yield session


@pytest_asyncio.fixture
async def session_b(tenant_b: uuid.UUID) -> AsyncIterator[AsyncSession]:
    async with tenant_session(tenant_b) as session:
        yield session


def sync_dsn(url: str) -> str:
    """psycopg wants a plain postgresql:// DSN; strip SQLAlchemy's dialect suffix."""
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


@pytest.fixture(scope="session")
def migrator_conn() -> AsyncIterator[psycopg.Connection]:
    settings = get_settings()
    conn = psycopg.connect(sync_dsn(settings.migrator_database_url))
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def app_rw_dsn() -> str:
    settings = get_settings()
    return sync_dsn(settings.database_url)
