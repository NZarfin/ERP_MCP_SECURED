"""GUARDRAILS.md §1: 'Tenants cannot see each other.' Proves RLS actually blocks a
cross-tenant read (and a cross-tenant write attempt), against the real database with
app_rw -- not by trusting the policy SQL to be correct.
"""

import uuid

import pytest
from app.commands.base import CommandContext
from app.db.session import tenant_session
from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from sqlalchemy import text


@pytest.mark.asyncio
async def test_tenant_b_cannot_read_tenant_a_customer(
    tenant_a: uuid.UUID, tenant_b: uuid.UUID
) -> None:
    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test")
        result = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="Acme"), idempotency_key=str(uuid.uuid4())
        )

    async with tenant_session(tenant_b) as session:
        row = await session.execute(
            text("SELECT id FROM customer WHERE id = :id"), {"id": str(result.customer_id)}
        )
        assert row.first() is None, "tenant B could read tenant A's customer through RLS"


@pytest.mark.asyncio
async def test_cross_tenant_insert_is_rejected_by_row_level_security(
    tenant_a: uuid.UUID, tenant_b: uuid.UUID
) -> None:
    """Even a raw SQL insert (bypassing the command layer entirely) cannot plant a row
    under another tenant's id once the session is scoped to tenant_a -- WITH CHECK on
    the RLS policy rejects it, not just application-level validation.
    """
    from sqlalchemy.exc import DBAPIError

    async with tenant_session(tenant_a) as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text(
                    "INSERT INTO customer (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'sneaky')"
                ),
                {"tenant_id": str(tenant_b)},
            )
