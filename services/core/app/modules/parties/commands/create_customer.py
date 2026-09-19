"""parties.create_customer — the phase-0 reference command.

Deliberately not two-phase: creating a customer record is neither a money-, stock- nor
document-affecting change (GUARDRAILS.md §3), so it commits directly. It still goes
through the full command layer (idempotency, audit, outbox) as every command must.
"""

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.commands.base import Command, OutboxEventDraft
from app.modules.parties.models.customer import Customer


class CreateCustomerInput(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    vat_id: str | None = Field(default=None, max_length=32)


class CreateCustomerResult(BaseModel):
    customer_id: uuid.UUID
    name: str


class CreateCustomer(Command[CreateCustomerInput, CreateCustomerResult]):
    name = "parties.create_customer"
    result_type = CreateCustomerResult

    async def validate(self, input: CreateCustomerInput) -> None:
        return None

    async def summarize(self, input: CreateCustomerInput) -> str:
        return f"Create customer '{input.name}'"

    async def apply(
        self, input: CreateCustomerInput
    ) -> tuple[CreateCustomerResult, list[OutboxEventDraft]]:
        customer = Customer(
            tenant_id=self.ctx.tenant_id,
            name=input.name,
            email=input.email,
            vat_id=input.vat_id,
        )
        self.session.add(customer)
        await self.session.flush()  # assign customer.id before we reference it below

        result = CreateCustomerResult(customer_id=customer.id, name=customer.name)
        event = OutboxEventDraft(
            event_type="parties.customer_created.v1",
            payload={"customer_id": str(customer.id), "name": customer.name},
        )
        return result, [event]
