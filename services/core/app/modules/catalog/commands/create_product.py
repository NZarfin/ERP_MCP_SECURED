import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.commands.base import Command, OutboxEventDraft
from app.core.money import to_minor_units
from app.modules.catalog.models.product import Product


class CreateProductInput(BaseModel):
    model_config = {"extra": "forbid"}

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=32)
    base_price: Decimal = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class CreateProductResult(BaseModel):
    product_id: uuid.UUID
    sku: str


class CreateProduct(Command[CreateProductInput, CreateProductResult]):
    name = "catalog.create_product"
    result_type = CreateProductResult

    async def validate(self, input: CreateProductInput) -> None:
        return None

    async def summarize(self, input: CreateProductInput) -> str:
        return f"Create product '{input.name}' ({input.sku})"

    async def apply(
        self, input: CreateProductInput
    ) -> tuple[CreateProductResult, list[OutboxEventDraft]]:
        product = Product(
            tenant_id=self.ctx.tenant_id,
            sku=input.sku,
            name=input.name,
            unit=input.unit,
            base_price_amount=to_minor_units(input.base_price),
            base_price_currency=input.currency,
        )
        self.session.add(product)
        await self.session.flush()

        result = CreateProductResult(product_id=product.id, sku=product.sku)
        event = OutboxEventDraft(
            event_type="catalog.product_created.v1",
            payload={"product_id": str(product.id), "sku": product.sku},
        )
        return result, [event]
