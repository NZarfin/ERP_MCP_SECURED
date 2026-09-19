export function StatTile({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="border border-ink-border bg-ink-surface rounded-sm px-5 py-4 flex-1 min-w-[160px]">
      <div className="text-[11px] uppercase tracking-[0.15em] text-paper-muted font-mono mb-1.5">
        {label}
      </div>
      <div
        className={`text-3xl font-display tabular-nums ${accent ? "text-crop-text" : "text-paper-primary"}`}
      >
        {value}
      </div>
    </div>
  );
}
