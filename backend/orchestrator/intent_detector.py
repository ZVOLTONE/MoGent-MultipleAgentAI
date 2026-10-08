"""Intent & persona detection (PRD 8, 14).

Uses the orchestrator LLM to classify the user's utterance, with a
heuristic fallback so the system still works if the LLM returns bad JSON.
Persona is detected ONLY from the user's words (PRD 9.7).
"""
from __future__ import annotations

import re

from config import config
from backend.llm.ollama import OllamaClient
from backend.llm import prompts
from backend.utcp import stock_universe

VALID_INTENTS = {"price", "single_metric", "fundamental", "macro", "multi_analysis",
                 "education", "general_education", "news_search", "out_of_scope"}
VALID_PERSONAS = {"complete_beginner", "fundamental_investor", "macro_strategist",
                  "wealth_preservation", "senior_investor"}
VALID_CAPS = {"investment_education", "fundamental_analysis", "valuation_analysis",
              "risk_analysis", "dividend_analysis", "macro_analysis", "news_sentiment",
              "catalyst_analysis"}
VALID_MODS = {"simple_language", "sector_bank", "downside_focus"}

# Words that signal a news/catalyst request component
_NEWS_WORDS = (
    "berita", "kabar", "update", "cari informasi", "informasi tentang",
    "news", "terkini tentang", "apa yang terjadi", "kebijakan",
    "katalis", "isu", "kejadian", "peristiwa",
)

# Words that signal fundamental/analysis request for a company
_FUNDAMENTAL_WORDS = (
    "fundamental", "analisis", "analisa", "analisis saham", "kinerja",
    "valuasi", "per ", "pbv", "pb ", "roe", "eps", "ldr", "laporan keuangan",
    "review", "bagaimana saham", "bagaimana kinerja", "bagaimana kondisi",
    "carikan", "cari tahu", "berikan analisis", "harga saham",
)

# Words that signal multi-dimensional / comprehensive analysis
_MULTI_WORDS = (
    "gabungkan", "kombinasi", "sekaligus", "dan juga", "serta",
    "fundamental dan", "dan makro", "dan berita", "multi", "komprehensif",
    "menyeluruh", "lengkap", "kemudian", "lalu",
)


class IntentDetector:
    def __init__(self, llm: OllamaClient | None = None):
        self.llm = llm or OllamaClient()

    def detect(self, user_query: str) -> dict:
        res = self.llm.generate_json(config.ORCHESTRATOR_MODEL,
                                     prompts.intent_persona_prompt(user_query))
        data = res["data"] if res["ok"] and isinstance(res["data"], dict) else {}
        return self._sanitize(data, user_query)

    def _sanitize(self, data: dict, user_query: str) -> dict:
        ticker = self._ticker(data.get("ticker"), user_query)
        out = {
            "ticker": ticker,
            "intent": data.get("intent") if data.get("intent") in VALID_INTENTS else None,
            "personas": [p for p in (data.get("personas") or []) if p in VALID_PERSONAS],
            "capabilities": [c for c in (data.get("capabilities") or []) if c in VALID_CAPS],
            "modifiers": [m for m in (data.get("modifiers") or []) if m in VALID_MODS],
            "needs_macro_numbers": bool(data.get("needs_macro_numbers", False)),
            # whether the user also wants news/catalyst context alongside data analysis
            "wants_news": False,
        }

        # heuristic backstops
        q = user_query.lower()
        if out["intent"] is None:
            out["intent"] = self._heuristic_intent(q, ticker)

        # A question with no ticker that asks for a definition/concept is
        # general education, answered directly without any tool/API call.
        if ticker is None and out["intent"] in ("education", "single_metric", "fundamental",
                                                 "price") and self._looks_general(q):
            out["intent"] = "general_education"

        if "sederhana" in q or "pemula" in q:
            if "simple_language" not in out["modifiers"]:
                out["modifiers"].append("simple_language")
            if "complete_beginner" not in out["personas"]:
                out["personas"].append("complete_beginner")
        if any(w in q for w in ("preservasi", "menjaga kekayaan", "pensiun", "pensiunan")):
            if "wealth_preservation" not in out["personas"]:
                out["personas"].append("wealth_preservation")
        if "bi rate" in q or "inflasi" in q or "kurs" in q:
            out["needs_macro_numbers"] = True

        # Detect presence of news/catalyst keywords and fundamental keywords
        has_news_words = any(w in q for w in _NEWS_WORDS)
        has_fundamental_words = any(w in q for w in _FUNDAMENTAL_WORDS)
        has_multi_words = any(w in q for w in _MULTI_WORDS)

        # ---------------------------------------------------------------
        # CRITICAL FIX: When a ticker is present, NEVER route to pure
        # news_search. Instead:
        #   - fundamental/valuation only → fundamental
        #   - fundamental + news/macro/catalyst → multi_analysis
        #   - news only for a stock → multi_analysis (run data + news)
        # This prevents queries like "analisis ADRO + berita kebijakan"
        # from being hijacked into a generic news search.
        # ---------------------------------------------------------------
        if ticker:
            if has_news_words:
                out["wants_news"] = True
            # Upgrade news_search to multi_analysis whenever ticker is known
            if out["intent"] == "news_search":
                out["intent"] = "multi_analysis"
            # If both fundamental intent AND news/multi words present → multi_analysis
            if has_news_words or has_multi_words:
                if out["intent"] in ("fundamental", "single_metric", "education"):
                    out["intent"] = "multi_analysis"
            # Ensure at least fundamental if no explicit intent resolved yet
            if out["intent"] not in VALID_INTENTS:
                out["intent"] = "multi_analysis" if has_news_words else "fundamental"
        else:
            # No ticker → pure news search is fine for news keywords
            if has_news_words and not out["needs_macro_numbers"]:
                out["intent"] = "news_search"
                out["news_scope"] = (
                    "global" if any(w in q for w in
                                    ("global", "dunia", "internasional", "amerika", "as ",
                                     "china", "eropa", "fed"))
                    else "id"
                )

        out.setdefault("news_scope", "id")
        return out

    def _ticker(self, candidate, user_query) -> str | None:
        # Validate against the local IDX universe (CSV) - no API/token cost.
        return stock_universe.resolve_ticker(candidate, user_query)

    @staticmethod
    def _looks_general(q: str) -> bool:
        triggers = ("apa itu", "apa yang dimaksud", "jelaskan", "pengertian",
                    "definisi", "bagaimana cara", "apa perbedaan", "apa bedanya",
                    "mengapa", "kenapa", "contoh")
        return any(t in q for t in triggers)

    def _heuristic_intent(self, q: str, ticker: str | None) -> str:
        if ticker is None and self._looks_general(q):
            return "general_education"
        if "harga" in q and ticker:
            return "price"
        if "bi rate" in q or "inflasi" in q:
            return "macro"
        if ticker and (any(w in q for w in _FUNDAMENTAL_WORDS) or
                       any(w in q for w in _NEWS_WORDS) or
                       any(w in q for w in _MULTI_WORDS)):
            return "multi_analysis"
        if "fundamental" in q:
            return "fundamental" if ticker else "general_education"
        if "pemula" in q or "apa itu" in q:
            return "general_education" if ticker is None else "education"
        return "fundamental" if ticker else "general_education"
