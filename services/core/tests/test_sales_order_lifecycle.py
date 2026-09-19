import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.commands.base import CommandContext, ValidationFailedError
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.inventory.commands.adjust_stock import AdjustStock, AdjustStockInput
from app.modules.inventory.commands.create_location import CreateLocation, CreateLocationInput
from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from app.modules.sales.commands.cancel_order import CancelOrder, CancelOrderInput
from app.modules.sales.commands.confirm_order import ConfirmOrder, ConfirmOrderInput
from app.modules.sales.commands.create_order import (
    CreateOrder,
    CreateOrderInput,
    CreateOrderLineInput,
)
from app.modules.sales.commands.deliver_order import DeliverOrder, DeliverOrderInput
from app.modules.sales.queries.list_orders import ListOrdersFilters, list_orders


async def _propose_and_commit(command_cls, ctx, session, input_, idempotency_key):
    proposal = await command_cls(ctx, session).execute(
        input_, idempotency_key=idempotency_key, mode="propose"
    )
    return await command_cls(ctx, session).execute(
        input_, idempotency_key=idempotency_key, mode="commit", confirm_token=proposal.confirm_token
    )


async def _setup_customer_product_stock(
    session, tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    ctx = CommandContext(tenant_id=tenant_id, actor="test")
    customer = await CreateCustomer(ctx, session).execute(
        CreateCustomerInput(name="Trattoria Roma"), idempotency_key=str(uuid.uuid4())
    )
    product = await CreateProduct(ctx, session).execute(
        CreateProductInput(
            sku="BASIL-001", name="Fresh Basil", unit="bunch", base_price=Decimal("2.95")
        ),
        idempotency_key=str(uuid.uuid4()),
    )
    location = await CreateLocation(ctx, session).execute(
        CreateLocationInput(code="MAIN", name="Main Warehouse"), idempotency_key=str(uuid.uuid4())
    )
    await _propose_and_commit(
        AdjustStock,
        ctx,
        session,
        AdjustStockInput(
            product_id=product.product_id,
            location_id=location.location_id,
            quantity_delta=Decimal("100"),
            reason_note="initial stock",
        ),
        str(uuid.uuid4()),
    )
    return customer.customer_id, product.product_id


@pytest.mark.asyncio
async def test_order_lifecycle_create_confirm_deliver(tenant_a: uuid.UUID) -> None:
    async with tenant_session(tenant_a) as session:
        customer_id, product_id = await _setup_customer_product_stock(session, tenant_a)

    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    create_input = CreateOrderInput(
        customer_id=customer_id,
        order_date=date.today(),
        lines=[CreateOrderLineInput(product_id=product_id, quantity=Decimal("10"))],
    )
    async with tenant_session(tenant_a) as session:
        created = await CreateOrder(ctx, session).execute(
            create_input, idempotency_key=str(uuid.uuid4())
        )
        assert created.status == "draft"
        assert created.total_amount == Decimal("29.50")

    confirm_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        confirmed = await _propose_and_commit(
            ConfirmOrder,
            ctx,
            session,
            ConfirmOrderInput(sales_order_id=created.sales_order_id),
            confirm_key,
        )
        assert confirmed.status == "confirmed"

    deliver_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        delivered = await _propose_and_commit(
            DeliverOrder,
            ctx,
            session,
            DeliverOrderInput(sales_order_id=created.sales_order_id),
            deliver_key,
        )
        assert delivered.status == "delivered"

    async with tenant_session(tenant_a) as session:
        result = await list_orders(
            session, tenant_a, ListOrdersFilters(status=["delivered"], search="Trattoria")
        )
        assert result.total == 1
        assert result.items[0].id == created.sales_order_id
        assert result.items[0].line_count == 1


@pytest.mark.asyncio
async def test_deliver_order_blocked_without_enough_stock(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        customer = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="No Stock Cafe"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="MINT-002", name="Mint", unit="bunch", base_price=Decimal("1.00")
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        created = await CreateOrder(ctx, session).execute(
            CreateOrderInput(
                customer_id=customer.customer_id,
                order_date=date.today(),
                lines=[CreateOrderLineInput(product_id=product.product_id, quantity=Decimal("5"))],
            ),
            idempotency_key=str(uuid.uuid4()),
        )

    confirm_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        await _propose_and_commit(
            ConfirmOrder,
            ctx,
            session,
            ConfirmOrderInput(sales_order_id=created.sales_order_id),
            confirm_key,
        )

    deliver_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        with pytest.raises(ValidationFailedError):
            await _propose_and_commit(
                DeliverOrder,
                ctx,
                session,
                DeliverOrderInput(sales_order_id=created.sales_order_id),
                deliver_key,
            )


@pytest.mark.asyncio
async def test_cancel_order_from_draft(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        customer = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="Cancel Test Co"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(sku="KALE-001", name="Kale", unit="kg", base_price=Decimal("3.00")),
            idempotency_key=str(uuid.uuid4()),
        )
        created = await CreateOrder(ctx, session).execute(
            CreateOrderInput(
                customer_id=customer.customer_id,
                order_date=date.today(),
                lines=[CreateOrderLineInput(product_id=product.product_id, quantity=Decimal("2"))],
            ),
            idempotency_key=str(uuid.uuid4()),
        )

    cancel_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        cancelled = await _propose_and_commit(
            CancelOrder,
            ctx,
            session,
            CancelOrderInput(sales_order_id=created.sales_order_id),
            cancel_key,
        )
        assert cancelled.status == "cancelled"
