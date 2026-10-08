"""Explanation layer for cards (PRD Web-Cards 7.3, 7.4, 7.5).

The card explanations ("bullets") are built WITHOUT the LLM on the MVP:
  (a) a static glossary of beginner terms, and
  (b) sentences lifted from the validated synthesis answer, after being
      scrubbed of meta-phrases and ungrounded qualitative judgements.

No new numbers are introduced here. Everything is deterministic.
"""
from __future__ import annotations

import re

# Beginner glossary (PRD Lampiran B). Deskriptif, bukan preskriptif.
GLOSSARY: dict[str, str] = {
    "PER": "Harga saham dibagi laba per saham; menunjukkan berapa kali laba yang "
           "dibayar pasar untuk satu saham.",
    "PBV": "Harga saham dibagi nilai buku per saham.",
    "ROE": "Laba bersih dibagi ekuitas; mengukur laba yang dihasilkan dari modal "
           "pemegang saham.",
    "LDR": "Kredit dibagi dana pihak ketiga; menggambarkan seberapa besar dana "
           "simpanan yang disalurkan sebagai kredit.",
    "Kapitalisasi pasar": "Harga saham dikali jumlah saham beredar.",
    "Imbal hasil dividen": "Dividen per saham dibagi harga saham.",
    "Pendapatan bunga bersih": "Selisih pendapatan bunga dari kredit dengan beban "
                               "bunga atas dana pihak ketiga.",
}

# metric -> glossary key, used to add relevant terms to a glossary card.
METRIC_GLOSSARY_KEY = {
    "pe_ratio": "PER", "forward_pe": "PER",
    "pb_ratio": "PBV",
    "roe": "ROE", "q_roe_annualized": "ROE",
    "ldr": "LDR",
    "market_cap": "Kapitalisasi pasar",
    "dividend_yield": "Imbal hasil dividen",
    "net_interest_income": "Pendapatan bunga bersih",
    "q_net_interest_income": "Pendapatan bunga bersih",
}

# PRD 7.4: qualitative judgement words banned unless backed by a documented
# threshold or an explicit in-ledger comparison.
_JUDGEMENT_WORDS = [
    "tinggi", "rendah", "murah", "mahal", "sehat", "berisiko", "bagus", "buruk",
    "kuat", "lemah", "menarik", "overvalued", "undervalued", "wajar", "premium",
    "aman", "layak", "prospektif",
]
# PRD 7.5: trade-command words.
_TRADE_WORDS = ["beli", "jual", "tahan", "akumulasi", "buy", "sell", "hold"]
# PRD 7.5 / W-T8: meta phrases about the data pipeline itself.
_META_PATTERNS = [
    r"narasi agent", r"fact[_ ]?id", r"as[_ ]?of\s+kosong", r"evidence[_ ]?id",
    r"data duplikat", r"\{\{\s*f_\d+\s*\}\}", r"tidak terdapat kontradiksi",
    r"kontradiksi dalam narasi", r"penanda", r"ledger",
]

_META_RE = re.compile("|".join(_META_PATTERNS), re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _has_word(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", low) for w in words)


def is_meta(text: str) -> bool:
    return bool(_META_RE.search(text or ""))


def is_judgement(text: str) -> bool:
    """True if the sentence contains an ungrounded qualitative judgement.

    A judgement word is allowed only when a comparison cue is present
    (vs, dibanding, rata-rata, periode) — PRD 7.4 (comparison-from-data case).
    """
    if not _has_word(text, _JUDGEMENT_WORDS):
        return False
    low = text.lower()
    comparison_cues = ["dibanding", "vs", "versus", "rata-rata", "periode sebelum",
                       "lebih dari", "kurang dari", "di atas", "di bawah", "peer"]
    if any(c in low for c in comparison_cues):
        return False
    return True


def clean_bullet(text: str) -> str:
    """Strip raw markers and tidy whitespace from a sentence."""
    text = re.sub(r"\{\{\s*f_\d+\s*\}\}", "", text)
    text = re.sub(r"[#*`_>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_bullets(answer: str, max_items: int = 3,
                    *, allow_judgement: bool = False) -> list[str]:
    """Pick up to ``max_items`` grounded, non-meta sentences from the synthesis.

    Sentences with trade commands, meta phrases, or ungrounded judgements are
    dropped (PRD 7.4/7.5, W-T7/W-T8).
    """
    if not answer:
        return []
    # work on prose only: drop list markers / headings
    text = re.sub(r"^#{1,6}\s.*$", "", answer, flags=re.MULTILINE)
    out: list[str] = []
    for raw in _SENT_SPLIT.split(text):
        s = clean_bullet(raw)
        if len(s) < 25 or len(s) > 240:
            continue
        if is_meta(s) or _has_word(s, _TRADE_WORDS):
            continue
        if not allow_judgement and is_judgement(s):
            continue
        if s.lower().startswith(("ringkasan", "kesimpulan", "keterbatasan", "catatan")):
            s = s.split(":", 1)[-1].strip() or s
        if s and s not in out:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


def extract_risk_bullets(answer: str, max_items: int = 5) -> list[str]:
    """Pull sentences from a 'Risiko' section if present; judgements allowed
    here because risk discussion is inherently qualitative, but meta/trade words
    are still removed."""
    if not answer:
        return []
    # try to isolate a risk section
    m = re.search(r"(risiko|risk)[^\n]*\n(.+?)(\n#{1,6}\s|\Z)", answer,
                  re.IGNORECASE | re.DOTALL)
    scope = m.group(2) if m else answer
    out = []
    for raw in re.split(r"\n+|(?<=[.!?])\s+", scope):
        s = clean_bullet(re.sub(r"^[-*\d.\)\s]+", "", raw))
        if len(s) < 20 or len(s) > 240:
            continue
        if is_meta(s) or _has_word(s, _TRADE_WORDS):
            continue
        if s and s not in out:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


def glossary_for_metrics(metrics: list[str]) -> list[dict]:
    """Return glossary entries relevant to the metrics shown on other cards."""
    seen, out = set(), []
    for m in metrics:
        key = METRIC_GLOSSARY_KEY.get(m)
        if key and key not in seen and key in GLOSSARY:
            seen.add(key)
            out.append({"term": key, "definition": GLOSSARY[key]})
    return out
