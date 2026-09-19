"""Phase 0 exit criterion (ROADMAP.md): 'a demo command writes a row, audit entry
and event in one tx.' Also covers idempotency and the propose/commit two-phase flow
required by GUARDRAILS.md §3, using a small test-only two-phase command so the
mechanism is proven without adding a real money/stock/document command in phase 0.
"""

from __future__ import annotations

import uuid

import pytest
from app.commands.base import Command, CommandContext, OutboxEventDraft, ProposalRequiredError
from app.db.session import tenant_session
from app.modules.audit.models import AuditLog, OutboxEvent
from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from app.modules.parties.models.customer import Customer
from pydantic import BaseModel
from sqlalchemy import select, text


@pytest.mark.asyncio
async def test_create_customer_writes_row_audit_and_outbox_in_one_tx(
    tenant_a: uuid.UUID,
) -> None:
    idempotency_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test-user")
        result = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="Acme Herbs", email="buyer@acme.example.com"),
            idempotency_key=idempotency_key,
        )

    async with tenant_session(tenant_a) as session:
        customer = (
            await session.execute(select(Customer).where(Customer.id == result.customer_id))
        ).scalar_one()
        assert customer.name == "Acme Herbs"

        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.idempotency_key == idempotency_key)
            )
        ).scalar_one()
        assert audit.command_name == "parties.create_customer"
        assert audit.actor == "test-user"

        event = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "parties.customer_created.v1")
            )
        ).scalar_one()
        assert event.payload_json["customer_id"] == str(result.customer_id)


@pytest.mark.asyncio
async def test_retry_with_same_idempotency_key_does_not_duplicate(tenant_a: uuid.UUID) -> None:
    idempotency_key = str(uuid.uuid4())
    input_ = CreateCustomerInput(name="Once Only")

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test-user")
        first = await CreateCustomer(ctx, session).execute(input_, idempotency_key=idempotency_key)

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test-user")
        second = await CreateCustomer(ctx, session).execute(input_, idempotency_key=idempotency_key)

    assert first.customer_id == second.customer_id

    async with tenant_session(tenant_a) as session:
        count = await session.execute(
            text("SELECT count(*) FROM customer WHERE name = 'Once Only'")
        )
        assert count.scalar_one() == 1


class _EchoInput(BaseModel):
    model_config = {"extra": "forbid"}
    message: str


class _EchoResult(BaseModel):
    message: str


class _TwoPhaseEcho(Command[_EchoInput, _EchoResult]):
    """Test-only command proving the propose -> confirm_token -> commit mechanism."""

    name = "test.two_phase_echo"
    result_type = _EchoResult
    two_phase = True

    async def validate(self, input: _EchoInput) -> None:
        return None

    async def summarize(self, input: _EchoInput) -> str:
        return f"Echo '{input.message}'"

    async def apply(self, input: _EchoInput) -> tuple[_EchoResult, list[OutboxEventDraft]]:
        return _EchoResult(message=input.message), []


@pytest.mark.asyncio
async def test_two_phase_commit_requires_a_matching_confirm_token(tenant_a: uuid.UUID) -> None:
    idempotency_key = str(uuid.uuid4())
    input_ = _EchoInput(message="hello")

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test-user")
        with pytest.raises(ProposalRequiredError):
            await _TwoPhaseEcho(ctx, session).execute(input_, idempotency_key=idempotency_key)

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test-user")
        proposal = await _TwoPhaseEcho(ctx, session).execute(
            input_, idempotency_key=idempotency_key, mode="propose"
        )

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test-user")
        result = await _TwoPhaseEcho(ctx, session).execute(
            input_,
            idempotency_key=idempotency_key,
            mode="commit",
            confirm_token=proposal.confirm_token,
        )
        assert result.message == "hello"
