"""Deterministic demo data: a fresh produce/herbs wholesaler, per docs/ROADMAP.md's
suggested first design partner. Fixed tenant id + fixed random seed, so re-running
against a freshly migrated database always reproduces the same dataset -- useful for
prototyping UI changes and for A/B-testing against a stable baseline.

Runs every write through the same commands the REST API and (eventually) the MCP
gateway use -- seeding doubles as a correctness exercise, not a side channel that
could drift from the real write path.

Known simplification: stock balance is a running total across ALL moves regardless
of date, so a delivery dated before its replenishing receipt can still succeed. Fine
for generating filterable demo data; not a claim that the ledger is temporally
accurate.

Run with: uv run python -m app.seed
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from faker import Faker

from app.commands.base import Command, CommandContext
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.custom.commands.define_field import DefineField, DefineFieldInput
from app.modules.gateway.commands.create_access_token import (
    VALID_SCOPES,
    CreateAccessToken,
    CreateAccessTokenInput,
    CreateAccessTokenResult,
)
from app.modules.gateway.commands.grant_entitlement import (
    VALID_SKUS,
    GrantEntitlement,
    GrantEntitlementInput,
)
from app.modules.inventory.commands.adjust_stock import AdjustStock, AdjustStockInput
from app.modules.inventory.commands.create_location import CreateLocation, CreateLocationInput
from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from app.modules.parties.commands.create_supplier import CreateSupplier, CreateSupplierInput
from app.modules.purchasing.commands.cancel_po import CancelPo, CancelPoInput
from app.modules.purchasing.commands.confirm_po import ConfirmPo, ConfirmPoInput
from app.modules.purchasing.commands.create_po import CreatePo, CreatePoInput, CreatePoLineInput
from app.modules.purchasing.commands.receive_po import ReceivePo, ReceivePoInput
from app.modules.sales.commands.cancel_order import CancelOrder, CancelOrderInput
from app.modules.sales.commands.confirm_order import ConfirmOrder, ConfirmOrderInput
from app.modules.sales.commands.create_order import (
    CreateOrder,
    CreateOrderInput,
    CreateOrderLineInput,
)
from app.modules.sales.commands.deliver_order import DeliverOrder, DeliverOrderInput

DEMO_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000d0")
SEED = 20260101

PRODUCTS: list[tuple[str, str, str, str]] = [
    # sku, name, unit, base_price (EUR)
    ("BASIL-001", "Fresh Basil", "bunch", "2.95"),
    ("BASIL-002", "Purple Basil", "bunch", "3.10"),
    ("THYME-001", "Thyme", "bunch", "2.50"),
    ("ROSE-001", "Rosemary", "bunch", "2.75"),
    ("MINT-001", "Mint", "bunch", "2.25"),
    ("OREG-001", "Oregano", "bunch", "2.40"),
    ("SAGE-001", "Sage", "bunch", "2.60"),
    ("DILL-001", "Dill", "bunch", "2.30"),
    ("CORI-001", "Coriander", "bunch", "2.20"),
    ("CHIV-001", "Chives", "bunch", "2.10"),
    ("PARS-001", "Flat-Leaf Parsley", "bunch", "1.95"),
    ("TARR-001", "Tarragon", "bunch", "3.20"),
    ("LOVA-001", "Lovage", "bunch", "2.80"),
    ("MICR-001", "Microgreens Mix", "tray", "6.50"),
    ("PEAS-001", "Pea Shoots", "tray", "5.75"),
    ("LETT-001", "Butterhead Lettuce", "kg", "3.10"),
    ("LETT-002", "Oakleaf Lettuce", "kg", "3.25"),
    ("LETT-003", "Romaine Lettuce", "kg", "2.95"),
    ("KALE-001", "Curly Kale", "kg", "3.40"),
    ("SPIN-001", "Baby Spinach", "kg", "4.10"),
    ("ROCK-001", "Wild Rocket", "kg", "5.20"),
    ("WATE-001", "Watercress", "bunch", "2.65"),
    ("FLOW-001", "Edible Flower Mix", "tray", "8.90"),
    ("TOMA-001", "Cherry Tomatoes", "kg", "4.75"),
    ("TOMA-002", "Heirloom Tomatoes", "kg", "6.20"),
    ("RADI-001", "Radish Bunch", "bunch", "1.85"),
    ("SPRO-001", "Spring Onion", "bunch", "1.60"),
    ("FENN-001", "Fennel Bulb", "kg", "3.55"),
    ("ENDI-001", "Belgian Endive", "kg", "4.00"),
    ("WASA-001", "Wasabi Rocket", "tray", "7.40"),
]

SUPPLIERS = [
    "Westland Kwekerij B.V.",
    "Polder Herbs Growers",
    "Green Valley Farms",
    "Kaskade Glasshouse Produce",
    "Zuiderzee Organic Farms",
    "Delta Fresh Herbs",
    "Noordwijk Bloom & Grow",
    "Bio Boerderij De Groene Hoek",
    "Rotterdam Harbor Produce Co.",
    "Flevoland Fields",
]

CUSTOMERS = [
    "Trattoria Roma",
    "Bistro Nord",
    "The Green Table",
    "Kade 12 Restaurant",
    "De Kleine Keuken",
    "Markthal Deli",
    "Foodhallen Kitchen",
    "Cafe Verdant",
    "Restaurant Basilic",
    "Zuiderdiep Grill",
    "Olive & Thyme Bistro",
    "The Herb Garden Cafe",
    "Rotterdam Rooftop Kitchen",
    "Brasserie Botanique",
    "De Frisse Oogst",
    "Stadstuin Restaurant",
    "Harvest Table Catering",
    "Groenten & Grill",
    "Kruidentuin Bistro",
    "Amsterdam Fresh Kitchen",
    "Delft Dining Co.",
    "Seasons Catering",
    "The Farm-to-Fork Co.",
    "Urban Greens Deli",
    "Willow & Basil",
]

HARVEST_REGIONS = ["Westland", "Venlo", "Zuid-Holland", "Imported"]


async def _commit(
    command_cls: type[Command[Any, Any]], ctx: CommandContext, session: Any, input_: Any
) -> Any:
    return await command_cls(ctx, session).execute(input_, idempotency_key=str(uuid.uuid4()))


async def _propose_and_commit(
    command_cls: type[Command[Any, Any]], ctx: CommandContext, session: Any, input_: Any
) -> Any:
    idempotency_key = str(uuid.uuid4())
    proposal = await command_cls(ctx, session).execute(
        input_, idempotency_key=idempotency_key, mode="propose"
    )
    return await command_cls(ctx, session).execute(
        input_, idempotency_key=idempotency_key, mode="commit", confirm_token=proposal.confirm_token
    )


def _random_date(rng: random.Random, days_back: int = 180) -> date:
    return date.today() - timedelta(days=rng.randint(0, days_back))


async def _seed_reference_data(
    ctx: CommandContext, rng: random.Random, fake: Faker
) -> tuple[uuid.UUID, list[uuid.UUID], list[uuid.UUID], list[uuid.UUID]]:
    """Location, supplier ids, customer ids, product ids. Also defines one custom
    field on sales_order (harvest_region) and seeds generous initial stock so later
    deliveries have something to draw down against.
    """
    async with tenant_session(ctx.tenant_id) as session:
        location = await _commit(
            CreateLocation, ctx, session, CreateLocationInput(code="MAIN", name="Main Warehouse")
        )

        await DefineField(ctx, session).execute(
            DefineFieldInput(
                entity="sales_order",
                key="harvest_region",
                label="Harvest region",
                field_type="select",
                validation={"options": HARVEST_REGIONS},
            ),
            idempotency_key=str(uuid.uuid4()),
        )

        supplier_ids = []
        for name in SUPPLIERS:
            supplier = await _commit(
                CreateSupplier,
                ctx,
                session,
                CreateSupplierInput(
                    name=name,
                    email=fake.company_email(),
                    vat_id=f"NL{rng.randint(100000000, 999999999)}B01",
                ),
            )
            supplier_ids.append(supplier.supplier_id)

        customer_ids = []
        for name in CUSTOMERS:
            customer = await _commit(
                CreateCustomer,
                ctx,
                session,
                CreateCustomerInput(name=name, email=fake.company_email()),
            )
            customer_ids.append(customer.customer_id)

        product_ids = []
        for sku, name, unit, price in PRODUCTS:
            product = await _commit(
                CreateProduct,
                ctx,
                session,
                CreateProductInput(sku=sku, name=name, unit=unit, base_price=Decimal(price)),
            )
            product_ids.append(product.product_id)

    # Initial stock take: generous headroom per product so demo deliveries never
    # starve for stock regardless of how the random order dates land.
    async with tenant_session(ctx.tenant_id) as session:
        for product_id in product_ids:
            await _propose_and_commit(
                AdjustStock,
                ctx,
                session,
                AdjustStockInput(
                    product_id=product_id,
                    location_id=location.location_id,
                    quantity_delta=Decimal(rng.randint(500, 2000)),
                    reason_note="initial stock take",
                ),
            )

    return location.location_id, supplier_ids, customer_ids, product_ids


async def _seed_purchase_orders(
    ctx: CommandContext,
    rng: random.Random,
    supplier_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> None:
    for _ in range(100):
        supplier_id = rng.choice(supplier_ids)
        lines = [
            CreatePoLineInput(product_id=pid, quantity=Decimal(rng.randint(10, 200)))
            for pid in rng.sample(product_ids, k=rng.randint(1, 4))
        ]
        async with tenant_session(ctx.tenant_id) as session:
            created = await _commit(
                CreatePo,
                ctx,
                session,
                CreatePoInput(supplier_id=supplier_id, order_date=_random_date(rng), lines=lines),
            )

        outcome = rng.choices(
            ["draft", "cancelled", "confirmed", "received"], weights=[15, 10, 25, 50]
        )[0]
        if outcome == "draft":
            continue
        async with tenant_session(ctx.tenant_id) as session:
            if outcome == "cancelled":
                await _propose_and_commit(
                    CancelPo,
                    ctx,
                    session,
                    CancelPoInput(purchase_order_id=created.purchase_order_id),
                )
                continue
            await _propose_and_commit(
                ConfirmPo, ctx, session, ConfirmPoInput(purchase_order_id=created.purchase_order_id)
            )
        if outcome == "confirmed":
            continue
        async with tenant_session(ctx.tenant_id) as session:
            await _propose_and_commit(
                ReceivePo,
                ctx,
                session,
                ReceivePoInput(
                    purchase_order_id=created.purchase_order_id,
                    lot_code=f"LOT-{rng.randint(1000, 9999)}",
                ),
            )


async def _seed_sales_orders(
    ctx: CommandContext,
    rng: random.Random,
    customer_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> None:
    for _ in range(200):
        customer_id = rng.choice(customer_ids)
        lines = [
            CreateOrderLineInput(product_id=pid, quantity=Decimal(rng.randint(1, 20)))
            for pid in rng.sample(product_ids, k=rng.randint(1, 5))
        ]
        custom = {"harvest_region": rng.choice(HARVEST_REGIONS)} if rng.random() < 0.4 else {}
        async with tenant_session(ctx.tenant_id) as session:
            created = await _commit(
                CreateOrder,
                ctx,
                session,
                CreateOrderInput(
                    customer_id=customer_id,
                    order_date=_random_date(rng),
                    lines=lines,
                    custom=custom,
                ),
            )

        outcome = rng.choices(
            ["draft", "cancelled", "confirmed", "delivered"], weights=[15, 10, 25, 50]
        )[0]
        if outcome == "draft":
            continue
        async with tenant_session(ctx.tenant_id) as session:
            if outcome == "cancelled":
                await _propose_and_commit(
                    CancelOrder,
                    ctx,
                    session,
                    CancelOrderInput(sales_order_id=created.sales_order_id),
                )
                continue
            await _propose_and_commit(
                ConfirmOrder, ctx, session, ConfirmOrderInput(sales_order_id=created.sales_order_id)
            )
        if outcome == "confirmed":
            continue
        async with tenant_session(ctx.tenant_id) as session:
            await _propose_and_commit(
                DeliverOrder, ctx, session, DeliverOrderInput(sales_order_id=created.sales_order_id)
            )


async def _seed_gateway_access(ctx: CommandContext) -> str:
    """Grants every core entitlement (all four domain modules) and issues one
    all-scopes access token for the demo tenant -- the token an MCP client
    (Claude Desktop, claude.ai) authenticates with. Returns the raw token.
    """
    async with tenant_session(ctx.tenant_id) as session:
        for sku in VALID_SKUS:
            await GrantEntitlement(ctx, session).execute(
                GrantEntitlementInput(sku=sku), idempotency_key=f"seed-entitlement-{sku}"
            )

    async with tenant_session(ctx.tenant_id) as session:
        result = await CreateAccessToken(ctx, session).execute(
            CreateAccessTokenInput(name="seed-demo-token", scopes=list(VALID_SCOPES)),
            idempotency_key="seed-demo-access-token",
        )
    assert isinstance(result, CreateAccessTokenResult)
    return result.token


async def main() -> None:
    rng = random.Random(SEED)
    fake = Faker("en_US")
    fake.seed_instance(SEED)
    ctx = CommandContext(tenant_id=DEMO_TENANT_ID, actor="seed-script")

    print(f"Seeding demo tenant {DEMO_TENANT_ID} ...")
    _, supplier_ids, customer_ids, product_ids = await _seed_reference_data(ctx, rng, fake)
    print(
        f"  {len(supplier_ids)} suppliers, {len(customer_ids)} customers, "
        f"{len(product_ids)} products"
    )

    await _seed_purchase_orders(ctx, rng, supplier_ids, product_ids)
    print("  100 purchase orders")

    await _seed_sales_orders(ctx, rng, customer_ids, product_ids)
    print("  200 sales orders")

    mcp_token = await _seed_gateway_access(ctx)
    print("  gateway entitlements granted (parties, catalog, sales, purchasing)")

    print("Done. X-Tenant-Id header for the API/web app:")
    print(f"  {DEMO_TENANT_ID}")
    if mcp_token == "***redacted***":
        print(
            "MCP access token: already issued on a previous seed run (idempotent retry "
            "never re-reveals a secret, per app/commands/base.py's redact_for_audit). "
            "Issue a new one via gateway.create_access_token if you need it again."
        )
    else:
        print("MCP bearer token (shown once -- save it):")
        print(f"  {mcp_token}")


if __name__ == "__main__":
    asyncio.run(main())
