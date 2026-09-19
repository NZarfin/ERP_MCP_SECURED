"""GatewayTokenVerifier in isolation, against a real (RLS-scoped) database --
no MCP transport involved. Malformed input, an unknown hash and a revoked token
must all return None (a rejection, not an exception) before any tool runs.
"""

from __future__ import annotations

import uuid

import pytest
from app.commands.base import CommandContext
from app.db.session import tenant_session
from app.modules.gateway.commands.create_access_token import (
    CreateAccessToken,
    CreateAccessTokenInput,
    CreateAccessTokenResult,
)
from app.modules.gateway.models.access_token import AccessToken as AccessTokenRow
from gateway.auth import GatewayTokenVerifier
from sqlalchemy import select

# module-scoped: app.db.session.engine is one module-level asyncpg pool shared by
# every test here, and pytest-asyncio's default per-function event loop makes a
# pooled connection from test N unusable (and unrecoverable, not just re-pinged)
# in test N+1's fresh loop. One loop for the whole module matches how the engine
# is actually used at runtime -- across many calls on one running event loop, not
# a new loop per call.
pytestmark = pytest.mark.asyncio(loop_scope="module")


async def _issue_token(tenant_id: uuid.UUID) -> str:
    ctx = CommandContext(tenant_id=tenant_id, actor="test", client="tests")
    async with tenant_session(tenant_id) as session:
        result = await CreateAccessToken(ctx, session).execute(
            CreateAccessTokenInput(name="test-token", scopes=["sales:read"]),
            idempotency_key=str(uuid.uuid4()),
        )
        assert isinstance(result, CreateAccessTokenResult)
        return result.token


async def test_valid_token_resolves_tenant_and_scopes(tenant_id: uuid.UUID) -> None:
    token = await _issue_token(tenant_id)

    resolved = await GatewayTokenVerifier().verify_token(token)

    assert resolved is not None
    assert resolved.client_id == str(tenant_id)
    assert resolved.scopes == ["sales:read"]


async def test_malformed_token_is_rejected() -> None:
    assert await GatewayTokenVerifier().verify_token("not-a-valid-token") is None
    assert await GatewayTokenVerifier().verify_token(f"{uuid.uuid4()}.") is None
    assert await GatewayTokenVerifier().verify_token("not-a-uuid.somesecret") is None


async def test_unknown_hash_is_rejected(tenant_id: uuid.UUID) -> None:
    assert await GatewayTokenVerifier().verify_token(f"{tenant_id}.not-the-real-secret") is None


async def test_revoked_token_is_rejected(tenant_id: uuid.UUID) -> None:
    token = await _issue_token(tenant_id)
    async with tenant_session(tenant_id) as session:
        row = (
            await session.execute(
                select(AccessTokenRow).where(AccessTokenRow.tenant_id == tenant_id)
            )
        ).scalar_one()
        row.revoked_at = row.created_at

    assert await GatewayTokenVerifier().verify_token(token) is None


async def test_a_tenants_token_cannot_resolve_into_another_tenant(tenant_id: uuid.UUID) -> None:
    """The tenant id is embedded in the token itself, so a token minted for one
    tenant structurally cannot verify against another tenant's row, even if the
    secret happened to collide -- see gateway/auth.py's own docstring."""
    other_tenant_id = uuid.uuid4()
    token = await _issue_token(tenant_id)
    _, _, secret = token.partition(".")
    forged = f"{other_tenant_id}.{secret}"

    assert await GatewayTokenVerifier().verify_token(forged) is None
