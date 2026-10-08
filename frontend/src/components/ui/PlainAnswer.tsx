import type { QueryResult } from "@/types";

/** Plain text answer (Mode Kartu OFF, PRD 11 PlainAnswer). Minimal monochrome glass style. */
export function PlainAnswer({ result }: { result: QueryResult }) {
  const lines = (result.answer || "").split("\n");
  return (
    <article className="glass-card animate-fade-up mx-auto max-w-2xl rounded-[var(--radius-card)] p-7">
      {result.ticker && (
        <div className="mb-3 inline-block rounded-md border border-black/10 bg-black/[0.03] px-2.5 py-0.5 font-mono text-xs font-semibold tracking-wide text-black">
          {result.ticker}
        </div>
      )}
      <div className="space-y-2.5 text-[15px] leading-relaxed text-[var(--color-ink)]">
        {lines.map((ln, i) => {
          const t = ln.trim();
          if (!t) return <div key={i} className="h-1.5" />;
          if (t.startsWith("## "))
            return (
              <h3 key={i} className="pt-2 text-base font-semibold tracking-tight text-black">
                {t.slice(3)}
              </h3>
            );
          if (/^\d+\.\s/.test(t) || t.startsWith("- "))
            return (
              <p key={i} className="pl-3 text-[var(--color-ink-soft)]">
                {t}
              </p>
            );
          return (
            <p key={i} className="text-[var(--color-ink-soft)]">
              {t}
            </p>
          );
        })}
      </div>
      {Array.isArray(result.limitations) && result.limitations.length > 0 && (
        <div className="mt-5 border-t border-black/[0.07] pt-3.5 text-xs text-[var(--color-ink-faint)]">
          <span className="font-semibold text-[var(--color-ink-soft)]">Keterbatasan data:</span>{" "}
          {(result.limitations as string[]).join("; ")}
        </div>
      )}
    </article>
  );
}
