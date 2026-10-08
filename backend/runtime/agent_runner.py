"""Agent Runner (PRD 21 / Output Contract 16).

Executes any agent (base or derived) from its JSON spec, enforcing the full
grounding pipeline:

  resolve tools -> call via UTCP (cached) -> Evidence Store
  -> Identity Lock (overview) -> Fact Ledger (facts_extractor + sanity)
  -> No-Data Gate -> LLM narrative (markers only)
  -> Number Validator (regen up to N) -> Identity/glossary check
  -> render markers -> Agent output contract

Because agents are declarative specs, the SAME runner runs factory-created
derived agents with no new Python (PRD note at end of section 21).
"""
from __future__ import annotations

from config import config
from backend.utcp.registry import ToolRegistry
from backend.utcp.cache import RequestCache
from backend.grounding.evidence_store import EvidenceStore
from backend.grounding.fact_ledger import FactLedger
from backend.grounding import no_data_gate, number_validator, identity_lock, glossary
from backend.llm.ollama import OllamaClient
from backend.llm import prompts
from . import facts_extractor as fx

# Tools whose raw payload is useful to the card UI (price chart, news lists).
# For every other tool we expose evidence metadata only, so /query stays small
# (PRD Web-Cards 9.1 note + risk #2).
PAYLOAD_TOOLS = {
    "get_daily_price", "search_idx_news", "search_web_news",
    "search_macro_news_id", "search_macro_news_global", "get_macro_indicators",
}


def build_evidence_public(store, include_payload_for=PAYLOAD_TOOLS) -> list[dict]:
    """Evidence list for the API: metadata always, payload only for card tools."""
    out = []
    for r in store.all():
        rec = r.to_public()
        if r.tool in include_payload_for and r.result_status == "ok":
            rec["payload"] = r.payload
        out.append(rec)
    return out


# Which report sections each tool-less analysis needs, by capability.
CAPABILITY_SECTIONS = {
    "investment_education": ["overview", "valuation"],
    "fundamental_analysis": ["overview", "valuation", "financials", "dividend"],
    "valuation_analysis": ["overview", "valuation"],
    "risk_analysis": ["overview", "valuation", "financials"],
    "dividend_analysis": ["overview", "dividend"],
}


