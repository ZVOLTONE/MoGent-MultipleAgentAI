"use client";

import * as React from "react";

/* ---------------------------------- Types --------------------------------- */

export type ThinkingOrbMode =
  | "orbits"
  | "globe"
  | "wave"
  | "ring"
  | "ribbon"
  | "braid";

export type ThinkingOrbVariant =
  | "working"
  | "searching"
  | "listening"
  | "breathing"
  | "composing"
  | "weaving";

export type ThinkingOrbSurface = "auto" | "light" | "dark";

export interface ThinkingOrbProps {
  variant?: ThinkingOrbVariant | ThinkingOrbMode;
  /** "light" = black dots (for white / glass background), "dark" = white dots, "auto" = follows theme */
  surface?: ThinkingOrbSurface;
  /** canvas size in px */
  size?: number;
  /** animation speed multiplier */
  speed?: number;
  /** sphere scale relative to canvas (0-1) */
  scale?: number;
  playback?: "play" | "pause";
  caption?: string;
  className?: string;
  showCaption?: boolean;
}

export const VARIANT_TO_MODE_MAP: Record<
  ThinkingOrbVariant | ThinkingOrbMode,
  ThinkingOrbMode
> = {
  working: "orbits",
  orbits: "orbits",
  searching: "globe",
  globe: "globe",
  listening: "wave",
  wave: "wave",
  breathing: "ring",
  ring: "ring",
  composing: "ribbon",
  ribbon: "ribbon",
  weaving: "braid",
  braid: "braid",
};

export const CAPTIONS: Record<ThinkingOrbMode, string> = {
  orbits: "Orchestrating",
  globe: "Specialist Reasoning",
  wave: "Synthesizing",
  ribbon: "Composing Cards",
  braid: "Multi-Agent Weaver",
  ring: "System Core",
};

/* ------------------ 4 Backend Models Configuration ------------------ */

export interface BackendModelConfig {
  id: string;
  title: string;
  modelCode: string;
  mode: ThinkingOrbMode;
  variant: ThinkingOrbVariant;
  role: string;
  stepName: string;
  description: string;
}

export const BACKEND_MODELS: BackendModelConfig[] = [
  {
    id: "orchestrator",
    title: "Orchestrator Model",
    modelCode: "qwen2.5:7b",
    mode: "orbits",
    variant: "working",
    role: "Perencanaan & Intent Routing",
    stepName: "Memahami pertanyaan & merancang rute",
    description: "Mendeteksi maksud pengguna, memilih spesialis yang tepat, dan mengelola alur kolaborasi agent.",
  },
  {
    id: "specialist",
    title: "Specialist Model",
    modelCode: "deepseek-r1:7b",
    mode: "globe",
    variant: "searching",
    role: "Penalaran Mendalam & Pengambilan Data",
    stepName: "Mengambil data & eksekusi kalkulasi",
    description: "Model reasoning yang menjalankan kalkulasi valuasi, membedah rasio keuangan, dan memanggil tool UTCP.",
  },
  {
    id: "synthesizer",
    title: "Synthesizer Model",
    modelCode: "qwen2.5:7b",
    mode: "wave",
    variant: "listening",
    role: "Sintesis & Validasi Fakta Grounding",
    stepName: "Menyintesis temuan & uji kontradiksi",
    description: "Memadukan temuan antar-agent, memastikan semua angka bersumber bukti dan bebas halusinasi.",
  },
  {
    id: "presentation",
    title: "Presentation Composer",
    modelCode: "qwen2.5:7b",
    mode: "ribbon",
    variant: "composing",
    role: "Penyusun Slide & Struktur Kartu",
    stepName: "Menyusun kartu visual interaktif",
    description: "Mengonversi fakta terverifikasi ke dalam format slide kartu interaktif yang siap dipindai.",
  },
];

/* ------------------------------- Geometry --------------------------------- */

type Pt = { x: number; y: number; z: number; a: number; r: number };

const TAU = Math.PI * 2;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));

function fibSphere(n: number) {
  const pts: { x: number; y: number; z: number }[] = [];
  for (let i = 0; i < n; i++) {
    const y = 1 - (2 * (i + 0.5)) / n;
    const rr = Math.sqrt(1 - y * y);
    const th = i * GOLDEN;
    pts.push({ x: Math.cos(th) * rr, y, z: Math.sin(th) * rr });
  }
  return pts;
}

