"""Orchestrator (PRD 7, 8, 14, 16).

Pipeline:
  intent/persona detection -> capability matching -> routing (4 lanes)
  -> [Agent Factory if persona mismatch] -> agent run via A2A
  -> specialist collaboration -> synthesizer -> final answer

Everything is captured in a ``trace`` for --debug and the API. The
orchestrator never writes numbers itself (PRD 8).
"""
from __future__ import annotations

from datetime import datetime

from config import config
from backend.utcp.registry import ToolRegistry
from backend.utcp.cache import RequestCache
from backend.utcp import stock_universe
from backend.llm.ollama import OllamaClient
from backend.llm import prompts
from backend.grounding import number_validator, glossary
from backend.agent_factory.registry import AgentRegistry
from backend.agent_factory.factory import AgentFactory
from backend.agent_factory import lineage as lineage_mod
from backend.runtime.agent_runner import AgentRunner
from backend.a2a.protocol import A2ABus
from backend.specialists.invoker import SpecialistInvoker
from .intent_detector import IntentDetector
from .synthesizer import Synthesizer

MACRO_REFUSAL = (
    "Data BI Rate/inflasi/kurs belum tersedia di sistem ini, sehingga saya tidak dapat "
    "memberikan angkanya. Anda dapat memeriksa situs resmi Bank Indonesia atau BPS. "
    "Secara konseptual (bukan data terkini), penurunan BI Rate umumnya menurunkan biaya "
    "dana bank dan dapat mendorong permintaan kredit."
)