class AgentRunner:
    def __init__(self, tool_registry: ToolRegistry | None = None,
                 llm: OllamaClient | None = None, debug: bool = False):
        self.tools = tool_registry or ToolRegistry()
        self.llm = llm or OllamaClient()
        self.debug = debug

    def run(self, spec: dict, ticker: str | None, user_query: str, cache: RequestCache,
            shared_identity: identity_lock.Identity | None = None) -> dict:
        agent_id = spec["agent_id"]
        store = EvidenceStore()
        ledger = FactLedger()
        trace = {"tool_calls": [], "evidence": [], "validator": None}

        identity = shared_identity
        sections_needed = self._sections_for(spec)

        # 1. tool execution -> evidence + facts
        for tool in spec.get("tools", []):
            if not self.tools.is_available(tool):
                # still record an error evidence so the gate reflects reality
                resp = self.tools.call(tool, self._args_for(tool, ticker, sections_needed), cache)
                store.add(resp)
                trace["tool_calls"].append({"tool": tool, "status": resp.result_status,
                                            "glyph": resp.status_glyph()})
                continue
            resp = self.tools.call(tool, self._args_for(tool, ticker, sections_needed), cache)
            rec = store.add(resp)
            trace["tool_calls"].append({"tool": tool, "args": resp.args,
                                        "status": resp.result_status, "glyph": resp.status_glyph(),
                                        "evidence_id": rec.evidence_id})
            if resp.is_ok:
                self._extract(spec, tool, resp, rec.evidence_id, ledger, identity)
                # build identity from the first ok report overview
                if identity is None and tool == "get_company_report" and isinstance(resp.data, dict):
                    ov = resp.data.get("overview")
                    if ov:
                        identity = identity_lock.build_identity_from_overview(
                            ticker or "", ov, resp.data.get("company_name"))

        trace["evidence"] = [r.to_public() for r in store.all()]

        # 2. No-Data Gate (PRD 10.2)
        if not no_data_gate.passes(store):
            # Auto-fallback: when the agent's own tools failed/returned nothing,
            # try fetching recent news so the user still gets current context
            # instead of a dead end (user request). Still grounded: headlines
            # come from the news tool, no fabricated numbers.
            news = self._news_fallback(ticker, user_query, cache, store, trace)
            if news is not None:
                return news
            return self._no_data_output(spec, ticker, identity, store, trace)

        # re-extract facts that needed identity (bank metrics) once identity known
        # (handled inline above; identity typically known after overview section)

        # 3. LLM narrative with markers only
        facts_prompt = ledger.facts_for_prompt()
        identity_block = self._identity_block(identity, ticker)
        template_note = self._template_note(identity)
        sys = prompts.agent_system_prompt(spec)
        sections = (spec.get("output_format") or {}).get("sections", ["ringkasan", "keterbatasan"])

        narrative, validator_info = self._generate_validated(
            spec, sys, identity_block, facts_prompt, sections, user_query, ledger, identity)
        trace["validator"] = validator_info

        rendered = ledger.render_markers(narrative)

        facts_public = [f.to_public() for f in ledger.all()]
        confidence = self._confidence(spec, store, ledger)

        return {
            "agent_id": agent_id,
            "agent_version": spec.get("version", "1.0.0"),
            "status": "success" if validator_info.get("passed") else "partial",
            "ticker": ticker,
            "identity": identity.to_public() if identity else None,
            "facts": facts_public,
            "evidence": build_evidence_public(store),
            "analysis_text": rendered,
            "analysis_markers": narrative,
            "key_findings": [],
            "risks": [],
            "limitations": validator_info.get("limitations", []),
            "evidence_ids": store.ok_ids(),
            "confidence": confidence,
            "_trace": trace,
        }

    # -- helpers --------------------------------------------------------------
    def _sections_for(self, spec: dict) -> list[str]:
        secs = []
        for cap in spec.get("capabilities", []):
            for s in CAPABILITY_SECTIONS.get(cap, []):
                if s not in secs:
                    secs.append(s)
        if not secs:
            secs = ["overview", "valuation"]
        # bank focus adds financials
        if spec.get("sector_focus") == "bank" and "financials" not in secs:
            secs.append("financials")
        return secs

    def _args_for(self, tool: str, ticker: str | None, sections: list[str]) -> dict:
        if tool == "get_company_report":
            return {"symbol": ticker, "sections": ",".join(sections)}
        if tool in ("get_daily_price", "get_foreign_flow", "get_company_quarterly",
                    "get_company_corporate_actions", "get_shareholders"):
            return {"symbol": ticker}
        if tool == "search_idx_news":
            return {"symbols": ticker, "limit": 5}
        if tool == "get_filings":
            return {"symbol": ticker, "limit": 5}
        if tool == "get_idx_total":
            return {}
        if tool == "get_index_daily":
            return {"index": "idx30"}
        if tool == "screen_companies":
            return {"where": "market_cap>100000000000000", "order_by": "-market_cap"}
        if tool == "get_macro_indicators":
            return {}
        if tool in ("search_macro_news_id", "search_macro_news_global"):
            return {"limit": 6}
        return {"symbol": ticker}

    def _extract(self, spec, tool, resp, ev_id, ledger, identity):
        # macro indicator facts (inflasi, suku bunga riil, kurs) with source
        if tool == "get_macro_indicators" and isinstance(resp.data, dict):
            fx.extract_macro_indicators(ledger, resp.data, ev_id)
            return
        # news tools provide qualitative context, not numeric facts
        if tool in ("search_macro_news_id", "search_macro_news_global", "search_idx_news"):
            return
        # yfinance-backed tools (Sectors 404 on this tier)
        if tool == "get_company_quarterly" and isinstance(resp.data, dict):
            is_bank = (identity.is_bank() if identity else False) or \
                spec.get("sector_focus") == "bank"
            fx.extract_quarterly(ledger, resp.data, ev_id, is_bank)
            return
        if tool == "get_shareholders" and isinstance(resp.data, dict):
            fx.extract_shareholders(ledger, resp.data, ev_id)
            return
        if tool != "get_company_report" or not isinstance(resp.data, dict):
            return
        is_bank = (identity.is_bank() if identity else False) or spec.get("sector_focus") == "bank"
        # if identity not yet known, infer from this payload's overview
        if not identity:
            ov = resp.data.get("overview") or {}
            sub = (ov.get("sub_sector") or "").lower()
            is_bank = is_bank or ("bank" in sub) or (ov.get("sector", "").lower() == "financials")
        fx.extract_overview(ledger, resp.data, ev_id)
        fx.extract_valuation(ledger, resp.data, ev_id)
        fx.extract_financials(ledger, resp.data, ev_id, is_bank)
        fx.extract_dividend(ledger, resp.data, ev_id)

    def _identity_block(self, identity, ticker) -> str:
        if not identity:
            return f"Simbol: {ticker or '(tidak diketahui)'} (identitas sektor belum tersedia)."
        return (f"Simbol: {identity.symbol}; Nama: {identity.company_name}; "
                f"Sektor: {identity.sector}; Subsektor: {identity.subsector}. "
                f"Template analisis: {identity.template()}.")

    def _template_note(self, identity) -> str:
        if identity and identity.is_bank():
            return ("CATATAN SEKTOR: perusahaan ini adalah BANK. Gunakan kerangka bank "
                    "(kredit, dana pihak ketiga, LDR, profitabilitas). JANGAN memakai "
                    "metrik perusahaan produksi (gross margin, kualitas produk).\n")
        return ""

    def _generate_validated(self, spec, sys, identity_block, facts_prompt, sections,
                            user_query, ledger, identity):
        info = {"passed": False, "attempts": 0, "stray": [], "limitations": [],
                "fallback": False, "identity_violation": [], "banned_terms": []}
        from backend.utcp import clock
        user = prompts.agent_user_prompt(spec, identity_block, facts_prompt, sections,
                                         user_query, self._template_note(identity),
                                         time_context=clock.now_info()["tanggal_id"])
        prompt = user
        max_regen = config.NUMBER_VALIDATOR_MAX_REGEN
        narrative = ""
        for attempt in range(max_regen + 1):
            info["attempts"] = attempt + 1
            res = self.llm.generate(config.AGENT_MODEL, prompt, system=sys)
            if not res["ok"]:
                info["limitations"].append("model tidak dapat dihubungi")
                break
            narrative = res["text"]
            ok_num, stray = number_validator.validate(narrative)
            info["stray"] = stray
            # identity + glossary checks
            viol = identity_lock.check_narrative_against_identity(narrative, identity) if identity else []
            banned = glossary.find_banned(narrative)
            info["identity_violation"] = viol
            info["banned_terms"] = banned
            if ok_num and not viol and not banned:
                info["passed"] = True
                return narrative, info
            # build correction prompt
            corr = []
            if not ok_num:
                corr.append(number_validator.correction_instruction(stray))
            if viol:
                corr.append(f"REVISI: jangan menyebut {viol}; perusahaan ini sektor "
                            f"{identity.sector if identity else ''}.")
            if banned:
                corr.append(f"REVISI: hindari istilah tidak baku {banned}.")
            prompt = user + "\n\n" + "\n".join(corr)

        # fallback: deterministic template (PRD 10.5)
        info["fallback"] = True
        info["limitations"].append("narasi otomatis dinonaktifkan; dipakai tabel fakta deterministik")
        narrative = number_validator.deterministic_template(ledger, identity_block)
        return narrative, info

    def _confidence(self, spec, store, ledger) -> float:
        required = [t for t in spec.get("tools", []) if self.tools.is_available(t)]
        if not required:
            return 0.0
        ok_tools = {r.tool for r in store.ok_records()}
        base = len(ok_tools & set(required)) / len(required)
        anomalies = sum(1 for f in ledger.all() if f.anomaly)
        return round(max(0.0, base - 0.1 * anomalies), 2)

    def _news_fallback(self, ticker, user_query, cache, store, trace):
        """When tools yielded no data, fetch recent news as a grounded fallback.

        Returns a success-with-news output, or None if news is also unavailable.
        """
        query = ticker or user_query
        resp = self.tools.call("search_web_news",
                               {"query": query, "scope": "id", "limit": 6}, cache)
        store.add(resp)
        trace.setdefault("tool_calls", []).append(
            {"tool": "search_web_news", "status": resp.result_status,
             "glyph": resp.status_glyph(), "fallback": True})
        if resp.result_status != "ok" or not resp.data:
            return None
        items = resp.data
        lines = ["Data analisis dari tool utama tidak tersedia, namun berikut "
                 "berita terbaru yang relevan (sumber tertera):", ""]
        for i, it in enumerate(items, 1):
            when = f" — {it['published']}" if it.get("published") else ""
            lines.append(f"{i}. {it['title']} [{it.get('source','')}{when}]")
            if it.get("url"):
                lines.append(f"   {it['url']}")
        return {
            "agent_id": "news_fallback",
            "agent_version": "1.0.0",
            "status": "partial",
            "ticker": ticker,
            "identity": None,
            "facts": [],
            "evidence": build_evidence_public(store),
            "analysis_text": "\n".join(lines),
            "analysis_markers": "",
            "key_findings": [],
            "risks": [],
            "limitations": ["data tool utama tidak tersedia; menggunakan berita terbaru sebagai konteks"],
            "evidence_ids": store.ok_ids(),
            "confidence": 0.2,
            "_trace": trace,
        }

    def _no_data_output(self, spec, ticker, identity, store, trace) -> dict:
        reason = no_data_gate.reason_from_store(store)
        return {
            "agent_id": spec["agent_id"],
            "agent_version": spec.get("version", "1.0.0"),
            "status": "no_data",
            "ticker": ticker,
            "identity": identity.to_public() if identity else None,
            "facts": [],
            "evidence": build_evidence_public(store),
            "analysis_text": f"Data tidak tersedia untuk analisis ini ({reason}). "
                             f"Tidak ada klaim yang dapat dibuat.",
            "analysis_markers": "",
            "key_findings": [],
            "risks": [],
            "limitations": [reason],
            "evidence_ids": [],
            "confidence": 0.0,
            "_trace": trace,
        }