const SPHERE_DENSE = fibSphere(480);
const SPHERE_GHOST = fibSphere(220);

function rotate(
  x: number,
  y: number,
  z: number,
  ay: number,
  ax: number
): [number, number, number] {
  // Y-axis rotation
  const cy = Math.cos(ay);
  const sy = Math.sin(ay);
  const x1 = x * cy + z * sy;
  const z1 = -x * sy + z * cy;
  // X-axis rotation
  const cx = Math.cos(ax);
  const sx = Math.sin(ax);
  const y2 = y * cx - z1 * sx;
  const z2 = y * sx + z1 * cx;
  return [x1, y2, z2];
}

function ghost(ay: number, ax: number, a = 0.14): Pt[] {
  return SPHERE_GHOST.map((p) => {
    const [x, y, z] = rotate(p.x, p.y, p.z, ay, ax);
    return { x, y, z, a, r: 0.9 };
  });
}

const GENERATORS: Record<ThinkingOrbMode, (t: number) => Pt[]> = {
  /* Model 1: Orbits - particles revolving in tilted orbital rings around a ghosted sphere */
  orbits: (t) => {
    const out = ghost(t * 0.25, 0.4);
    for (let k = 0; k < 3; k++) {
      const tilt = (k * Math.PI) / 3 + 0.5;
      const m = 56;
      for (let i = 0; i < m; i++) {
        const ang = (i / m) * TAU + t * (0.8 + k * 0.25);
        const [x, y, z] = rotate(
          Math.cos(ang),
          0,
          Math.sin(ang),
          k * 1.05 + t * 0.15,
          tilt
        );
        out.push({ x, y, z, a: 0.95, r: 1.6 });
      }
    }
    return out;
  },

  /* Model 2: Globe - dense dotted sphere with vertical scan beam */
  globe: (t) => {
    const sweep = Math.sin(t * 1.1);
    return SPHERE_DENSE.map((p) => {
      const d = p.y - sweep;
      const glow = Math.exp(-d * d * 16);
      const [x, y, z] = rotate(p.x, p.y, p.z, t * 0.5, 0.35);
      return { x, y, z, a: 0.3 + 0.7 * glow, r: 1 + glow * 1.1 };
    });
  },

  /* Model 3: Wave - harmonic breathing latitude rings */
  wave: (t) => {
    const out: Pt[] = [];
    const L = 15;
    for (let i = 0; i < L; i++) {
      const phi = -Math.PI / 2 + (Math.PI * (i + 0.5)) / L;
      const k =
        1 + 0.12 * Math.sin(t * 2 + i * 0.6) + 0.08 * Math.sin(t * 3.1 - i * 0.9);
      const rr = Math.cos(phi) * k;
      const n = Math.round(10 + 44 * Math.cos(phi));
      for (let j = 0; j < n; j++) {
        const th = (j / n) * TAU + t * 0.2 * (i % 2 ? 1 : -1);
        const [x, y, z] = rotate(
          Math.cos(th) * rr,
          Math.sin(phi),
          Math.sin(th) * rr,
          0,
          0.28
        );
        out.push({ x, y, z, a: 0.85, r: 1.2 });
      }
    }
    return out;
  },

  /* Face-on ring pulsing with slow radial ripple */
  ring: (t) => {
    const out: Pt[] = [];
    for (let j = 0; j < 4; j++) {
      const radius = 0.45 + j * 0.15 + 0.04 * Math.sin(t * 1.5 - j * 0.9);
      const n = 70 + j * 24;
      for (let i = 0; i < n; i++) {
        const ang = (i / n) * TAU + t * 0.15 * (j % 2 ? 1 : -1);
        out.push({
          x: Math.cos(ang) * radius,
          y: Math.sin(ang) * radius,
          z: 0.4,
          a: 0.35 + 0.2 * j + 0.2 * Math.sin(t * 1.5 - j * 0.9),
          r: 1.3,
        });
      }
    }
    return out;
  },

  /* Model 4: Ribbon - multi-lane ribbon flowing around the sphere */
  ribbon: (t) => {
    const out: Pt[] = [];
    const lanes = 5;
    const steps = 130;
    for (let l = 0; l < lanes; l++) {
      for (let i = 0; i < steps; i++) {
        const th = (i / steps) * TAU;
        const lat =
          0.5 * Math.sin(2 * th + t * 1.5) +
          0.12 * Math.sin(3 * th - t) +
          (l - (lanes - 1) / 2) * 0.13;
        const [x, y, z] = rotate(
          Math.cos(lat) * Math.cos(th),
          Math.sin(lat),
          Math.cos(lat) * Math.sin(th),
          t * 0.4,
          0.3
        );
        out.push({ x, y, z, a: 0.9, r: 1.3 });
      }
    }
    return [...ghost(t * 0.4, 0.3, 0.1), ...out];
  },

  /* Braid - three helical strands interwoven around a ghosted sphere */
  braid: (t) => {
    const out = ghost(0, 0.3, 0.1);
    const n = 100;
    for (let s = 0; s < 3; s++) {
      for (let i = 0; i < n; i++) {
        const v = (i / (n - 1)) * 2 - 1;
        const y = v * 0.95;
        const rr = Math.sqrt(1 - y * y) * 0.9;
        const ang = v * 5 + t * 1.4 + (s * TAU) / 3;
        const [x, yy, z] = rotate(
          Math.cos(ang) * rr,
          y,
          Math.sin(ang) * rr,
          0,
          0.3
        );
        out.push({ x, y: yy, z, a: 0.95, r: 1.5 });
      }
    }
    return out;
  },
};

