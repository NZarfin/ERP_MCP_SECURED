"""Validates a `custom` JSONB payload against the tenant's CustomFieldDefinitions for
one entity, on every write (GUARDRAILS.md §1: "Custom data stays well-formed | JSON
Schema validation on every write to custom / custom_records"). Not a Command: called
from inside another command's validate(), same as inventory.service.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.base import ValidationFailedError
from app.modules.custom.models.field_definition import CustomFieldDefinition


def _check_type(key: str, field_type: str, value: object, validation: dict[str, object]) -> None:
    if field_type == "text" and not isinstance(value, str):
        raise ValidationFailedError(f"custom field '{key}' must be text")
    if field_type == "number" and (isinstance(value, bool) or not isinstance(value, int | float)):
        raise ValidationFailedError(f"custom field '{key}' must be a number")
    if field_type == "boolean" and not isinstance(value, bool):
        raise ValidationFailedError(f"custom field '{key}' must be a boolean")
    if field_type == "date":
        if not isinstance(value, str):
            raise ValidationFailedError(f"custom field '{key}' must be an ISO date string")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationFailedError(f"custom field '{key}' is not a valid ISO date") from exc
    if field_type == "select":
        options = validation.get("options", [])
        if not isinstance(options, list) or value not in options:
            raise ValidationFailedError(f"custom field '{key}' must be one of {options}")


async def validate_custom_fields(
    session: AsyncSession, tenant_id: uuid.UUID, entity: str, data: dict[str, object]
) -> None:
    definitions = (
        (
            await session.execute(
                select(CustomFieldDefinition).where(
                    CustomFieldDefinition.tenant_id == tenant_id,
                    CustomFieldDefinition.entity == entity,
                )
            )
        )
        .scalars()
        .all()
    )
    by_key = {d.key: d for d in definitions}

    unknown = set(data) - set(by_key)
    if unknown:
        raise ValidationFailedError(f"unknown custom field(s) for {entity}: {sorted(unknown)}")

    for key, definition in by_key.items():
        if definition.required and key not in data:
            raise ValidationFailedError(f"custom field '{key}' is required")
        if key in data:
            _check_type(key, definition.field_type, data[key], definition.validation)
