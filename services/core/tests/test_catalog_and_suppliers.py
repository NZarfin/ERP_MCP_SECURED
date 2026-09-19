import uuid
from decimal import Decimal

import pytest
from app.commands.base import CommandContext
from app.core.money import from_minor_units, to_minor_units
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.catalog.models.product import Product
from app.modules.parties.commands.create_supplier import CreateSupplier, CreateSupplierInput
from app.modules.parties.models.supplier import Supplier
from sqlalchemy import select


def test_money_round_trips_through_minor_units() -> None:
    assert from_minor_units(to_minor_units(Decimal("12.50"))) == Decimal("12.50")
    assert to_minor_units(Decimal("12.505")) == 1251  # ROUND_HALF_UP
    assert to_minor_units(Decimal("0.00")) == 0


@pytest.mark.asyncio
async def test_create_supplier(tenant_a: uuid.UUID) -> None:
    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test")
        result = await CreateSupplier(ctx, session).execute(
            CreateSupplierInput(name="Green Valley Farms"), idempotency_key=str(uuid.uuid4())
        )

    async with tenant_session(tenant_a) as session:
        supplier = (
            await session.execute(select(Supplier).where(Supplier.id == result.supplier_id))
        ).scalar_one()
        assert supplier.name == "Green Valley Farms"


@pytest.mark.asyncio
async def test_create_product_stores_price_as_minor_units(tenant_a: uuid.UUID) -> None:
    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test")
        result = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="BASIL-001", name="Fresh Basil", unit="bunch", base_price=Decimal("2.95")
            ),
            idempotency_key=str(uuid.uuid4()),
        )

    async with tenant_session(tenant_a) as session:
        product = (
            await session.execute(select(Product).where(Product.id == result.product_id))
        ).scalar_one()
        assert product.base_price_amount == 295
        assert from_minor_units(product.base_price_amount) == Decimal("2.95")
