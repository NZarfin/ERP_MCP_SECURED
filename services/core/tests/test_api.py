"""End-to-end HTTP test of the REST API (app/api/*): proves the routers, the
tenancy header dependency and the command/query layers work together, not just each
piece in isolation. Uses an in-process ASGI transport -- no separate server needed.
"""

import uuid
from decimal import Decimal

import pytest
from app.commands.base import CommandContext
from app.db.session import tenant_session
from app.main import app
from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_sales_orders_endpoint_filters_by_status_and_search(tenant_a: uuid.UUID) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        customer = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="API Test Bistro"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="API-001", name="Coriander", unit="bunch", base_price=Decimal("1.20")
            ),
            idempotency_key=str(uuid.uuid4()),
        )

    headers = {"X-Tenant-Id": str(tenant_a)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/sales/orders",
            headers=headers,
            json={
                "customer_id": str(customer.customer_id),
                "order_date": "2026-01-15",
                "lines": [{"product_id": str(product.product_id), "quantity": "3"}],
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        assert create_resp.json()["status"] == "draft"

        list_resp = await client.get(
            "/api/sales/orders",
            headers=headers,
            params={"status": "draft", "search": "API Test"},
        )
        assert list_resp.status_code == 200, list_resp.text
        body = list_resp.json()
        assert body["total"] == 1
        assert body["items"][0]["customer_name"] == "API Test Bistro"

        no_match_resp = await client.get(
            "/api/sales/orders", headers=headers, params={"search": "Nonexistent Customer"}
        )
        assert no_match_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_missing_tenant_header_is_rejected() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sales/orders")
        assert resp.status_code == 422  # FastAPI: required header missing


@pytest.mark.asyncio
async def test_cross_tenant_orders_are_invisible_via_api(
    tenant_a: uuid.UUID, tenant_b: uuid.UUID
) -> None:
    ctx = CommandContext(tenant_id=tenant_a, actor="test")
    async with tenant_session(tenant_a) as session:
        customer = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="Tenant A Only"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="API-002", name="Dill", unit="bunch", base_price=Decimal("1.10")
            ),
            idempotency_key=str(uuid.uuid4()),
        )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/sales/orders",
            headers={"X-Tenant-Id": str(tenant_a)},
            json={
                "customer_id": str(customer.customer_id),
                "order_date": "2026-01-15",
                "lines": [{"product_id": str(product.product_id), "quantity": "1"}],
            },
        )

        as_tenant_b = await client.get("/api/sales/orders", headers={"X-Tenant-Id": str(tenant_b)})
        assert as_tenant_b.json()["total"] == 0
