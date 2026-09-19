"""FastAPI app skeleton for services/core.

Phase 0 only wires the tenancy seam and a health check; the REST API for the web app
(ARCHITECTURE.md §4) and the MCP gateway (services/mcp-gateway) land in later phases.
Auth here is a placeholder `X-Tenant-Id` header -- real OAuth 2.1 / scoped tokens are
phase 2 (ROADMAP.md). This is intentionally the *only* place a request resolves a
tenant id, per the tenancy decision in ARCHITECTURE.md §3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import tenant_session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(title="erp-core", lifespan=lifespan)


async def get_tenant_db(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
) -> AsyncIterator[AsyncSession]:
    try:
        tenant_id = UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-Id must be a UUID") from exc
    async with tenant_session(tenant_id) as session:
        yield session


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/tenant")
async def health_tenant(session: AsyncSession = Depends(get_tenant_db)) -> dict[str, str]:
    """Round-trips through the tenancy seam so a smoke test can prove
    `SET app.tenant_id` is actually happening on live connections, not just in tests."""
    return {"status": "ok"}
