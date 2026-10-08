import { useMemo } from "react";
import type { SeriesPoint } from "@/types";

interface Props {
  series: SeriesPoint[];
  height?: number;
}

/** Minimalist monochrome price line for glass cards */
export function Sparkline({ series, height = 120 }: Props) {
  const { path, area, first, last, minVal, maxVal } = useMemo(() => {
    const w = 480;
    const h = height;
    const pad = 8;
    const vals = series.map((p) => p.c);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const span = max - min || 1;
    const stepX = (w - pad * 2) / Math.max(1, series.length - 1);
    const pts = series.map((p, i) => {
      const x = pad + i * stepX;
      const y = pad + (h - pad * 2) * (1 - (p.c - min) / span);
      return [x, y] as const;
    });
    const d = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const areaD = `${d} L${pts[pts.length - 1][0].toFixed(1)},${h - pad} L${pts[0][0].toFixed(1)},${h - pad} Z`;
    return {
      path: d,
      area: areaD,
      first: series[0],
      last: series[series.length - 1],
      minVal: min,
      maxVal: max,
    };
  }, [series, height]);

  return (
    <figure className="m-0 rounded-xl border border-black/[0.07] bg-white/50 p-3.5 backdrop-blur-sm" aria-label="Grafik pergerakan harga">
      <div className="mb-2 flex items-center justify-between text-[11px] font-mono text-[var(--color-ink-faint)]">
        <span>Min: {minVal.toLocaleString("id-ID")}</span>
        <span>Max: {maxVal.toLocaleString("id-ID")}</span>
      </div>
      <svg
        viewBox={`0 0 480 ${height}`}
        className="w-full overflow-visible"
        role="img"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#000000" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#000000" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#spark-fill)" />
        <path d={path} fill="none" stroke="#000000" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <figcaption className="mt-2.5 flex justify-between text-[11px] font-mono text-[var(--color-ink-faint)]">
        <span>{first?.d}</span>
        <span>{last?.d}</span>
      </figcaption>
    </figure>
  );
}
