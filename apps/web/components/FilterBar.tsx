import type { OrderFilters, SortField } from "@/lib/types";

interface StatusOption {
  value: string;
  label: string;
}

const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: "-order_date", label: "Newest first" },
  { value: "order_date", label: "Oldest first" },
  { value: "-total_amount", label: "Highest value" },
  { value: "total_amount", label: "Lowest value" },
];

export function FilterBar({
  filters,
  onChange,
  statusOptions,
  searchPlaceholder,
}: {
  filters: OrderFilters;
  onChange: (next: OrderFilters) => void;
  statusOptions: StatusOption[];
  searchPlaceholder: string;
}) {
  function toggleStatus(value: string) {
    const has = filters.status.includes(value);
    onChange({
      ...filters,
      status: has ? filters.status.filter((s) => s !== value) : [...filters.status, value],
      offset: 0,
    });
  }

  function patch(partial: Partial<OrderFilters>) {
    onChange({ ...filters, ...partial, offset: 0 });
  }

  const hasActiveFilters =
    filters.status.length > 0 ||
    filters.dateFrom ||
    filters.dateTo ||
    filters.amountMin ||
    filters.amountMax ||
    filters.search;

  return (
    <div className="border border-ink-border bg-ink-surface rounded-sm p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-1.5">
          {statusOptions.map((opt) => {
            const active = filters.status.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleStatus(opt.value)}
                className={`px-3 py-1.5 rounded-full text-[11px] font-mono uppercase tracking-wide border transition-colors ${
                  active
                    ? "bg-crop-dim border-crop text-crop-text"
                    : "border-ink-borderStrong text-paper-secondary hover:border-paper-muted hover:text-paper-primary"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        <input
          type="search"
          value={filters.search}
          onChange={(e) => patch({ search: e.target.value })}
          placeholder={searchPlaceholder}
          className="flex-1 min-w-[180px] bg-ink-raised border border-ink-border rounded-sm px-3 py-1.5 text-sm text-paper-primary placeholder:text-paper-muted focus:outline-none focus:border-crop"
        />

        <select
          value={filters.sort}
          onChange={(e) => patch({ sort: e.target.value as SortField })}
          className="bg-ink-raised border border-ink-border rounded-sm px-3 py-1.5 text-sm text-paper-secondary focus:outline-none focus:border-crop"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2 text-paper-secondary">
          Date
          <input
            type="date"
            value={filters.dateFrom}
            onChange={(e) => patch({ dateFrom: e.target.value })}
            className="bg-ink-raised border border-ink-border rounded-sm px-2 py-1 text-paper-primary focus:outline-none focus:border-crop"
          />
          <span className="text-paper-muted">to</span>
          <input
            type="date"
            value={filters.dateTo}
            onChange={(e) => patch({ dateTo: e.target.value })}
            className="bg-ink-raised border border-ink-border rounded-sm px-2 py-1 text-paper-primary focus:outline-none focus:border-crop"
          />
        </label>

        <label className="flex items-center gap-2 text-paper-secondary">
          Value
          <input
            type="number"
            inputMode="decimal"
            placeholder="min"
            value={filters.amountMin}
            onChange={(e) => patch({ amountMin: e.target.value })}
            className="w-20 bg-ink-raised border border-ink-border rounded-sm px-2 py-1 text-paper-primary placeholder:text-paper-muted focus:outline-none focus:border-crop"
          />
          <span className="text-paper-muted">to</span>
          <input
            type="number"
            inputMode="decimal"
            placeholder="max"
            value={filters.amountMax}
            onChange={(e) => patch({ amountMax: e.target.value })}
            className="w-20 bg-ink-raised border border-ink-border rounded-sm px-2 py-1 text-paper-primary placeholder:text-paper-muted focus:outline-none focus:border-crop"
          />
        </label>

        {hasActiveFilters ? (
          <button
            type="button"
            onClick={() =>
              onChange({
                ...filters,
                status: [],
                dateFrom: "",
                dateTo: "",
                amountMin: "",
                amountMax: "",
                search: "",
                offset: 0,
              })
            }
            className="ml-auto text-[11px] font-mono uppercase tracking-wide text-paper-muted hover:text-rust-text transition-colors"
          >
            Clear filters
          </button>
        ) : null}
      </div>
    </div>
  );
}
