"""custom.define_field — AI proposes a field, never a column. Single-phase: defining
metadata isn't itself money/stock/document-affecting (existing records with the
`custom` JSONB column are validated against definitions on every write, not
retroactively).
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.modules.custom.models.field_definition import (
    SUPPORTED_ENTITIES,
    SUPPORTED_FIELD_TYPES,
    CustomFieldDefinition,
)

KEY_PATTERN_MSG = "key must be lowercase snake_case (e.g. 'harvest_region')"


class DefineFieldInput(BaseModel):
    model_config = {"extra": "forbid"}

    entity: Literal["sales_order"]
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=255)
    field_type: Literal["text", "number", "boolean", "date", "select"]
    validation: dict[str, object] = Field(default_factory=dict)
    required: bool = False

    @field_validator("key")
    @classmethod
    def _key_is_snake_case(cls, value: str) -> str:
        if not value.replace("_", "").isalnum() or not value.islower() or value[0].isdigit():
            raise ValueError(KEY_PATTERN_MSG)
        return value


class DefineFieldResult(BaseModel):
    field_definition_id: uuid.UUID
    entity: str
    key: str


class DefineField(Command[DefineFieldInput, DefineFieldResult]):
    name = "custom.define_field"
    result_type = DefineFieldResult

    async def validate(self, input: DefineFieldInput) -> None:
        if input.entity not in SUPPORTED_ENTITIES:
            raise ValidationFailedError(f"entity '{input.entity}' does not support custom fields")
        if input.field_type not in SUPPORTED_FIELD_TYPES:
            raise ValidationFailedError(f"unsupported field_type '{input.field_type}'")
        if input.field_type == "select" and not input.validation.get("options"):
            raise ValidationFailedError("field_type 'select' requires validation.options")

        existing = (
            await self.session.execute(
                select(CustomFieldDefinition.id).where(
                    CustomFieldDefinition.tenant_id == self.ctx.tenant_id,
                    CustomFieldDefinition.entity == input.entity,
                    CustomFieldDefinition.key == input.key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationFailedError(f"field '{input.key}' already defined for {input.entity}")

    async def summarize(self, input: DefineFieldInput) -> str:
        return f"Define custom field '{input.key}' ({input.field_type}) on {input.entity}"

    async def apply(
        self, input: DefineFieldInput
    ) -> tuple[DefineFieldResult, list[OutboxEventDraft]]:
        definition = CustomFieldDefinition(
            tenant_id=self.ctx.tenant_id,
            entity=input.entity,
            key=input.key,
            label=input.label,
            field_type=input.field_type,
            validation=input.validation,
            required=input.required,
        )
        self.session.add(definition)
        await self.session.flush()

        result = DefineFieldResult(
            field_definition_id=definition.id, entity=definition.entity, key=definition.key
        )
        event = OutboxEventDraft(
            event_type="custom.field_defined.v1",
            payload={"entity": input.entity, "key": input.key},
        )
        return result, [event]
