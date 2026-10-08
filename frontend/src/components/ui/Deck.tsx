import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { CardsResponse } from "@/types";
import { Card } from "./Card";

interface Props {
  data: CardsResponse;
  /** true when the query input has focus — arrow keys must not move the deck (W-T19) */
  inputFocused: boolean;
}

export function Deck({ data, inputFocused }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const cards = data.cards;
  const total = cards.length;
  const fontScale = data.meta?.font_scale || 1;

  const scrollTo = useCallback((i: number) => {
    const track = trackRef.current;
    if (!track) return;
    const clamped = Math.max(0, Math.min(total - 1, i));
    const child = track.children[clamped] as HTMLElement | undefined;
    if (child) {
      track.scrollTo({
        left: child.offsetLeft - (track.clientWidth - child.clientWidth) / 2,
        behavior: "smooth",
      });
    }
  }, [total]);

  // Track which card is closest to center
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const center = track.scrollLeft + track.clientWidth / 2;
        let best = 0;
        let bestDist = Infinity;
        Array.from(track.children).forEach((c, i) => {
          const el = c as HTMLElement;
          const mid = el.offsetLeft + el.clientWidth / 2;
          const d = Math.abs(mid - center);
          if (d < bestDist) {
            bestDist = d;
            best = i;
          }
        });
        setActive(best);
      });
    };
    track.addEventListener("scroll", onScroll, { passive: true });
    return () => track.removeEventListener("scroll", onScroll);
  }, []);

  // Keyboard navigation (ignored while typing — PRD 11.2 / W-T19)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (inputFocused) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        scrollTo(active + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        scrollTo(active - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, inputFocused, scrollTo]);

  return (
    <section aria-label="Dek kartu analisis" className="relative w-full pb-28">
      {/* Top subtle meta indicator */}
      <div className="mb-3 flex items-center justify-between px-2 text-xs font-mono text-[var(--color-ink-faint)]">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-black/60" />
          <span>{data.meta?.agent || "Presentation Composer"}</span>
        </span>
        <span>{data.meta?.n_facts || total} fakta terverifikasi</span>
      </div>

      {/* Horizontal deck track with uncropped peek and center focus */}
      <div ref={trackRef} className="deck-track">
        {cards.map((c, i) => (
          <Card
            key={c.id}
            card={c}
            index={i}
            total={total}
            fontScale={fontScale}
            isActive={i === active}
            distanceFromCenter={Math.abs(i - active)}
            onClick={() => scrollTo(i)}
          />
        ))}
      </div>

      {/* Live region announces the active card to screen readers (PRD 11.2) */}
      <div aria-live="polite" className="sr-only">
        Kartu {active + 1} dari {total}: {cards[active]?.title}
      </div>

      {/* Floating Navigation Dock (User Request: dibuat floating supaya geser lebih mudah) */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
        <nav
          aria-label="Navigasi kartu mengambang"
          className="flex items-center gap-3 rounded-full border border-black/10 bg-white/85 px-3.5 py-2 backdrop-blur-2xl shadow-[0_16px_40px_-8px_rgba(0,0,0,0.18),0_2px_6px_rgba(0,0,0,0.06)] ring-1 ring-black/5 transition-all"
        >
          {/* Previous Button */}
          <button
            type="button"
            onClick={() => scrollTo(active - 1)}
            disabled={active === 0}
            aria-label="Kartu sebelumnya"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-black text-white shadow-sm transition-all hover:bg-black/85 hover:scale-105 active:scale-95 disabled:pointer-events-none disabled:opacity-20"
          >
            <ChevronLeft size={17} aria-hidden="true" />
          </button>

          {/* Card Counter Indicator */}
          <div className="flex items-center gap-1.5 px-2">
            <span className="font-mono text-xs font-bold tabular-nums text-black">
              {active + 1}
            </span>
            <span className="text-[10px] text-black/30">/</span>
            <span className="font-mono text-xs text-black/50 tabular-nums">
              {total}
            </span>
          </div>

          {/* Dots Indicator Tabs */}
          <div className="flex items-center gap-1.5 px-1" role="tablist" aria-label="Indikator kartu">
            {cards.map((c, i) => (
              <button
                key={c.id}
                type="button"
                role="tab"
                aria-selected={i === active}
                aria-label={`Ke kartu ${i + 1}: ${c.title}`}
                onClick={() => scrollTo(i)}
                className={
                  "h-2 rounded-full transition-all duration-300 " +
                  (i === active
                    ? "w-6 bg-black"
                    : "w-2 bg-black/20 hover:bg-black/50")
                }
              />
            ))}
          </div>

          {/* Next Button */}
          <button
            type="button"
            onClick={() => scrollTo(active + 1)}
            disabled={active === total - 1}
            aria-label="Kartu berikutnya"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-black text-white shadow-sm transition-all hover:bg-black/85 hover:scale-105 active:scale-95 disabled:pointer-events-none disabled:opacity-20"
          >
            <ChevronRight size={17} aria-hidden="true" />
          </button>
        </nav>
      </div>
    </section>
  );
}
