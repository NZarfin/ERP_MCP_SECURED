import uuid
from decimal import Decimal

import pytest
from app.commands.base import CommandContext, ProposalRequiredError
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.inventory.commands.adjust_stock import AdjustStock, AdjustStockInput
from app.modules.inventory.commands.create_location import CreateLocation, CreateLocationInput
from app.modules.inventory.service import get_stock_balance


async def _make_product_and_location(session, tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    ctx = CommandContext(tenant_id=tenant_id, actor="test")
    product = await CreateProduct(ctx, session).execute(
        CreateProductInput(
            sku="MINT-001", name="Fresh Mint", unit="bunch", base_price=Decimal("1.50")
        ),
        idempotency_key=str(uuid.uuid4()),
    )
    location = await CreateLocation(ctx, session).execute(
        CreateLocationInput(code="MAIN", name="Main Warehouse"), idempotency_key=str(uuid.uuid4())
    )
    return product.product_id, location.location_id


@pytest.mark.asyncio
async def test_adjust_stock_requires_confirm_token_and_updates_balance(
    tenant_a: uuid.UUID,
) -> None:
    async with tenant_session(tenant_a) as session:
        product_id, location_id = await _make_product_and_location(session, tenant_a)

    idempotency_key = str(uuid.uuid4())
    adjust_input = AdjustStockInput(
        product_id=product_id,
        location_id=location_id,
        quantity_delta=Decimal("-3.5"),
        reason_note="spoilage write-off",
    )

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test")
        with pytest.raises(ProposalRequiredError):
            await AdjustStock(ctx, session).execute(adjust_input, idempotency_key=idempotency_key)

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test")
        proposal = await AdjustStock(ctx, session).execute(
            adjust_input, idempotency_key=idempotency_key, mode="propose"
        )

    async with tenant_session(tenant_a) as session:
        ctx = CommandContext(tenant_id=tenant_a, actor="test")
        await AdjustStock(ctx, session).execute(
            adjust_input,
            idempotency_key=idempotency_key,
            mode="commit",
            confirm_token=proposal.confirm_token,
        )

    async with tenant_session(tenant_a) as session:
        balance = await get_stock_balance(session, tenant_a, product_id)
        assert balance == Decimal("-3.500")
