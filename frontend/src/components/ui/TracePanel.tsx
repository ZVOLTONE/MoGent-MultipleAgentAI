import type { Card, NewsItem } from "@/types";
import { Bullets } from "./Bullets";

/** Sources & limitations card with minimalist monochrome glass styling */
export function TracePanel({ card }: { card: Card }) {
  const failed = (card.items as NewsItem[]) || [];
  return (
    <div className="space-y-4">
      <Bullets items={card.bullets || []} />
      {failed.length > 0 && (
        <div className="rounded-xl border border-black/[0.06] bg-white/50 p-3.5 backdrop-blur-sm">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">
            Tool yang belum berhasil
          </div>
          <ul className="space-y-1.5">
            {failed.map((t, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 rounded-lg border border-black/[0.06] bg-white/70 px-3 py-2 text-xs"
              >
                <span className="font-mono text-[var(--color-ink)]">{t.title}</span>
                <span className="font-medium text-[var(--color-bad)]">
                  ✗ {t.date || t.source}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
