export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (next: number) => void;
}) {
  if (total === 0) return null;

  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const from = offset + 1;
  const to = Math.min(offset + limit, total);

  return (
    <div className="flex items-center justify-between mt-3 text-[12px] font-mono text-paper-muted">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          className="px-2.5 py-1 border border-ink-border rounded-sm uppercase tracking-wide transition-colors hover:border-crop hover:text-crop-text disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-ink-border disabled:hover:text-paper-muted"
        >
          Prev
        </button>
        <span>
          {page} / {pageCount}
        </span>
        <button
          type="button"
          disabled={page >= pageCount}
          onClick={() => onOffsetChange(offset + limit)}
          className="px-2.5 py-1 border border-ink-border rounded-sm uppercase tracking-wide transition-colors hover:border-crop hover:text-crop-text disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-ink-border disabled:hover:text-paper-muted"
        >
          Next
        </button>
      </div>
    </div>
  );
}
