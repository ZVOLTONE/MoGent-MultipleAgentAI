import { LayoutGrid, Sparkles, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onChange: (v: string) => void;
  cardMode: boolean;
  onToggleCardMode: () => void;
  onSubmit: () => void;
  loading: boolean;
  onFocusChange: (focused: boolean) => void;
}

export function QueryBar({
  value,
  onChange,
  cardMode,
  onToggleCardMode,
  onSubmit,
  loading,
  onFocusChange,
}: Props) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!loading) onSubmit();
      }}
      className="w-full"
    >
      <div className="glass-input flex items-center gap-2 rounded-2xl p-2 transition-all focus-within:border-black/30 focus-within:ring-2 focus-within:ring-black/5">
        <Sparkles size={18} className="ml-2.5 shrink-0 text-black/50" aria-hidden="true" />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => onFocusChange(true)}
          onBlur={() => onFocusChange(false)}
          placeholder="Tanya analisis saham IDX, mis. “Analisis fundamental BBCA”"
          aria-label="Pertanyaan analisis"
          maxLength={300}
          className="min-w-0 flex-1 bg-transparent px-1 text-sm font-medium text-[var(--color-ink)] placeholder:text-[var(--color-ink-faint)] focus:outline-none"
        />

        <button
          type="button"
          onClick={onToggleCardMode}
          aria-pressed={cardMode}
          aria-label="Mode Kartu"
          title={cardMode ? "Mode Kartu: AKTIF" : "Mode Kartu: nonaktif"}
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-all",
            cardMode
              ? "border-black bg-black text-white shadow-sm"
              : "border-black/10 bg-white/70 text-[var(--color-ink-soft)] hover:bg-white hover:text-black"
          )}
        >
          <LayoutGrid size={13} aria-hidden="true" />
          <span className="hidden sm:inline">Mode Kartu</span>
          <span className="sr-only">{cardMode ? "aktif" : "nonaktif"}</span>
        </button>

        <button
          type="submit"
          disabled={loading || !value.trim()}
          aria-label="Kirim Analisis"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-black text-white shadow-sm transition-all hover:bg-black/90 active:scale-95 disabled:pointer-events-none disabled:opacity-25"
        >
          <ArrowUp size={18} aria-hidden="true" />
        </button>
      </div>
    </form>
  );
}