class Orchestrator:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.tools = ToolRegistry()
        self.llm = OllamaClient()
        self.registry = AgentRegistry()
        self.registry.verify_integrity()
        self.factory = AgentFactory(self.registry)
        self.runner = AgentRunner(self.tools, self.llm, debug=debug)
        self.specialists = SpecialistInvoker(self.registry, self.runner)
        self.intent_detector = IntentDetector(self.llm)
        self.synthesizer = Synthesizer(self.llm)

    def handle(self, user_query: str) -> dict:
        trace_id = "tr_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        cache = RequestCache()
        bus = A2ABus(trace_id)
        trace = {"trace_id": trace_id, "user_query": user_query}

        detected = self.intent_detector.detect(user_query)
        trace["detected"] = detected

        result = {
            "status": "success", "trace_id": trace_id,
            "intent": [detected["intent"]], "persona": detected["personas"],
            "ticker": detected.get("ticker"),
            "agents_used": [],
            "agent_factory": {"invoked": False, "base_agents_unchanged": True},
            "tool_calls": [], "answer": "", "limitations": [], "contradictions": [],
            "facts": [], "evidence": [],
            "_trace": trace,
        }

        ticker = detected["ticker"]
        intent = detected["intent"]
        wants_news = detected.get("wants_news", False)

        # --- out-of-scope / general education first --------------------------
        if intent == "general_education":
            return self._run_general_education(user_query, result)
        if intent == "out_of_scope":
            result["answer"] = ("Pertanyaan ini di luar cakupan analisis saham IDX. "
                                "Saya dapat membantu edukasi investasi atau analisis "
                                "emiten IDX (sebutkan kode sahamnya).")
            result["intent"] = ["out_of_scope"]
            return result

        # --- Macro questions: run macro_intelligence with real scraped data --
        q_low = user_query.lower()
        wants_bi_rate = "bi rate" in q_low or "bi-rate" in q_low or "suku bunga acuan" in q_low

        # CRITICAL FIX: if a ticker is present alongside macro request,
        # this is a COMBINED query (fundamental + macro context), NOT pure macro.
        # Pure macro route is only for ticker-less macro questions.
        if detected["needs_macro_numbers"] and ticker:
            # Route to multi_analysis; macro will run as one of the agents.
            intent = "multi_analysis"
            wants_news = True  # also pull news/macro context
        elif intent == "macro" or detected["needs_macro_numbers"]:
            return self._run_macro(user_query, result, cache, bus, wants_bi_rate)

        # --- News search lane: free-form news query (NO ticker, scrape results) ---
        if intent == "news_search" and not ticker:
            return self._run_news_search(user_query, result, cache,
                                         detected.get("news_scope", "id"), ticker)

        # --- Simple lane: direct price (PRD 14 T1) ---------------------------
        if intent == "price" and ticker:
            return self._run_single_spec("investment_guide", ticker, user_query,
                                         result, cache, bus, override_tools=["get_daily_price"])

        # --- No ticker but needs company data --------------------------------
        if not ticker:
            unknown = stock_universe.unknown_ticker_like(detected.get("ticker"), user_query)
            if unknown:
                result["status"] = "error"
                result["answer"] = (
                    f"Kode saham '{unknown}' tidak terdaftar di daftar saham IDX "
                    f"(diperiksa dari basis data lokal, {stock_universe.count()} emiten). "
                    f"Pastikan kodenya benar, misalnya BBCA, BBRI, atau TLKM.")
                result["limitations"] = [f"{unknown}: tidak ada di universe IDX"]
                return result
            result["answer"] = (
                "Pertanyaan ini sepertinya memerlukan data perusahaan tertentu, "
                "namun saya belum menemukan kode saham IDX pada pertanyaan Anda. "
                "Sebutkan kodenya (misalnya BBCA, BBRI, TLKM) agar saya dapat "
                "mengambil datanya. Untuk pertanyaan umum seperti \"apa itu EPS\", "
                "Anda bisa menanyakannya langsung tanpa kode saham.")
            result["limitations"] = ["kode saham IDX tidak terdeteksi"]
            return result

        # --- Ticker existence gate (PRD T19) via LOCAL CSV (no API cost) -----
        if not stock_universe.exists(ticker):
            result["status"] = "error"
            result["answer"] = (f"Kode saham '{ticker}' tidak terdaftar di daftar saham "
                                f"IDX (diperiksa dari basis data lokal). Analisis tidak "
                                f"dapat dilakukan untuk ticker yang tidak ada.")
            result["limitations"] = [f"{ticker}: tidak ada di universe IDX ({stock_universe.count()} emiten)"]
            return result

        # --- Decide: existing agent / factory / reuse ------------------------
        personas = detected["personas"] or self._default_personas(intent)
        capabilities = detected["capabilities"] or self._default_caps(intent)
        modifiers = detected["modifiers"]

        decision = self.factory.decide(personas, capabilities, modifiers, user_query)
        trace["factory_decision"] = decision.to_public()

        if decision.action == "use_existing":
            agent_id = decision.agent_id
        elif decision.action == "reuse":
            agent_id = decision.agent_id
            self.registry.bump_use_count(agent_id)
            result["agent_factory"] = {"invoked": True, "operation": "reuse", "reused": True,
                                       "new_agent_id": agent_id, "version": decision.version,
                                       "parents": self._parents_str(self.registry.get(agent_id)),
                                       "base_agents_unchanged": True}
        elif decision.action == "fallback":
            agent_id = (decision.parent_ids[0] if getattr(decision, "parent_ids", None)
                        else "fundamental_analyst")
            result["limitations"].append("Agent Factory fallback: menjalankan agent induk")
        else:
            # compose / modify / compose_modify -> create derived agent
            create = self.factory.create(decision, personas, capabilities, modifiers, user_query)
            trace["factory_create"] = {k: create[k] for k in
                                       ("ok", "operation", "errors", "validations", "override_notes")}
            if create["ok"]:
                agent_id = create["spec"]["agent_id"]
                result["agent_factory"] = {
                    "invoked": True, "operation": create["operation"], "reused": False,
                    "new_agent_id": agent_id, "version": create["spec"]["version"],
                    "parents": self._parents_str(create["spec"]),
                    "validations": create["validations"],
                    "base_agents_unchanged": True,
                    "lineage_render": lineage_mod.render(create["spec"]),
                }
            else:
                # validation/smoke failed -> fallback to a parent (PRD 9.4)
                agent_id = decision.parent_ids[0]
                result["agent_factory"] = {"invoked": True, "operation": create["operation"],
                                           "reused": False, "failed": True,
                                           "errors": create["errors"],
                                           "base_agents_unchanged": True}
                result["limitations"].append(
                    "Agent Factory gagal validasi; menjalankan agent induk: " + agent_id)

        # --- Run the chosen agent + optional specialist collaboration --------
        return self._run_with_collaboration(agent_id, ticker, user_query, result, cache, bus,
                                            intent, wants_news=wants_news)

    # -- running --------------------------------------------------------------
    def _run_news_search(self, user_query, result, cache, scope, ticker):
        """Free-form news search (no ticker): scrape results, present grounded headlines.

        When a ticker IS present, this method should NOT be called — use
        _run_with_collaboration with wants_news=True instead.

        Headlines/sources/links are real (from the tool). An optional LLM
        summary is validated so it adds no fabricated numbers; otherwise we
        present the headline list deterministically.
        """
        result["intent"] = ["news_search"]
        result["agents_used"] = ["news_sentiment"]

        # Build a focused search query: if ticker present, use that; otherwise raw query
        search_query = ticker if ticker else user_query
        resp = self.tools.call("search_web_news",
                               {"query": search_query, "scope": scope, "limit": 8}, cache)
        self._finalize_tools(result, cache)

        if resp.result_status != "ok" or not resp.data:
            result["status"] = "no_data"
            result["answer"] = ("Tidak ada hasil berita yang dapat diambil untuk permintaan "
                                "ini saat ini. Silakan coba kata kunci lain.")
            result["limitations"] = [f"search_web_news: {resp.result_status}"]
            return result

        items = resp.data
        # Deterministic, grounded list of real headlines.
        lines = ["Berikut berita yang ditemukan (sumber tertera):", ""]
        for i, it in enumerate(items, 1):
            when = f" — {it['published']}" if it.get("published") else ""
            lines.append(f"{i}. {it['title']} [{it.get('source','')}{when}]")
            if it.get("summary"):
                lines.append(f"   {it['summary'][:160]}")
            if it.get("url"):
                lines.append(f"   {it['url']}")
        headline_block = "\n".join(lines)

        # Optional short LLM overview (qualitative, no numbers), validated.
        titles = "\n".join(f"- {it['title']}" for it in items[:8])
        prompt = (
            "Anda merangkum sekumpulan judul berita untuk pengguna. "
            "DILARANG menulis angka apa pun dan DILARANG menambah fakta di luar judul. "
            "Buat 2-3 kalimat ringkas Bahasa Indonesia tentang tema umum berita berikut, "
            "lalu akhiri dengan mengingatkan pengguna memeriksa tautan sumber.\n\n"
            f"PERMINTAAN: {user_query}\n\nJUDUL:\n{titles}"
        )
        res = self.llm.generate(config.AGENT_MODEL, prompt)
        overview = res["text"] if res["ok"] else ""
        ok_num, _ = number_validator.validate(overview)
        if res["ok"] and ok_num and overview.strip():
            answer = overview.strip() + "\n\n" + headline_block
        else:
            answer = headline_block
            result["limitations"].append("ringkasan otomatis dilewati; menampilkan daftar judul apa adanya")

        result["answer"] = answer
        result["status"] = "success"
        result["_trace"]["news_items"] = len(items)
        return result

    def _run_macro(self, user_query, result, cache, bus, wants_bi_rate):
        """Macro lane: real scraped indicators + macro news (no ticker needed)."""
        result["intent"] = ["macro"]
        spec = dict(self.registry.get("macro_intelligence"))
        # restrict to ticker-less macro tools for a pure macro question
        spec["tools"] = ["get_macro_indicators", "search_macro_news_id",
                         "search_macro_news_global"]
        out = self.runner.run(spec, None, user_query, cache)
        result["agents_used"] = ["macro_intelligence"]

        syn = self.synthesizer.synthesize(user_query, [out], out.get("facts", []))
        answer = syn["answer"]
        limitations = list(syn["limitations"])

        if wants_bi_rate:
            answer = (answer + "\n\nCatatan BI Rate: angka BI Rate tidak diambil dari "
                      "sumber terverifikasi di sistem ini, sehingga tidak ditampilkan. "
                      "Silakan cek situs resmi Bank Indonesia (bi.go.id) untuk angka terkini.")
            limitations.append("BI Rate: tidak tersedia dari sumber terverifikasi")

        result["answer"] = answer
        result["limitations"] += limitations
        result["contradictions"] = syn["contradictions"]
        result["status"] = out.get("status", "success")
        result["_trace"]["agent_outputs"] = [self._slim(out)]
        self._finalize_tools(result, cache)
        return result

    def _run_general_education(self, user_query, result):
        """Answer a concept/definition question directly (no tool, no API).

        Still passes the output through the Number Validator so the LLM cannot
        fabricate specific figures; falls back to a safe message if it does.
        """
        result["intent"] = ["general_education"]
        result["agents_used"] = ["investment_guide"]
        res = self.llm.generate(config.AGENT_MODEL,
                                prompts.general_education_prompt(user_query))
        answer = res["text"] if res["ok"] else ""
        ok_num, stray = number_validator.validate(answer)
        banned = glossary.find_banned(answer)
        if not res["ok"] or not ok_num or banned:
            # retry once asking to avoid specific numbers
            if res["ok"]:
                corr = (prompts.general_education_prompt(user_query) +
                        "\n\nREVISI: jangan menulis angka spesifik apa pun; jelaskan "
                        "konsep saja.")
                res2 = self.llm.generate(config.AGENT_MODEL, corr)
                if res2["ok"]:
                    ok2, _ = number_validator.validate(res2["text"])
                    if ok2 and not glossary.find_banned(res2["text"]):
                        answer = res2["text"]
                        ok_num = True
        if not answer or not ok_num:
            answer = ("Pertanyaan edukasi umum. Saya tidak dapat menyusun penjelasan "
                      "yang memenuhi aturan grounding saat ini. Silakan ajukan ulang "
                      "atau sebutkan kode saham IDX untuk analisis berbasis data.")
            result["limitations"].append("penjelasan konseptual tidak lolos validasi angka")
        result["answer"] = answer
        result["_trace"]["mode"] = "general_education"
        return result

    def _run_single_spec(self, agent_id, ticker, user_query, result, cache, bus,
                         override_tools=None):
        spec = dict(self.registry.get(agent_id))
        if override_tools:
            spec["tools"] = override_tools
        out = self.runner.run(spec, ticker, user_query, cache)
        result["agents_used"] = [agent_id]
        syn = self.synthesizer.synthesize(user_query, [out], out.get("facts", []))
        result["answer"] = syn["answer"]
        result["limitations"] += syn["limitations"]
        result["contradictions"] = syn["contradictions"]
        result["status"] = out.get("status", "success")
        result["_trace"]["agent_outputs"] = [self._slim(out)]
        self._finalize_tools(result, cache)
        return result

    def _run_with_collaboration(self, agent_id, ticker, user_query, result, cache, bus,
                                intent, wants_news: bool = False):
        spec = self.registry.get(agent_id)
        primary = self.runner.run(spec, ticker, user_query, cache)
        result["agents_used"] = [agent_id]
        agent_outputs = [primary]
        identity = None
        if primary.get("identity"):
            from backend.grounding.identity_lock import Identity
            idd = primary["identity"]
            identity = Identity(**{k: idd.get(k) for k in
                                   ("symbol", "company_name", "sector", "subsector", "source")})

        # multi-analysis: add macro + risk specialist via A2A (PRD T5)
        if intent == "multi_analysis" and primary.get("status") != "no_data":
            # macro market-proxy agent
            macro_spec = self.registry.get("macro_intelligence")
            macro_out = self.runner.run(macro_spec, ticker, user_query, cache)
            agent_outputs.append(macro_out)
            result["agents_used"].append("macro_intelligence")
            # risk challenger specialist via A2A
            resp = self.specialists.call("risk_challenger", agent_id, ticker, user_query,
                                         bus, cache, shared_identity=identity)
            if resp.get("result", {}).get("_agent_output"):
                agent_outputs.append(resp["result"]["_agent_output"])
                result["agents_used"].append("risk_challenger")

        # catalyst/news lane: when user explicitly wants news context for a ticker,
        # fetch relevant news using the ticker symbol so results are on-target.
        if wants_news:
            news_out = self._fetch_stock_news(ticker, user_query, cache, agent_outputs)
            if news_out:
                agent_outputs.append(news_out)
                result["agents_used"].append("catalyst_news")

        global_facts = []
        for a in agent_outputs:
            global_facts += a.get("facts", [])
        syn = self.synthesizer.synthesize(user_query, agent_outputs, global_facts)
        result["answer"] = syn["answer"]
        result["limitations"] += syn["limitations"]
        result["contradictions"] = syn["contradictions"]
        result["status"] = primary.get("status", "success")
        result["_trace"]["agent_outputs"] = [self._slim(a) for a in agent_outputs]
        result["_trace"]["a2a"] = bus.debug_dump()
        self._finalize_tools(result, cache)
        return result

    def _fetch_stock_news(self, ticker: str, user_query: str,
                          cache: RequestCache, existing_outputs: list) -> dict | None:
        """Fetch news specifically about the ticker and return as an agent-like output.

        The news items are real and grounded (from the news tool). This output
        is passed to the synthesizer so it can integrate catalyst/news context
        with the fundamental analysis narrative.
        """
        # Use the Sectors IDX news API first (topic-specific), then fallback to web news
        idx_resp = self.tools.call("search_idx_news",
                                   {"symbols": ticker, "limit": 6}, cache)
        web_resp = self.tools.call("search_web_news",
                                   {"query": ticker, "scope": "id", "limit": 6}, cache)

        news_items = []
        if idx_resp.result_status == "ok" and isinstance(idx_resp.data, list):
            for item in idx_resp.data:
                if isinstance(item, dict):
                    news_items.append({
                        "title": item.get("title", ""),
                        "source": item.get("source", "IDX News"),
                        "published": item.get("created_at", item.get("date", "")),
                        "url": item.get("link", item.get("url", "")),
                        "summary": item.get("body", item.get("summary", ""))[:200],
                    })

        if web_resp.result_status == "ok" and isinstance(web_resp.data, list):
            for item in web_resp.data:
                if isinstance(item, dict) and item.get("title"):
                    # Deduplicate by title similarity
                    if not any(item["title"] in n["title"] or n["title"] in item["title"]
                               for n in news_items):
                        news_items.append(item)

        if not news_items:
            return None

        # Build a news summary block (deterministic, grounded)
        lines = [f"## Berita & Katalis Terkini untuk {ticker}", ""]
        for i, it in enumerate(news_items[:8], 1):
            when = f" — {it.get('published', '')}" if it.get("published") else ""
            source = it.get("source", "")
            lines.append(f"{i}. **{it['title']}** [{source}{when}]")
            if it.get("summary"):
                lines.append(f"   {it['summary'][:200]}")
            if it.get("url"):
                lines.append(f"   {it['url']}")
        news_block = "\n".join(lines)

        return {
            "agent_id": "catalyst_news",
            "agent_version": "1.0.0",
            "status": "success",
            "ticker": ticker,
            "identity": None,
            "facts": [],
            "analysis_text": news_block,
            "analysis_markers": "",
            "key_findings": [],
            "risks": [],
            "limitations": [],
            "evidence_ids": [],
            "confidence": 1.0,
            "_trace": {"source": "news_tool"},
        }

    def _finalize_tools(self, result, cache):
        result["tool_calls"] = [{"tool": r.tool, "args": r.args, "result_status": r.result_status,
                                 "glyph": r.status_glyph()} for r in cache.all_calls()]
        result["_trace"]["cache_stats"] = cache.stats()
        result["_trace"]["duplicate_tool_calls"] = cache.has_duplicates()
        self._expose_facts_evidence(result, cache)

    # -- W0: expose facts + evidence for the card UI (PRD Web-Cards 9.1) -----
    def _expose_facts_evidence(self, result, cache):
        """Attach de-duplicated global facts and tool evidence to the response.

        * facts: merged from every agent output in the trace (already public
          dicts with evidence_id/as_of/source).
        * evidence: one record per tool call from the request cache; raw payload
          is included only for card tools (price chart, news, macro) to keep the
          response small.
        """
        from backend.runtime.agent_runner import PAYLOAD_TOOLS

        # --- facts (de-duplicated on fact_id, then on metric/value/as_of) ----
        seen_fid, seen_key, facts = set(), set(), []
        for out in result["_trace"].get("agent_outputs", []):
            for f in out.get("facts", []):
                fid = f.get("fact_id")
                key = (f.get("metric"), f.get("value"), f.get("unit"), f.get("as_of"))
                if fid in seen_fid or key in seen_key:
                    continue
                seen_fid.add(fid)
                seen_key.add(key)
                # attach a human source label if missing (field_path origin)
                if "source" not in f:
                    f = {**f, "source": self._source_label(f.get("field_path"))}
                facts.append(f)
        result["facts"] = facts

        # --- evidence (metadata always, payload only for card tools) ---------
        evidence = []
        for r in cache.all_calls():
            rec = {
                "evidence_id": None,  # per-request cache has no global ev id
                "tool": r.tool,
                "args": r.args,
                "result_status": r.result_status,
                "http_status": r.http_status,
                "fetched_at": r.fetched_at,
                "payload_sha256": r.payload_sha256[:12],
            }
            if r.tool in PAYLOAD_TOOLS and r.result_status == "ok":
                rec["payload"] = r.data
            evidence.append(rec)
        result["evidence"] = evidence

    @staticmethod
    def _source_label(field_path: str | None) -> str:
        if not field_path:
            return "Sectors"
        fp = field_path.lower()
        if fp.startswith("yfinance"):
            return "Yahoo Finance"
        if fp.startswith("get_macro_indicators") or "macro" in fp:
            return "Makro (BPS/World Bank)"
        if fp.startswith("daily"):
            return "Sectors (harga harian)"
        return "Sectors"

    # -- helpers --------------------------------------------------------------
    def _slim(self, out: dict) -> dict:
        return {k: out[k] for k in ("agent_id", "status", "confidence", "identity",
                                    "evidence_ids", "limitations") if k in out} | {
            "facts": [{"fact_id": f["fact_id"], "metric": f["metric"],
                       "value": f["value"], "unit": f["unit"], "evidence_id": f["evidence_id"]}
                      for f in out.get("facts", [])],
            "analysis_text": out.get("analysis_text", ""),
            "tool_calls": out.get("_trace", {}).get("tool_calls", []),
            "validator": out.get("_trace", {}).get("validator"),
        }

    def _parents_str(self, spec) -> list[str]:
        if not spec:
            return []
        return [f"{p['agent_id']}@{p.get('version','1.0.0')}"
                for p in (spec.get("lineage", {}) or {}).get("parents", [])]

    def _default_personas(self, intent) -> list[str]:
        return {"fundamental": ["fundamental_investor"], "education": ["complete_beginner"],
                "macro": ["macro_strategist"], "multi_analysis": ["fundamental_investor"],
                "single_metric": ["fundamental_investor"]}.get(intent, ["fundamental_investor"])

    def _default_caps(self, intent) -> list[str]:
        return {"fundamental": ["fundamental_analysis", "valuation_analysis"],
                "education": ["investment_education"],
                "macro": ["macro_analysis"],
                "multi_analysis": ["fundamental_analysis", "risk_analysis", "catalyst_analysis"],
                "single_metric": ["valuation_analysis"]}.get(intent, ["fundamental_analysis"])
