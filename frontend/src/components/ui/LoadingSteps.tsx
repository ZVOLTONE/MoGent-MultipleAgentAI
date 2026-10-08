import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ThinkingOrb, BACKEND_MODELS } from "./thinking-orb";
import { Cpu } from "lucide-react";

interface LoadingStepsProps {
  cardMode: boolean;
}

export function LoadingSteps({ cardMode }: LoadingStepsProps) {
  const stepsList = cardMode ? BACKEND_MODELS : BACKEND_MODELS.slice(0, 3);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setStepIndex((current) => Math.min(current + 1, stepsList.length - 1));
    }, 1100);
    return () => window.clearInterval(id);
  }, [stepsList.length]);

  const activeModel = stepsList[stepIndex] || stepsList[0];

  return (
    <div
      className="glass-panel mx-auto my-6 flex max-w-xl flex-col items-center justify-center rounded-[var(--radius-card)] p-8 text-center transition-all"
      role="status"
      aria-live="polite"
    >
      {/* Active Model Live Orb */}
      <div className="relative mb-2 flex items-center justify-center">
        {/* Ambient subtle glow ring */}
        <div className="pointer-events-none absolute h-48 w-48 rounded-full bg-gradient-to-b from-black/[0.04] to-transparent blur-xl" />
        
        <AnimatePresence mode="wait">
          <motion.div
            key={activeModel.id}
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.04 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="relative"
          >
            <ThinkingOrb
              variant={activeModel.mode}
              surface="light"
              size={190}
              speed={1.05}
              showCaption={false}
            />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Model & Step Information */}
      <div className="space-y-1.5">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1 text-[11px] font-medium tracking-wide text-black/75">
          <Cpu size={12} className="text-black" />
          <span>{activeModel.title}</span>
          <span className="text-black/30">|</span>
          <span className="font-mono text-[10px] text-black/90">{activeModel.modelCode}</span>
        </div>

        <h3 className="pt-1 text-base font-semibold tracking-tight text-[var(--color-ink)]">
          {activeModel.stepName}…
        </h3>

        <p className="mx-auto max-w-md text-xs leading-relaxed text-[var(--color-ink-soft)]">
          {activeModel.role} · {activeModel.description}
        </p>
      </div>

      {/* 4 Models Progress Pipeline */}
      <div className="mt-6 w-full max-w-md space-y-3">
        {/* Progress Bar */}
        <div className="flex gap-1.5 px-2" aria-hidden="true">
          {stepsList.map((m, idx) => (
            <div
              key={m.id}
              className="h-1 flex-1 overflow-hidden rounded-full bg-black/10 transition-colors"
            >
              <div
                className={`h-full transition-all duration-500 ${
                  idx <= stepIndex ? "w-full bg-black" : "w-0"
                }`}
              />
            </div>
          ))}
        </div>

        {/* 4 Models Stage Badges */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {stepsList.map((model, idx) => {
            const isActive = idx === stepIndex;
            const isDone = idx < stepIndex;
            return (
              <div
                key={model.id}
                className={`flex flex-col items-center rounded-xl p-2 text-center transition-all ${
                  isActive
                    ? "border border-black/15 bg-white shadow-sm ring-1 ring-black/5"
                    : isDone
                    ? "border border-black/5 bg-black/[0.02] opacity-75"
                    : "border border-transparent opacity-40"
                }`}
              >
                <span className="text-[10px] font-semibold tracking-tight text-[var(--color-ink)]">
                  {model.title.replace(" Model", "")}
                </span>
                <span className="text-[9px] font-mono text-[var(--color-ink-faint)]">
                  {model.modelCode}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
