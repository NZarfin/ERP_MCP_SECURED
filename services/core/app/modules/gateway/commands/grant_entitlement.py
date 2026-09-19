"""gateway.grant_entitlement — provisions a tenant's access to a module's tools.
Single-phase: this is what a billing/provisioning system calls when a subscription
starts (Phase 8 wires a real billing system to this; the seed script stands in for
it now). Not itself money-moving in this system's frame -- the billing charge is a
separate, external concern.
"""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.gateway.models.entitlement import Entitlement

VALID_SKUS = ("core.parties", "core.catalog", "core.sales", "core.purchasing")


class GrantEntitlementInput(BaseModel):
    model_config = {"extra": "forbid"}

    sku: str = Field(min_length=1, max_length=64)


class GrantEntitlementResult(BaseModel):
    entitlement_id: uuid.UUID
    sku: str


class GrantEntitlement(Command[GrantEntitlementInput, GrantEntitlementResult]):
    name = "gateway.grant_entitlement"
    result_type = GrantEntitlementResult

    async def validate(self, input: GrantEntitlementInput) -> None:
        if input.sku not in VALID_SKUS:
            raise ValidationFailedError(f"unknown sku '{input.sku}'")
        existing = (
            await self.session.execute(
                select(Entitlement.id).where(
                    Entitlement.tenant_id == self.ctx.tenant_id, Entitlement.sku == input.sku
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationFailedError(f"sku '{input.sku}' already granted")

    async def summarize(self, input: GrantEntitlementInput) -> str:
        return f"Grant entitlement '{input.sku}'"

    async def apply(
        self, input: GrantEntitlementInput
    ) -> tuple[GrantEntitlementResult, list[OutboxEventDraft]]:
        entitlement = Entitlement(tenant_id=self.ctx.tenant_id, sku=input.sku)
        self.session.add(entitlement)
        await self.session.flush()

        result = GrantEntitlementResult(entitlement_id=entitlement.id, sku=entitlement.sku)
        event = OutboxEventDraft(
            event_type="gateway.entitlement_granted.v1",
            payload={"sku": input.sku},
        )
        return result, [event]
