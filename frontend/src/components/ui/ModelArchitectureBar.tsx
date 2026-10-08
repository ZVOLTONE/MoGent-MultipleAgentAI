import { useState } from "react";
import { BACKEND_MODELS, ThinkingOrb, type BackendModelConfig } from "./thinking-orb";
import { Cpu, Info, ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  activeModelId?: string;
  isCompact?: boolean;
}

export function ModelArchitectureBar({ activeModelId, isCompact = false }: Props) {
  const [selectedModel, setSelectedModel] = useState<BackendModelConfig | null>(null);
  const [expanded, setExpanded] = useState(!isCompact);

  return (
    <section aria-label="Arsitektur 4 Model Backend" className="w-full my-6">
      <div className="glass-panel mx-auto max-w-4xl rounded-[var(--radius-card)] p-5 sm:p-6">
        <div className="flex items-center justify-between border-b border-black/[0.06] pb-3.5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-black text-white">
              <Cpu size={14} />
            </span>
            <div>
              <h2 className="text-xs font-semibold tracking-wide uppercase text-[var(--color-ink)]">
                Arsitektur 4 Model Kolaboratif (MoGent)
              </h2>
              <p className="text-[11px] text-[var(--color-ink-faint)]">
                Setiap model memiliki peran dan representasi Orb 3D partikel tersendiri
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex items-center gap-1 rounded-lg border border-black/10 bg-white/70 px-2.5 py-1 text-[11px] font-medium text-[var(--color-ink-soft)] transition-colors hover:bg-black hover:text-white"
          >
            <span>{expanded ? "Tutup" : "Lihat Detail"}</span>
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>

        {expanded && (
          <div className="mt-5 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            {BACKEND_MODELS.map((model) => {
              const isActive = activeModelId === model.id;
              const isSelected = selectedModel?.id === model.id;

              return (
                <div
                  key={model.id}
                  onClick={() => setSelectedModel((prev) => (prev?.id === model.id ? null : model))}
                  className={`glass-card group relative flex cursor-pointer flex-col items-center rounded-2xl p-4 text-center transition-all ${
                    isActive
                      ? "ring-2 ring-black bg-white"
                      : isSelected
                      ? "ring-1 ring-black/40 bg-white/90"
                      : "hover:border-black/20"
                  }`}
                >
                  {/* Model 3D Orb */}
                  <div className="relative mb-1 flex h-28 w-28 items-center justify-center">
                    <ThinkingOrb
                      variant={model.mode}
                      surface="light"
                      size={110}
                      speed={0.9}
                      showCaption={false}
                    />
                  </div>

                  {/* Badge Model Code */}
                  <div className="mb-1.5 inline-flex items-center gap-1 rounded-full border border-black/10 bg-black/[0.04] px-2.5 py-0.5 font-mono text-[10px] font-semibold text-black">
                    <span>{model.modelCode}</span>
                  </div>

                  {/* Title & Role */}
                  <h3 className="text-xs font-semibold tracking-tight text-[var(--color-ink)]">
                    {model.title}
                  </h3>
                  <p className="mt-0.5 text-[11px] font-medium text-[var(--color-ink-soft)]">
                    {model.role}
                  </p>

                  <p className="mt-2 line-clamp-2 text-[10px] leading-relaxed text-[var(--color-ink-faint)]">
                    {model.description}
                  </p>

                  {/* Orb Representation Tag */}
                  <div className="mt-3 flex items-center gap-1 text-[9px] font-mono uppercase tracking-wider text-black/50">
                    <span>Orb:</span>
                    <span className="font-semibold text-black">{model.mode}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Selected Model Expanded Info Box */}
        {selectedModel && expanded && (
          <div className="mt-4 rounded-xl border border-black/[0.08] bg-black/[0.02] p-3 text-xs">
            <div className="flex items-start gap-2">
              <Info size={14} className="mt-0.5 shrink-0 text-black/60" />
              <div>
                <span className="font-semibold text-black">{selectedModel.title} ({selectedModel.modelCode}):</span>{" "}
                <span className="text-[var(--color-ink-soft)]">{selectedModel.description}</span>
                <div className="mt-1 font-mono text-[11px] text-black/70">
                  Tahap Alur: <span className="underline">{selectedModel.stepName}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
