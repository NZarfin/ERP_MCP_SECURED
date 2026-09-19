"use client";

import { useEffect, useState } from "react";
import { fetchSalesOrders } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { DEFAULT_FILTERS, type ListResult, type OrderFilters, type SalesOrderSummary } from "@/lib/types";
import { FilterBar } from "@/components/FilterBar";
import { OrdersTable, type OrderRow } from "@/components/OrdersTable";
import { Pagination } from "@/components/Pagination";
import { StatTile } from "@/components/StatTile";

const STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "confirmed", label: "Confirmed" },
  { value: "delivered", label: "Delivered" },
  { value: "cancelled", label: "Cancelled" },
];

export default function SalesPage() {
  const [filters, setFilters] = useState<OrderFilters>(DEFAULT_FILTERS);
  const [result, setResult] = useState<ListResult<SalesOrderSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const handle = setTimeout(() => {
      fetchSalesOrders(filters)
        .then((r) => {
          if (!cancelled) {
            setResult(r);
            setError(null);
          }
        })
        .catch((e: Error) => !cancelled && setError(e.message))
        .finally(() => !cancelled && setLoading(false));
    }, 200); // light debounce so typing in search doesn't fire a request per keystroke
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [filters]);

  const rows: OrderRow[] =
    result?.items.map((o) => ({
      id: o.id,
      counterparty: o.customer_name,
      status: o.status,
      order_date: o.order_date,
      currency: o.currency,
      total_amount: o.total_amount,
      line_count: o.line_count,
    })) ?? [];

  const currency = result?.items[0]?.currency ?? "EUR";
  const openCount = result
    ? result.items.filter((o) => o.status === "draft" || o.status === "confirmed").length
    : 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-4xl font-display font-semibold text-paper-primary">Sales</h1>
        <p className="text-paper-secondary mt-1">
          Every quote and order in one ledger. Filter by status, date, counterparty or value.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <StatTile label="Matching orders" value={result ? String(result.total) : "—"} />
        <StatTile
          label="Total value"
          value={result ? formatMoney(result.total_value, currency) : "—"}
          accent
        />
        <StatTile
          label="Avg. order value"
          value={
            result && result.total > 0
              ? formatMoney(String(Number(result.total_value) / result.total), currency)
              : "—"
          }
        />
        <StatTile label="Open on this page" value={String(openCount)} />
      </div>

      <FilterBar
        filters={filters}
        onChange={setFilters}
        statusOptions={STATUS_OPTIONS}
        searchPlaceholder="Search customer…"
      />

      {error ? (
        <div className="border border-rust rounded-sm bg-rust-dim text-rust-text px-4 py-3 text-sm">
          Could not reach the API: {error}
        </div>
      ) : (
        <>
          <OrdersTable rows={rows} counterpartyLabel="Customer" loading={loading} />
          {result ? (
            <Pagination
              total={result.total}
              limit={filters.limit}
              offset={filters.offset}
              onOffsetChange={(offset) => setFilters((f) => ({ ...f, offset }))}
            />
          ) : null}
        </>
      )}
    </div>
  );
}
