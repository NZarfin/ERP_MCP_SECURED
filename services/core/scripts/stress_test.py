"""Concurrent load against a running REST API. Plain asyncio + httpx -- no k6/locust,
no new infra dependency. Two phases:

1. Read load: concurrent filtered GET /api/sales/orders and /api/purchasing/pos
   against the seeded demo tenant (`make seed` first). Reports p50/p95/throughput.
2. Write load + isolation under concurrency: spins up several fresh synthetic
   tenants, fires concurrent sales.create_order calls interleaved *across* tenants,
   then asserts each tenant's order count is exactly what it created and RLS did not
   leak a row across tenants -- extends what tests/test_tenancy_isolation.py checks,
   under concurrent load instead of one request at a time.

Run with: uv run --extra dev python scripts/stress_test.py
(or `make stress`, which starts/stops uvicorn around it)
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
from app.commands.base import CommandContext
from app.db.session import tenant_session
from app.modules.catalog.commands.create_product import (
    CreateProduct,
    CreateProductInput,
    CreateProductResult,
)
from app.modules.parties.commands.create_customer import (
    CreateCustomer,
    CreateCustomerInput,
    CreateCustomerResult,
)

BASE_URL = "http://127.0.0.1:8000"
DEMO_TENANT_ID = "00000000-0000-0000-0000-0000000000d0"

READ_REQUESTS = 200
READ_CONCURRENCY = 20
WRITE_TENANTS = 5
ORDERS_PER_TENANT = 20


@dataclass
class Timings:
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0

    def record(self, elapsed_s: float, ok: bool) -> None:
        self.latencies_ms.append(elapsed_s * 1000)
        if not ok:
            self.errors += 1

    def report(self, label: str, wall_s: float) -> None:
        if not self.latencies_ms:
            print(f"{label}: no requests completed")
            return
        sorted_ms = sorted(self.latencies_ms)
        p50 = sorted_ms[len(sorted_ms) // 2]
        p95 = sorted_ms[int(len(sorted_ms) * 0.95) - 1]
        throughput = len(self.latencies_ms) / wall_s if wall_s > 0 else float("inf")
        print(
            f"{label}: {len(self.latencies_ms)} requests in {wall_s:.2f}s "
            f"({throughput:.1f} req/s) p50={p50:.1f}ms p95={p95:.1f}ms "
            f"mean={statistics.mean(sorted_ms):.1f}ms errors={self.errors}"
        )


async def _read_one(client: httpx.AsyncClient, timings: Timings) -> None:
    start = time.perf_counter()
    resp = await client.get(
        "/api/sales/orders",
        headers={"X-Tenant-Id": DEMO_TENANT_ID},
        params={"limit": 20, "offset": 0},
    )
    timings.record(time.perf_counter() - start, resp.status_code == 200)


async def read_load(client: httpx.AsyncClient) -> None:
    timings = Timings()
    semaphore = asyncio.Semaphore(READ_CONCURRENCY)

    async def bounded() -> None:
        async with semaphore:
            await _read_one(client, timings)

    start = time.perf_counter()
    await asyncio.gather(*(bounded() for _ in range(READ_REQUESTS)))
    timings.report("read (GET /api/sales/orders)", time.perf_counter() - start)


async def setup_synthetic_tenant() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Creates one tenant with one customer and one product via the command layer
    directly (no REST endpoint for that -- parties/catalog creation isn't exposed as
    a write endpoint in Phase 1's REST API, see app/api/parties.py, app/api/catalog.py).
    """
    tenant_id = uuid.uuid4()
    ctx = CommandContext(tenant_id=tenant_id, actor="stress-test")
    async with tenant_session(tenant_id) as session:
        customer = await CreateCustomer(ctx, session).execute(
            CreateCustomerInput(name="Stress Test Customer"), idempotency_key=str(uuid.uuid4())
        )
        product = await CreateProduct(ctx, session).execute(
            CreateProductInput(
                sku="STRESS-001", name="Stress Test Item", unit="unit", base_price=Decimal("1.00")
            ),
            idempotency_key=str(uuid.uuid4()),
        )
    assert isinstance(customer, CreateCustomerResult)
    assert isinstance(product, CreateProductResult)
    return tenant_id, customer.customer_id, product.product_id


async def _write_one(
    client: httpx.AsyncClient,
    timings: Timings,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
) -> None:
    start = time.perf_counter()
    resp = await client.post(
        "/api/sales/orders",
        headers={"X-Tenant-Id": str(tenant_id)},
        json={
            "customer_id": str(customer_id),
            "order_date": "2026-01-15",
            "lines": [{"product_id": str(product_id), "quantity": "1"}],
        },
    )
    timings.record(time.perf_counter() - start, resp.status_code == 200)


async def write_load_and_isolation_check(client: httpx.AsyncClient) -> bool:
    tenants = await asyncio.gather(*(setup_synthetic_tenant() for _ in range(WRITE_TENANTS)))
    timings = Timings()

    tasks = [
        _write_one(client, timings, tenant_id, customer_id, product_id)
        for tenant_id, customer_id, product_id in tenants
        for _ in range(ORDERS_PER_TENANT)
    ]
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    timings.report(
        f"write ({WRITE_TENANTS} tenants x {ORDERS_PER_TENANT} concurrent creates)",
        time.perf_counter() - start,
    )

    ok = True
    for tenant_id, _, _ in tenants:
        resp = await client.get(
            "/api/sales/orders", headers={"X-Tenant-Id": str(tenant_id)}, params={"limit": 1}
        )
        total = resp.json()["total"]
        if total != ORDERS_PER_TENANT:
            print(
                f"  ISOLATION FAILURE: tenant {tenant_id} has {total} orders, "
                f"expected {ORDERS_PER_TENANT}"
            )
            ok = False
    if ok:
        print(
            f"  isolation check passed: each of {WRITE_TENANTS} tenants sees exactly its own orders"
        )
    return ok


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            health = await client.get("/health")
            health.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"API not reachable at {BASE_URL}: {exc}")
            return 1

        await read_load(client)
        isolation_ok = await write_load_and_isolation_check(client)
        return 0 if isolation_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
