"""parties.create_supplier — same shape and rationale as create_customer.py."""

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.commands.base import Command, OutboxEventDraft
from app.modules.parties.models.supplier import Supplier


class CreateSupplierInput(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    vat_id: str | None = Field(default=None, max_length=32)


class CreateSupplierResult(BaseModel):
    supplier_id: uuid.UUID
    name: str


class CreateSupplier(Command[CreateSupplierInput, CreateSupplierResult]):
    name = "parties.create_supplier"
    result_type = CreateSupplierResult

    async def validate(self, input: CreateSupplierInput) -> None:
        return None

    async def summarize(self, input: CreateSupplierInput) -> str:
        return f"Create supplier '{input.name}'"

    async def apply(
        self, input: CreateSupplierInput
    ) -> tuple[CreateSupplierResult, list[OutboxEventDraft]]:
        supplier = Supplier(
            tenant_id=self.ctx.tenant_id,
            name=input.name,
            email=input.email,
            vat_id=input.vat_id,
        )
        self.session.add(supplier)
        await self.session.flush()

        result = CreateSupplierResult(supplier_id=supplier.id, name=supplier.name)
        event = OutboxEventDraft(
            event_type="parties.supplier_created.v1",
            payload={"supplier_id": str(supplier.id), "name": supplier.name},
        )
        return result, [event]
