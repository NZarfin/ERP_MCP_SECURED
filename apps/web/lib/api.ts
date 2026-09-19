import type { ListResult, OrderFilters, PurchaseOrderSummary, SalesOrderSummary } from "./types";

// Placeholder auth for Phase 1: a fixed X-Tenant-Id header, same as the REST API's
// own placeholder (app/api/deps.py). Real OAuth 2.1 sessions are Phase 2
// (docs/ROADMAP.md) -- this constant is the one place that changes when that lands.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const TENANT_ID =
  process.env.NEXT_PUBLIC_TENANT_ID ?? "00000000-0000-0000-0000-0000000000d0";

function buildParams(filters: OrderFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const status of filters.status) params.append("status", status);
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  if (filters.amountMin) params.set("amount_min", filters.amountMin);
  if (filters.amountMax) params.set("amount_max", filters.amountMax);
  if (filters.search) params.set("search", filters.search);
  params.set("sort", filters.sort);
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  return params;
}

async function get<T>(path: string, params: URLSearchParams): Promise<T> {
  const res = await fetch(`${API_URL}${path}?${params.toString()}`, {
    headers: { "X-Tenant-Id": TENANT_ID },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchSalesOrders(
  filters: OrderFilters,
): Promise<ListResult<SalesOrderSummary>> {
  return get<ListResult<SalesOrderSummary>>("/api/sales/orders", buildParams(filters));
}

export async function fetchPurchaseOrders(
  filters: OrderFilters,
): Promise<ListResult<PurchaseOrderSummary>> {
  return get<ListResult<PurchaseOrderSummary>>("/api/purchasing/pos", buildParams(filters));
}
