import { motion } from "motion/react";
import {
  LayoutGrid,
  TrendingUp,
  Users,
  Globe2,
  LineChart,
  Newspaper,
  ShieldAlert,
  FileText,
  BookOpen,
  type LucideIcon,
} from "lucide-react";
import type { Card as CardT, GlossaryItem, NewsItem } from "@/types";
import { FactGrid } from "./FactGrid";
import { NewsList } from "./NewsList";
import { Bullets } from "./Bullets";
import { Sparkline } from "./Sparkline";
import { TracePanel } from "./TracePanel";

const ICONS: Record<string, LucideIcon> = {
  summary: LayoutGrid,
  valuation: TrendingUp,
  performance: TrendingUp,
  ownership: Users,
  macro: Globe2,
  price: LineChart,
  chart: LineChart,
  news: Newspaper,
  risk: ShieldAlert,
  trace: FileText,
  glossary: BookOpen,
};

interface Props {
  card: CardT;
  index: number;
  total: number;
  fontScale: number;
  isActive: boolean;
  distanceFromCenter: number;
  onClick?: () => void;
}

export function Card({
  card,
  index,
  total,
  fontScale,
  isActive,
  distanceFromCenter,
  onClick,
}: Props) {
  const Icon = ICONS[card.id] || ICONS[card.type] || FileText;
  const isGlossary = card.type === "glossary";

  // Calculate blur and scaling based on distance from center (PRD & User Request)
  const blurPx = isActive ? 0 : distanceFromCenter === 1 ? 5 : 8;
  const targetOpacity = isActive ? 1 : distanceFromCenter === 1 ? 0.6 : 0.35;
  const targetScale = isActive ? 1 : distanceFromCenter === 1 ? 0.95 : 0.9;

  // Staggered fan rotation for playing card dealing animation
  const fanRotation = (index - (total - 1) / 2) * 4;

  return (
    <motion.article
      className={`deck-card transition-shadow ${
        isActive ? "z-20 cursor-default" : "z-10 cursor-pointer hover:opacity-80"
      }`}
      onClick={!isActive ? onClick : undefined}
      initial={{
        opacity: 0,
        y: 80,
        rotate: fanRotation,
        scale: 0.88,
      }}
      animate={{
        opacity: targetOpacity,
        y: 0,
        rotate: 0,
        scale: targetScale,
        filter: `blur(${blurPx}px)`,
      }}
      transition={{
        y: { type: "spring", stiffness: 220, damping: 22, mass: 0.85, delay: index * 0.08 },
        rotate: { type: "spring", stiffness: 220, damping: 22, mass: 0.85, delay: index * 0.08 },
        opacity: { duration: 0.35, delay: index * 0.06 },
        scale: { type: "spring", stiffness: 260, damping: 25 },
        filter: { duration: 0.35 },
      }}
      aria-roledescription="kartu"
      aria-label={`Kartu ${index + 1} dari ${total}: ${card.title}`}
      style={{ fontSize: `${fontScale}rem` }}
    >
      <div
        className={`glass-card flex h-full min-h-[440px] flex-col rounded-[var(--radius-card)] p-6 sm:p-7 ${
          isActive
            ? "shadow-[0_24px_50px_-12px_rgba(0,0,0,0.1),0_2px_4px_rgba(0,0,0,0.04),inset_0_1px_1px_rgba(255,255,255,1)]"
            : "shadow-[0_8px_20px_-8px_rgba(0,0,0,0.06)]"
        }`}
      >
        <header className="mb-5 flex items-center gap-3.5 border-b border-black/[0.06] pb-4">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-black text-white shadow-sm ring-1 ring-black/10">
            <Icon size={18} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-base font-semibold tracking-tight text-[var(--color-ink)]">
              {card.title}
            </h2>
            {card.subtitle && (
              <p className="truncate text-xs font-medium text-[var(--color-ink-faint)]">
                {card.subtitle}
              </p>
            )}
          </div>
          <span className="rounded-full border border-black/[0.08] bg-white/70 px-2.5 py-0.5 font-mono text-[11px] font-medium tabular-nums text-[var(--color-ink-soft)]">
            {index + 1}/{total}
          </span>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {card.type === "chart" && card.series && (
            <Sparkline series={card.series} />
          )}
          {card.facts && card.facts.length > 0 && <FactGrid facts={card.facts} />}
          {card.type === "news" && (
            <NewsList items={(card.items as NewsItem[]) || []} />
          )}
          {card.type === "trace" && <TracePanel card={card} />}
          {isGlossary && (
            <dl className="space-y-3">
              {((card.items as GlossaryItem[]) || []).map((g, i) => (
                <div key={i} className="rounded-xl border border-black/[0.06] bg-white/50 p-3.5 backdrop-blur-sm">
                  <dt className="text-sm font-semibold text-[var(--color-ink)]">{g.term}</dt>
                  <dd className="mt-1 text-sm leading-relaxed text-[var(--color-ink-soft)]">
                    {g.definition}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {card.type !== "trace" && card.bullets && card.bullets.length > 0 && (
            <div className="rounded-xl border border-black/[0.06] bg-white/40 p-4 backdrop-blur-sm">
              <Bullets items={card.bullets} />
            </div>
          )}
        </div>
      </div>
    </motion.article>
  );
}
