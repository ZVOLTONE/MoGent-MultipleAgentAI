import { ExternalLink } from "lucide-react";
import type { NewsItem } from "@/types";

export function NewsList({ items }: { items: NewsItem[] }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-2.5">
      {items.map((it, i) => (
        <li
          key={i}
          className="rounded-xl border border-black/[0.06] bg-white/50 p-3 backdrop-blur-sm transition-all hover:bg-white/80 hover:border-black/15"
        >
          <a
            href={it.url || "#"}
            target="_blank"
            rel="noreferrer"
            className="group flex items-start gap-2 text-[var(--color-ink)]"
          >
            <span className="flex-1 text-sm font-medium leading-snug group-hover:underline">
              {it.title}
            </span>
            {it.url && (
              <ExternalLink
                size={13}
                className="mt-0.5 shrink-0 text-black/40 group-hover:text-black"
                aria-hidden="true"
              />
            )}
          </a>
          <div className="mt-1.5 flex items-center gap-1.5 text-[11px] font-mono text-[var(--color-ink-faint)]">
            {[it.source, it.date].filter(Boolean).map((part, pIdx) => (
              <span key={pIdx}>
                {pIdx > 0 && <span className="mr-1.5">·</span>}
                {part}
              </span>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
