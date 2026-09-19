"""purchasing.create_po — draft creation, mirrors sales.create_order. Single-phase:
a draft commits nothing yet.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.commands.base import Command, OutboxEventDraft, ValidationFailedError
from app.core.money import from_minor_units, to_minor_units
from app.modules.catalog.models.product import Product
from app.modules.parties.models.supplier import Supplier
from app.modules.purchasing.models.purchase_order import PurchaseOrder, PurchaseOrderLine


class CreatePoLineInput(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal | None = None  # defaults to the product's base_price


class CreatePoInput(BaseModel):
    model_config = {"extra": "forbid"}

    supplier_id: uuid.UUID
    order_date: date
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    lines: list[CreatePoLineInput] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=2000)


class CreatePoResult(BaseModel):
    purchase_order_id: uuid.UUID
    status: str
    total_amount: Decimal


class CreatePo(Command[CreatePoInput, CreatePoResult]):
    name = "purchasing.create_po"
    result_type = CreatePoResult

    async def validate(self, input: CreatePoInput) -> None:
        supplier = (
            await self.session.execute(
                select(Supplier.id).where(
                    Supplier.id == input.supplier_id, Supplier.tenant_id == self.ctx.tenant_id
                )
            )
        ).scalar_one_or_none()
        if supplier is None:
            raise ValidationFailedError(f"unknown supplier_id {input.supplier_id}")

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

    async def summarize(self, input: CreatePoInput) -> str:
        return f"Create draft PO for supplier {input.supplier_id} ({len(input.lines)} lines)"

    async def apply(self, input: CreatePoInput) -> tuple[CreatePoResult, list[OutboxEventDraft]]:
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

        order = PurchaseOrder(
            tenant_id=self.ctx.tenant_id,
            supplier_id=input.supplier_id,
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
                PurchaseOrderLine(
                    tenant_id=self.ctx.tenant_id,
                    purchase_order_id=order.id,
                    product_id=product.id,
                    description=product.name,
                    quantity=line_input.quantity,
                    unit_price_amount=unit_price_minor,
                    line_total_amount=line_total_minor,
                )
            )

        order.total_amount = total_minor
        await self.session.flush()

        result = CreatePoResult(
            purchase_order_id=order.id,
            status=order.status,
            total_amount=from_minor_units(total_minor),
        )
        event = OutboxEventDraft(
            event_type="purchasing.po_created.v1",
            payload={"purchase_order_id": str(order.id), "supplier_id": str(input.supplier_id)},
        )
        return result, [event]