/* -------------------------------- Component ------------------------------- */

export function ThinkingOrb({
  variant = "working",
  surface = "light",
  size = 220,
  speed = 1,
  scale = 0.74,
  playback = "play",
  caption,
  className,
  showCaption = true,
}: ThinkingOrbProps) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const mode = VARIANT_TO_MODE_MAP[variant] ?? "orbits";

  const live = React.useRef({ speed, scale, playback, surface, mode });
  live.current = { speed, scale, playback, surface, mode };

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    let raf = 0;
    let last = performance.now();
    let t = 0;

    const frame = (now: number) => {
      const s = live.current;
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      if (s.playback === "play") t += dt * s.speed;

      const dark =
        s.surface === "dark" ||
        (s.surface === "auto" &&
          document.documentElement.classList.contains("dark"));
      const ink = dark ? "255,255,255" : "0,0,0";

      ctx.clearRect(0, 0, size, size);
      const R = (size / 2) * s.scale;
      const c = size / 2;

      const pts = GENERATORS[s.mode](t).sort((a, b) => a.z - b.z);
      for (const p of pts) {
        const depth = (p.z + 1) / 2; // 0 (back) .. 1 (front)
        const alpha = Math.min(1, p.a * (0.28 + 0.72 * depth));
        const rad = (p.r * (0.58 + 0.52 * depth) * size) / 240;
        ctx.beginPath();
        ctx.arc(c + p.x * R, c - p.y * R, rad, 0, TAU);
        ctx.fillStyle = `rgba(${ink},${alpha.toFixed(3)})`;
        ctx.fill();
      }
      raf = requestAnimationFrame(frame);
    };

    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [size]);

  return (
    <div
      className={["inline-flex flex-col items-center gap-2", className]
        .filter(Boolean)
        .join(" ")}
      role="status"
      aria-label={caption ?? CAPTIONS[mode]}
    >
      <canvas
        ref={canvasRef}
        style={{ width: size, height: size }}
        aria-hidden="true"
        className="pointer-events-none drop-shadow-[0_4px_12px_rgba(0,0,0,0.08)]"
      />
      {showCaption && (
        <span
          className={`text-[10px] tracking-[0.22em] font-medium uppercase ${
            surface === "dark" ? "text-white/60" : "text-black/60"
          }`}
        >
          {caption ?? CAPTIONS[mode]}
        </span>
      )}
    </div>
  );
}

/* Named wrappers */
type OrbPreset = Omit<ThinkingOrbProps, "variant">;
export const OrbWorking = (p: OrbPreset) => <ThinkingOrb variant="working" {...p} />;
export const OrbSearching = (p: OrbPreset) => <ThinkingOrb variant="searching" {...p} />;
export const OrbListening = (p: OrbPreset) => <ThinkingOrb variant="listening" {...p} />;
export const OrbBreathing = (p: OrbPreset) => <ThinkingOrb variant="breathing" {...p} />;
export const OrbComposing = (p: OrbPreset) => <ThinkingOrb variant="composing" {...p} />;
export const OrbWeaving = (p: OrbPreset) => <ThinkingOrb variant="weaving" {...p} />;

export default ThinkingOrb;
