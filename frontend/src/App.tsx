import { useState } from "react";
import { AlertCircle, Layers, ShieldCheck } from "lucide-react";
import { runQuery, buildCards } from "@/lib/api";
import type { CardsResponse, QueryResult } from "@/types";
import { QueryBar } from "@/components/ui/QueryBar";
import { LoadingSteps } from "@/components/ui/LoadingSteps";
import { Deck } from "@/components/ui/Deck";
import { PlainAnswer } from "@/components/ui/PlainAnswer";
import { ModelArchitectureBar } from "@/components/ui/ModelArchitectureBar";

export default function App() {
  const [query, setQuery] = useState("");
  const [cardMode, setCardMode] = useState(true); // default ON (PRD 11.3)
  const [loading, setLoading] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const [showModelsInfo, setShowModelsInfo] = useState(false);

  const [result, setResult] = useState<QueryResult | null>(null);
  const [cards, setCards] = useState<CardsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleSubmit() {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const qr = await runQuery(q);
      setResult(qr);
      if (cardMode) {
        try {
          const cardsResp = await buildCards(qr);
          setCards(cardsResp);
        } catch (e) {
          // /query ok but /cards failed -> fall back to text (PRD 11.5, W-T17)
          setCards(null);
          setNotice("Mode Kartu gagal disusun, beralih ke format teks.");
        }
      } else {
        setCards(null);
      }
    } catch (e) {
      // backend unreachable: keep previous deck, show message (PRD 11.5)
      setError(
        e instanceof Error
          ? `Gagal terhubung ke engine analisis backend. ${e.message}`
          : "Terjadi gangguan koneksi."
      );
    } finally {
      setLoading(false);
    }
  }

  const showDeck = cardMode && cards && !loading;
  const showPlain = result && !loading && (!cardMode || !cards);

  return (
    <div className="min-h-full pb-16 selection:bg-black selection:text-white">
      {/* Top Navigation & Query Header (Frosted Glass) */}
      <header className="sticky top-0 z-30 border-b border-black/[0.06] bg-white/75 backdrop-blur-xl transition-all">
        <div className="mx-auto max-w-4xl px-4 py-3 sm:px-6">
          <div className="mb-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-black text-white text-[10px] font-bold">
                M
              </span>
              <h1 className="text-sm font-semibold tracking-tight text-[var(--color-ink)]">
                AISector<span className="font-normal text-[var(--color-ink-faint)]">·MoGent</span>
              </h1>
              <span className="hidden sm:inline-flex items-center gap-1 rounded-full border border-black/10 bg-black/[0.03] px-2 py-0.5 text-[10px] font-mono text-black/70">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                4 Core Models
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowModelsInfo((v) => !v)}
                className="flex items-center gap-1 rounded-full border border-black/10 bg-white/60 px-2.5 py-1 text-[11px] font-medium text-[var(--color-ink-soft)] backdrop-blur-md transition-colors hover:bg-black hover:text-white"
              >
                <Layers size={12} />
                <span>Arsitektur Orb Model</span>
              </button>
              <span className="text-[11px] font-mono text-[var(--color-ink-faint)] hidden sm:inline">
                IDX Grounded
              </span>
            </div>
          </div>

          <QueryBar
            value={query}
            onChange={setQuery}
            cardMode={cardMode}
            onToggleCardMode={() => setCardMode((v) => !v)}
            onSubmit={handleSubmit}
            loading={loading}
            onFocusChange={setInputFocused}
          />

          {notice && (
            <p className="mt-2 text-xs font-medium text-[var(--color-warn)]">{notice}</p>
          )}
          {error && (
            <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[var(--color-bad)]">
              <AlertCircle size={13} aria-hidden="true" />
              {error}
            </p>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
        {/* Toggleable Model Architecture Showcase */}
        {showModelsInfo && (
          <div className="animate-fade-up mb-6">
            <ModelArchitectureBar />
          </div>
        )}

        {/* Loading State with Dynamic Model Orbs */}
        {loading && <LoadingSteps cardMode={cardMode} />}

        {/* Empty State / Welcome Screen */}
        {!loading && !result && (
          <EmptyState
            onPick={(q) => {
              setQuery(q);
            }}
          />
        )}

        {/* Results: Horizontal Card Deck or Plain Text */}
        {showDeck && (
          <div className="animate-fade-up">
            <Deck data={cards!} inputFocused={inputFocused} />
          </div>
        )}
        {showPlain && (
          <div className="animate-fade-up">
            <PlainAnswer result={result!} />
          </div>
        )}
      </main>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  const examples = [
    "Analisis fundamental BBCA",
    "Saya pensiunan, ingin menjaga kekayaan tapi tetap tumbuh pelan. Apakah BBCA cocok? Jelaskan sederhana.",
    "Bagaimana inflasi dan kurs Indonesia?",
    "Berapa harga BBRI?",
  ];

  return (
    <div className="animate-fade-up mx-auto max-w-4xl py-6 sm:py-10">
      {/* Hero Badge & Title */}
      <div className="text-center">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-black/10 bg-white/80 px-3.5 py-1 text-xs font-medium text-black backdrop-blur-md shadow-xs">
          <ShieldCheck size={14} className="text-black" />
          <span>Grounded Multi-Agent Intelligence · IDX</span>
        </div>

        <h2 className="mt-4 text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
          Analisis Saham Terverifikasi, Disajikan Sebagai Kartu.
        </h2>
        
        <p className="mx-auto mt-2.5 max-w-xl text-sm leading-relaxed text-[var(--color-ink-soft)]">
          Didukung kolaborasi 4 model AI spesialis dengan verifikasi fakta grounding.
          Setiap angka dapat ditelusuri ke sumber laporan resmi emiten dan pasar modal.
        </p>
      </div>

      {/* 4 Models Showcase with Distinct Live 3D Orbs */}
      <div className="mt-8">
        <ModelArchitectureBar isCompact={false} />
      </div>

      {/* Suggested Questions */}
      <div className="mt-6 text-center">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">
          Contoh Pertanyaan Analisis
        </p>
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          {examples.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => onPick(ex)}
              className="glass-pill max-w-full truncate rounded-full px-4 py-2 text-xs font-medium text-[var(--color-ink-soft)] transition-all hover:bg-black hover:text-white"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
