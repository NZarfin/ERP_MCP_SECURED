import { formatDate, formatMoney } from "@/lib/format";
import type { OrderStatus } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export interface OrderRow {
  id: string;
  counterparty: string;
  status: OrderStatus;
  order_date: string;
  currency: string;
  total_amount: string;
  line_count: number;
}

export function OrdersTable({
  rows,
  counterpartyLabel,
  loading,
}: {
  rows: OrderRow[];
  counterpartyLabel: string;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="border border-ink-border rounded-sm p-16 text-center text-paper-muted font-mono text-sm">
        Loading…
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="border border-ink-border rounded-sm p-16 text-center">
        <p className="text-paper-secondary font-display italic text-lg">No orders match.</p>
        <p className="text-paper-muted text-sm mt-1">Try widening a filter above.</p>
      </div>
    );
  }

  return (
    <div className="border border-ink-border rounded-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink-border bg-ink-raised text-left">
            <th className="px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-paper-muted font-medium">
              Date
            </th>
            <th className="px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-paper-muted font-medium">
              {counterpartyLabel}
            </th>
            <th className="px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-paper-muted font-medium">
              Status
            </th>
            <th className="px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-paper-muted font-medium text-right">
              Lines
            </th>
            <th className="px-4 py-2.5 font-mono text-[11px] uppercase tracking-wide text-paper-muted font-medium text-right">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.id}
              className="border-b border-ink-border last:border-b-0 hover:bg-ink-raised/60 transition-colors animate-rise-in"
              style={{ animationDelay: `${Math.min(i, 20) * 15}ms` }}
            >
              <td className="px-4 py-3 text-paper-secondary tabular-nums">
                {formatDate(row.order_date)}
              </td>
              <td className="px-4 py-3 text-paper-primary font-medium">{row.counterparty}</td>
              <td className="px-4 py-3">
                <StatusBadge status={row.status} />
              </td>
              <td className="px-4 py-3 text-right text-paper-secondary tabular-nums font-mono">
                {row.line_count}
              </td>
              <td className="px-4 py-3 text-right text-paper-primary tabular-nums font-mono font-medium">
                {formatMoney(row.total_amount, row.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
