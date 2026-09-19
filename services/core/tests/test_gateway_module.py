import uuid

import pytest
from app.commands.base import CommandContext, ValidationFailedError
from app.db.session import tenant_session
from app.modules.audit.models import AuditLog
from app.modules.gateway.commands.create_access_token import (
    CreateAccessToken,
    CreateAccessTokenInput,
    CreateAccessTokenResult,
)
from app.modules.gateway.commands.grant_entitlement import GrantEntitlement, GrantEntitlementInput
from app.modules.gateway.models.access_token import AccessToken
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_access_token_returns_raw_token_but_never_stores_it(
    tenant_a: uuid.UUID,
) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    idempotency_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        result = await CreateAccessToken(ctx, session).execute(
            CreateAccessTokenInput(name="test-client", scopes=["sales:read", "sales:write"]),
            idempotency_key=idempotency_key,
        )
        assert isinstance(result, CreateAccessTokenResult)
        raw_token = result.token
        assert len(raw_token) > 20

    async with tenant_session(tenant_a) as session:
        # The stored row only ever has the hash.
        stored = (
            await session.execute(
                select(AccessToken).where(AccessToken.id == result.access_token_id)
            )
        ).scalar_one()
        assert stored.token_hash != raw_token
        assert len(stored.token_hash) == 64  # sha256 hex digest

        # And the audit log -- which retries replay from -- never has the raw token
        # either (CLAUDE.md: never log tokens; app/commands/base.py's
        # redact_for_audit is what enforces this for this specific command).
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.idempotency_key == idempotency_key)
            )
        ).scalar_one()
        assert audit.result_json["token"] == "***redacted***"
        assert raw_token not in str(audit.result_json)


@pytest.mark.asyncio
async def test_create_access_token_idempotent_retry_returns_redacted_not_original(
    tenant_a: uuid.UUID,
) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    idempotency_key = str(uuid.uuid4())
    input_ = CreateAccessTokenInput(name="retry-client", scopes=["sales:read"])

    async with tenant_session(tenant_a) as session:
        first = await CreateAccessToken(ctx, session).execute(
            input_, idempotency_key=idempotency_key
        )
        assert isinstance(first, CreateAccessTokenResult)

    async with tenant_session(tenant_a) as session:
        second = await CreateAccessToken(ctx, session).execute(
            input_, idempotency_key=idempotency_key
        )
        assert isinstance(second, CreateAccessTokenResult)

    assert second.token == "***redacted***"
    assert first.token != second.token


@pytest.mark.asyncio
async def test_create_access_token_rejects_unknown_scope(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await CreateAccessToken(ctx, session).execute(
                CreateAccessTokenInput(name="bad-client", scopes=["admin:god-mode"]),
                idempotency_key=str(uuid.uuid4()),
            )


@pytest.mark.asyncio
async def test_grant_entitlement_rejects_duplicate_and_unknown_sku(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        await GrantEntitlement(ctx, session).execute(
            GrantEntitlementInput(sku="core.sales"), idempotency_key=str(uuid.uuid4())
        )

    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await GrantEntitlement(ctx, session).execute(
                GrantEntitlementInput(sku="core.sales"), idempotency_key=str(uuid.uuid4())
            )

    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await GrantEntitlement(ctx, session).execute(
                GrantEntitlementInput(sku="mod_whatsapp"), idempotency_key=str(uuid.uuid4())
            )
