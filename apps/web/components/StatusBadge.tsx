import type { OrderStatus } from "@/lib/types";

// Status colors are reserved and never reused for anything else; each badge ships
// with a label (color is never the only signal), per the status-palette convention.
const STYLES: Record<OrderStatus, { bg: string; text: string; dot: string }> = {
  draft: { bg: "bg-slate-dim", text: "text-slate-text", dot: "bg-slate" },
  confirmed: { bg: "bg-amber-dim", text: "text-amber-text", dot: "bg-amber" },
  delivered: { bg: "bg-crop-dim", text: "text-crop-text", dot: "bg-crop" },
  received: { bg: "bg-crop-dim", text: "text-crop-text", dot: "bg-crop" },
  cancelled: { bg: "bg-rust-dim", text: "text-rust-text", dot: "bg-rust" },
};

export function StatusBadge({ status }: { status: OrderStatus }) {
  const style = STYLES[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-mono uppercase tracking-wide ${style.bg} ${style.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} aria-hidden />
      {status}
    </span>
  );
}
