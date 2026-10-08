import { useState } from "react";
import { Info } from "lucide-react";
import type { CardFact } from "@/types";

function Fact({ fact }: { fact: CardFact }) {
  const [open, setOpen] = useState(false);
  const hasEvidence = Boolean(fact.evidence_id || fact.source);
  return (
    <div className="rounded-xl border border-black/[0.07] bg-white/60 p-3.5 backdrop-blur-md transition-all hover:border-black/15 hover:bg-white/85 hover:shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <span className="text-[12px] font-medium leading-tight text-[var(--color-ink-soft)]">
          {fact.label}
        </span>
        {hasEvidence && (
          <button
            type="button"
            aria-label={`Sumber ${fact.label}`}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="shrink-0 rounded-md p-1 text-[var(--color-ink-faint)] transition-colors hover:bg-black/5 hover:text-black focus-visible:outline-2 focus-visible:outline-black"
          >
            <Info size={13} aria-hidden="true" />
          </button>
        )}
      </div>
      <div className="mt-1.5 text-xl font-semibold tabular-nums tracking-tight text-[var(--color-ink)]">
        {fact.value}
      </div>
      <div className="mt-1 text-[11px] font-mono text-[var(--color-ink-faint)]">
        {fact.as_of || "tanggal tidak tercantum"}
      </div>
      {open && hasEvidence && (
        <dl className="mt-2.5 space-y-1 rounded-lg border border-black/[0.06] bg-black/[0.02] p-2.5 text-[11px] text-[var(--color-ink-soft)]">
          <div className="flex justify-between gap-2">
            <dt className="text-[var(--color-ink-faint)]">Sumber</dt>
            <dd className="text-right font-medium text-[var(--color-ink)]">{fact.source || "—"}</dd>
          </div>
          {fact.evidence_id && (
            <div className="flex justify-between gap-2">
              <dt className="text-[var(--color-ink-faint)]">Bukti</dt>
              <dd className="font-mono text-[10px] text-[var(--color-ink)]">{fact.evidence_id}</dd>
            </div>
          )}
          {fact.derived && fact.formula && (
            <div className="flex justify-between gap-2">
              <dt className="text-[var(--color-ink-faint)]">Rumus (ƒ)</dt>
              <dd className="text-right font-mono text-[10px] text-[var(--color-ink)]">{fact.formula}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}

export function FactGrid({ facts }: { facts: CardFact[] }) {
  if (!facts?.length) return null;
  return (
    <div className="grid grid-cols-2 gap-2.5">
      {facts.map((f, i) => (
        <Fact key={`${f.label}-${i}`} fact={f} />
      ))}
    </div>
  );
}
