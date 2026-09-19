import uuid

from pydantic import BaseModel, Field

from app.commands.base import Command, OutboxEventDraft
from app.modules.inventory.models.location import Location


class CreateLocationInput(BaseModel):
    model_config = {"extra": "forbid"}

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)


class CreateLocationResult(BaseModel):
    location_id: uuid.UUID
    code: str


class CreateLocation(Command[CreateLocationInput, CreateLocationResult]):
    name = "inventory.create_location"
    result_type = CreateLocationResult

    async def validate(self, input: CreateLocationInput) -> None:
        return None

    async def summarize(self, input: CreateLocationInput) -> str:
        return f"Create location '{input.name}' ({input.code})"

    async def apply(
        self, input: CreateLocationInput
    ) -> tuple[CreateLocationResult, list[OutboxEventDraft]]:
        location = Location(tenant_id=self.ctx.tenant_id, code=input.code, name=input.name)
        self.session.add(location)
        await self.session.flush()

        result = CreateLocationResult(location_id=location.id, code=location.code)
        event = OutboxEventDraft(
            event_type="inventory.location_created.v1",
            payload={"location_id": str(location.id), "code": location.code},
        )
        return result, [event]
