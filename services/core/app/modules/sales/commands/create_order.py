"""sales.create_order — draft creation. Single-phase: a draft commits nothing yet
(GUARDRAILS.md §3 only requires two-phase once a command touches money/stock/documents
for real; confirm_order is where a sales order becomes a commitment).
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.core.money import from_minor_units, to_minor_units
from app.modules.catalog.models.product import Product
from app.modules.parties.models.customer import Customer
from app.modules.sales.models.sales_order import SalesOrder, SalesOrderLine


class CreateOrderLineInput(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal | None = None  # defaults to the product's base_price


class CreateOrderInput(BaseModel):
    model_config = {"extra": "forbid"}

    customer_id: uuid.UUID
    order_date: date
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    lines: list[CreateOrderLineInput] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=2000)


class CreateOrderResult(BaseModel):
    sales_order_id: uuid.UUID
    status: str
    total_amount: Decimal


class CreateOrder(Command[CreateOrderInput, CreateOrderResult]):
    name = "sales.create_order"
    result_type = CreateOrderResult

    async def validate(self, input: CreateOrderInput) -> None:
        # GUARDRAILS.md §5: IDs are never trusted as-is -- resolve them deterministically
        # within the tenant. RLS already scopes these SELECTs; the explicit tenant_id
        # filter documents the invariant and survives a future RLS regression.
        customer = (
            await self.session.execute(
                select(Customer.id).where(
                    Customer.id == input.customer_id, Customer.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalar_one_or_none()
        if customer is None:
            raise ValidationFailedError(f"unknown customer_id {input.customer_id}")

        product_ids = {line.product_id for line in input.lines}
        found = set(
            (
                await self.session.execute(
                    select(Product.id).where(
                        Product.id.in_(product_ids), Product.tenant_id == self.ctx.tenant_id
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = product_ids - found
        if missing:
            raise ValidationFailedError(f"unknown product_id(s): {sorted(missing)}")

    async def summarize(self, input: CreateOrderInput) -> str:
        return (
            f"Create draft sales order for customer {input.customer_id} ({len(input.lines)} lines)"
        )

    async def apply(
        self, input: CreateOrderInput
    ) -> tuple[CreateOrderResult, list[OutboxEventDraft]]:
        products = {
            product.id: product
            for product in (
                await self.session.execute(
                    select(Product).where(
                        Product.id.in_({line.product_id for line in input.lines}),
                        Product.tenant_id == self.ctx.tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        }

        order = SalesOrder(
            tenant_id=self.ctx.tenant_id,
            customer_id=input.customer_id,
            status="draft",
            order_date=input.order_date,
            currency=input.currency,
            total_amount=0,
            notes=input.notes,
        )
        self.session.add(order)
        await self.session.flush()

        total_minor = 0
        for line_input in input.lines:
            product = products[line_input.product_id]
            unit_price = line_input.unit_price
            unit_price_minor = (
                to_minor_units(unit_price) if unit_price is not None else product.base_price_amount
            )
            line_total_minor = round(line_input.quantity * unit_price_minor)
            total_minor += line_total_minor
            self.session.add(
                SalesOrderLine(
                    tenant_id=self.ctx.tenant_id,
                    sales_order_id=order.id,
                    product_id=product.id,
                    description=product.name,
                    quantity=line_input.quantity,
                    unit_price_amount=unit_price_minor,
                    line_total_amount=line_total_minor,
                )
            )

        order.total_amount = total_minor
        await self.session.flush()

        result = CreateOrderResult(
            sales_order_id=order.id,
            status=order.status,
            total_amount=from_minor_units(total_minor),
        )
        event = OutboxEventDraft(
            event_type="sales.order_created.v1",
            payload={"sales_order_id": str(order.id), "customer_id": str(input.customer_id)},
        )
        return result, [event]
