import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.commands.base import CommandContext, ValidationFailedError
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.custom.commands.define_field import DefineField, DefineFieldInput
from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from app.modules.sales.commands.create_order import (
    CreateOrder,
    CreateOrderInput,
    CreateOrderLineInput,
)


async def _setup_customer_and_product(session, tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    ctx = CommandContext(tenant_id=tenant_id, actor="test")
    customer = await CreateCustomer(ctx, session).execute(
        CreateCustomerInput(name="Custom Field Co"), idempotency_key=str(uuid.uuid4())
    )
    product = await CreateProduct(ctx, session).execute(
        CreateProductInput(
            sku="MICRO-001", name="Microgreens Mix", unit="tray", base_price=Decimal("4.50")
        ),
        idempotency_key=str(uuid.uuid4()),
    )
    return customer.customer_id, product.product_id


@pytest.mark.asyncio
async def test_define_field_and_write_valid_custom_value(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        await DefineField(ctx, session).execute(
            DefineFieldInput(
                entity="sales_order",
                key="harvest_region",
                label="Harvest region",
                field_type="select",
                validation={"options": ["Westland", "Venlo", "Imported"]},
                required=False,
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        customer_id, product_id = await _setup_customer_and_product(session, tenant_a)

    async with tenant_session(tenant_a) as session:
        result = await CreateOrder(ctx, session).execute(
            CreateOrderInput(
                customer_id=customer_id,
                order_date=date.today(),
                lines=[CreateOrderLineInput(product_id=product_id, quantity=Decimal("1"))],
                custom={"harvest_region": "Westland"},
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        assert result.status == "draft"


@pytest.mark.asyncio
async def test_custom_field_rejects_value_outside_options(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        await DefineField(ctx, session).execute(
            DefineFieldInput(
                entity="sales_order",
                key="harvest_region",
                label="Harvest region",
                field_type="select",
                validation={"options": ["Westland", "Venlo"]},
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        customer_id, product_id = await _setup_customer_and_product(session, tenant_a)

    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await CreateOrder(ctx, session).execute(
                CreateOrderInput(
                    customer_id=customer_id,
                    order_date=date.today(),
                    lines=[CreateOrderLineInput(product_id=product_id, quantity=Decimal("1"))],
                    custom={"harvest_region": "Mars"},
                ),
                idempotency_key=str(uuid.uuid4()),
            )


@pytest.mark.asyncio
async def test_custom_field_rejects_undefined_key(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        customer_id, product_id = await _setup_customer_and_product(session, tenant_a)

    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await CreateOrder(ctx, session).execute(
                CreateOrderInput(
                    customer_id=customer_id,
                    order_date=date.today(),
                    lines=[CreateOrderLineInput(product_id=product_id, quantity=Decimal("1"))],
                    custom={"not_a_real_field": "value"},
                ),
                idempotency_key=str(uuid.uuid4()),
            )


@pytest.mark.asyncio
async def test_define_field_rejects_duplicate_key(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    field_input = DefineFieldInput(
        entity="sales_order", key="cold_chain", label="Cold chain required", field_type="boolean"
    )
    async with tenant_session(tenant_a) as session:
        await DefineField(ctx, session).execute(field_input, idempotency_key=str(uuid.uuid4()))

    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await DefineField(ctx, session).execute(field_input, idempotency_key=str(uuid.uuid4()))
