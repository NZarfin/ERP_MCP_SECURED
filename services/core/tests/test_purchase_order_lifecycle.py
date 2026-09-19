import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.commands.base import CommandContext
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.inventory.commands.create_location import CreateLocation, CreateLocationInput
from app.modules.inventory.service import get_stock_balance
from app.modules.parties.commands.create_supplier import CreateSupplier, CreateSupplierInput
from app.modules.purchasing.commands.cancel_po import CancelPo, CancelPoInput
from app.modules.purchasing.commands.confirm_po import ConfirmPo, ConfirmPoInput
from app.modules.purchasing.commands.create_po import CreatePo, CreatePoInput, CreatePoLineInput
from app.modules.purchasing.commands.receive_po import ReceivePo, ReceivePoInput
from app.modules.purchasing.queries.list_pos import ListPosFilters, list_pos


async def _propose_and_commit(command_cls, ctx, session, input_, idempotency_key):
    proposal = await command_cls(ctx, session).execute(
        input_, idempotency_key=idempotency_key, mode="propose"
    )
    return await command_cls(ctx, session).execute(
        input_, idempotency_key=idempotency_key, mode="commit", confirm_token=proposal.confirm_token
    )


@pytest.mark.asyncio
async def test_po_lifecycle_create_confirm_receive_updates_stock(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        supplier = await CreateSupplier(ctx, session).execute(
            CreateSupplierInput(name="Green Valley Farms"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="THYME-001", name="Thyme", unit="kg", base_price=Decimal("6.00")
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        await CreateLocation(ctx, session).execute(
            CreateLocationInput(code="MAIN", name="Main Warehouse"),
            idempotency_key=str(uuid.uuid4()),
        )
        created = await CreatePo(ctx, session).execute(
            CreatePoInput(
                supplier_id=supplier.supplier_id,
                order_date=date.today(),
                lines=[CreatePoLineInput(product_id=product.product_id, quantity=Decimal("20"))],
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        assert created.status == "draft"
        assert created.total_amount == Decimal("120.00")

    confirm_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        confirmed = await _propose_and_commit(
            ConfirmPo,
            ctx,
            session,
            ConfirmPoInput(purchase_order_id=created.purchase_order_id),
            confirm_key,
        )
        assert confirmed.status == "confirmed"

    receive_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        received = await _propose_and_commit(
            ReceivePo,
            ctx,
            session,
            ReceivePoInput(purchase_order_id=created.purchase_order_id, lot_code="LOT-001"),
            receive_key,
        )
        assert received.status == "received"

    async with tenant_session(tenant_a) as session:
        balance = await get_stock_balance(session, tenant_a, product.product_id)
        assert balance == Decimal("20.000")

        result = await list_pos(
            session, tenant_a, ListPosFilters(status=["received"], search="Green Valley")
        )
        assert result.total == 1
        assert result.items[0].id == created.purchase_order_id


@pytest.mark.asyncio
async def test_cancel_po_from_draft(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        supplier = await CreateSupplier(ctx, session).execute(
            CreateSupplierInput(name="Cancel PO Farms"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="ROSE-001", name="Rosemary", unit="kg", base_price=Decimal("5.00")
            ),
            idempotency_key=str(uuid.uuid4()),
        )
        created = await CreatePo(ctx, session).execute(
            CreatePoInput(
                supplier_id=supplier.supplier_id,
                order_date=date.today(),
                lines=[CreatePoLineInput(product_id=product.product_id, quantity=Decimal("5"))],
            ),
            idempotency_key=str(uuid.uuid4()),
        )

    cancel_key = str(uuid.uuid4())
    async with tenant_session(tenant_a) as session:
        cancelled = await _propose_and_commit(
            CancelPo,
            ctx,
            session,
            CancelPoInput(purchase_order_id=created.purchase_order_id),
            cancel_key,
        )
        assert cancelled.status == "cancelled"
