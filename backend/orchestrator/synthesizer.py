"""Synthesizer (PRD 8, 16).

Combines validated agent outputs into one answer. It must NOT add numbers,
entities, or claims. It detects cross-agent contradictions (e.g. different
sectors) and reports them in Limitations instead of averaging them. Agents
with status no_data/error are moved to Limitations.
"""
from __future__ import annotations

from config import config
from backend.llm.ollama import OllamaClient
from backend.llm import prompts
from backend.grounding import number_validator, glossary

import re as _re

_NUM_TOKEN_RE = _re.compile(r"\d[\d.,]*")


def _numbers_in(text: str) -> set:
    """Set of normalized numeric tokens (digits only) appearing in text.

    Used to confirm the synthesizer did not invent figures beyond those
    already present in the (validated) agent narratives.
    """
    out = set()
    for m in _NUM_TOKEN_RE.finditer(text or ""):
        digits = "".join(ch for ch in m.group(0) if ch.isdigit())
        if len(digits) >= 2:  # ignore trivial single digits / list markers
            out.add(digits)
    return out


class Synthesizer:
    def __init__(self, llm: OllamaClient | None = None):
        self.llm = llm or OllamaClient()

    def detect_contradictions(self, agent_outputs: list[dict]) -> list[str]:
        contradictions = []
        sectors = {}
        for a in agent_outputs:
            ident = a.get("identity") or {}
            sec = ident.get("sector")
            if sec:
                sectors.setdefault(sec, []).append(a.get("agent_id"))
        if len(sectors) > 1:
            contradictions.append(
                "Sektor tidak konsisten antar-agent: " +
                "; ".join(f"{s} ({', '.join(ids)})" for s, ids in sectors.items()))
        return contradictions

    def synthesize(self, user_query: str, agent_outputs: list[dict],
                   global_facts: list[dict]) -> dict:
        # Separate news/catalyst outputs from data-analysis outputs
        # (catalyst_news agent is always "success" but has no numerical facts)
        news_outputs = [a for a in agent_outputs if a.get("agent_id") == "catalyst_news"]
        data_outputs = [a for a in agent_outputs if a.get("agent_id") != "catalyst_news"]

        successful = [a for a in data_outputs if a.get("status") in ("success", "partial")]
        degraded = [a for a in data_outputs if a.get("status") in ("no_data", "error")]

        limitations = []
        for a in degraded:
            lim = "; ".join(a.get("limitations", [])) or a.get("status")
            limitations.append(f"{a.get('agent_id')}: {lim}")

        contradictions = self.detect_contradictions(successful)

        if not successful and not news_outputs:
            return {
                "answer": "Semua agent tidak memperoleh data valid, sehingga tidak ada "
                          "analisis yang dapat disampaikan.",
                "limitations": limitations or ["tidak ada data valid"],
                "contradictions": contradictions,
            }

        # If only news output is available (no successful data agents), present
        # the news block directly as a partial answer.
        if not successful and news_outputs:
            news_text = "\n\n".join(a.get("analysis_text", "") for a in news_outputs)
            return {
                "answer": ("Data analisis fundamental tidak tersedia. "
                           "Berikut berita terkini yang dapat memberikan konteks:\n\n"
                           + news_text),
                "limitations": limitations + ["data fundamental tidak tersedia; menampilkan berita saja"],
                "contradictions": contradictions,
            }

        # single data agent without news -> pass through its narrative directly
        if len(successful) == 1 and not news_outputs:
            a = successful[0]
            return {
                "answer": a.get("analysis_text", ""),
                "limitations": limitations + a.get("limitations", []),
                "contradictions": contradictions,
            }

        # multi-agent or agent + news -> LLM synthesis over already-RENDERED narratives.
        # The narratives already contain real, validated numbers, so the
        # synthesizer legitimately echoes them. We therefore check that it did
        # not INVENT numbers beyond those present in the agent narratives,
        # instead of rejecting all digits.
        all_outputs = successful + news_outputs
        blocks = []
        for a in all_outputs:
            label = a.get("agent_id", "")
            if label == "catalyst_news":
                label = "Berita & Katalis"
            elif label == "macro_intelligence":
                label = "Makro"
            elif label == "risk_challenger":
                label = "Tantangan Risiko"
            else:
                label = label.replace("_", " ").title()
            blocks.append({
                "agent_id": label,
                "analysis": a.get("analysis_text", ""),
                "status": a.get("status", "success"),
            })

        from backend.utcp import clock
        time_ctx = clock.now_info()["tanggal_id"]
        prompt = prompts.synthesizer_prompt(user_query, blocks, global_facts,
                                            contradictions, time_context=time_ctx)
        res = self.llm.generate(config.SYNTHESIZER_MODEL, prompt)
        answer = res["text"] if res["ok"] else ""

        allowed_numbers = set()
        for a in all_outputs:
            allowed_numbers |= _numbers_in(a.get("analysis_text", ""))
        invented = _numbers_in(answer) - allowed_numbers
        banned = glossary.find_banned(answer)

        if not res["ok"] or invented or banned or not answer.strip():
            # safe fallback: concatenate validated agent narratives with clear labels
            parts = []
            for a in successful:
                label = self._nice(a.get("agent_id"))
                parts.append(f"### {label}\n{a.get('analysis_text','')}")
            if news_outputs:
                for a in news_outputs:
                    parts.append(a.get("analysis_text", ""))
            answer = "\n\n".join(parts)
            if invented:
                limitations.append("sintesis otomatis digantikan gabungan narasi agent "
                                   "(model menambah angka yang tidak bersumber)")
            elif not res["ok"]:
                limitations.append("sintesis otomatis gagal; menampilkan gabungan narasi agent")

        return {
            "answer": answer,
            "limitations": limitations,
            "contradictions": contradictions,
        }

    @staticmethod
    def _nice(agent_id: str) -> str:
        return (agent_id or "").replace("_", " ").title()
