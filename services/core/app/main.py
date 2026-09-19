"""FastAPI app for services/core.

Wires the REST API for apps/web (ARCHITECTURE.md §4). The MCP gateway
(services/mcp-gateway) is a separate service, landing in Phase 2. Auth here is a
placeholder `X-Tenant-Id` header -- real OAuth 2.1 / scoped tokens are Phase 2
(ROADMAP.md). app/api/deps.py's `get_tenant_db` is the *only* place a request
resolves a tenant id, per the tenancy decision in ARCHITECTURE.md §3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import catalog, parties, purchasing, sales
from app.api.deps import get_tenant_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(title="erp-core", lifespan=lifespan)

# Dev-only CORS for apps/web running locally. Both hostnames are listed because
# browsers treat localhost and 127.0.0.1 as different origins. Tightened (or
# replaced by a same-origin deploy) before this goes anywhere near a real tenant.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parties.router)
app.include_router(catalog.router)
app.include_router(sales.router)
app.include_router(purchasing.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/tenant")
async def health_tenant(session: AsyncSession = Depends(get_tenant_db)) -> dict[str, str]:
    """Round-trips through the tenancy seam so a smoke test can prove
    `SET app.tenant_id` is actually happening on live connections, not just in tests."""
    return {"status": "ok"}
