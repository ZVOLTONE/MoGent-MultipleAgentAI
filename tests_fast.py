#!/usr/bin/env python3
"""Fast verification suite for AISector-MoGent (subset of PRD section 20).

Covers the deterministic test cases that do not need slow LLM generation:
  T12, T13, T15, T16 (factory safety)
  T17 (identity lock), T19 (fake ticker gate), T21 (no duplicate tool calls),
  T22 (number validator), plus T10 (base agents unchanged).

LLM-dependent narrative tests (T1-T8 full answers) are exercised by the CLI
and API manually; here we check the grounding machinery that guarantees them.

Run: python tests_fast.py
"""
from __future__ import annotations

import sys

from backend.agent_factory.registry import AgentRegistry, IntegrityError
from backend.agent_factory.factory import AgentFactory
from backend.agent_factory import validator, smoke_test
from backend.grounding import number_validator, identity_lock, sanity_checks
from backend.grounding.evidence_store import EvidenceStore
from backend.grounding import no_data_gate
from backend.utcp.registry import ToolRegistry
from backend.utcp.cache import RequestCache

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{PASS if cond else FAIL}] {name}" + (f"  ({detail})" if detail else ""))


def main():
    reg = AgentRegistry()
    reg.verify_integrity()
    fac = AgentFactory(reg)

    print("T10: base agents unchanged / present")
    check("9 base agents present", len(reg.base_agents()) == 9, f"{len(reg.base_agents())}")
    check("all base immutable", all(s.get("immutable") for s in reg.base_agents()))

    print("T12: tool outside whitelist rejected")
    iv, wg = reg.get("investment_guide"), reg.get("wealth_guardian")
    bad = {"agent_id": "x", "version": "1.0.0", "kind": "derived", "status": "active",
           "personas": ["x"], "capabilities": ["x"],
           "tools": ["get_company_report", "search_idx_news"],
           "output_format": {}, "locked_constraints": iv["locked_constraints"],
           "lineage": {"parents": []}}
    errs = validator.validate_derived(bad, [iv, wg])
    check("rejects out-of-whitelist tool", any("whitelist" in e for e in errs), str(errs))

    print("T13: locked constraint removal rejected")
    bad2 = dict(bad); bad2["tools"] = ["get_company_report"]; bad2["locked_constraints"] = ["GROUNDING_V1"]
    errs2 = validator.validate_derived(bad2, [iv, wg])
    check("rejects locked_constraints reduction", any("locked_constraints" in e for e in errs2))

    print("T16: smoke test returns no_data on empty data")
    passed, detail = smoke_test.run(bad2)
    check("smoke test passes (no_data behaviour)", passed, detail)

    print("No-Data Gate: empty store blocks LLM")
    check("empty store -> gate fails", not no_data_gate.passes(EvidenceStore()))

    print("T22: number validator")
    for bad_num in ["PER 15.3", "harga 6100", "PER 12.806.979.354", "yield 5%", "22x"]:
        ok, stray = number_validator.validate(bad_num)
        check(f"rejects '{bad_num}'", (not ok) and len(stray) > 0, str(stray))
    for good in ["PER {{f_003}} tahun 2025", "Ada 2 hal utama", "3 poin:"]:
        ok, _ = number_validator.validate(good)
        check(f"allows '{good}'", ok)

    print("T17: identity lock contradiction detection (BBCA=bank)")
    idn = identity_lock.build_identity_from_overview(
        "BBCA", {"sector": "Financials", "sub_sector": "Banks"}, "PT Bank Central Asia Tbk.")
    check("BBCA detected as bank", idn.is_bank() and idn.template() == "bank")
    hits = identity_lock.check_narrative_against_identity("BBCA bergerak di sektor pertanian sawit", idn)
    check("detects 'pertanian/sawit' contradiction", "pertanian" in hits)
    clean = identity_lock.check_narrative_against_identity("BBCA adalah bank dengan laba kuat", idn)
    check("clean bank narrative passes", clean == [])

    print("sanity: UAT anomaly flagged")
    anom, _ = sanity_checks.check("pe_ratio", 12806979354)
    check("flags PER=12.8B as anomaly", anom)

    print("T19: fake ticker gate (local CSV, no API)")
    from backend.utcp import stock_universe as su
    check("CSV universe loaded", su.is_loaded(), f"{su.count()} emiten")
    check("BBCA exists in universe", su.exists("BBCA"))
    check("ZZZZ not in universe", not su.exists("ZZZZ"))
    check("'EPS' treated as non-ticker", su.resolve_ticker(None, "apa itu EPS") is None)
    check("resolves BBCA from text", su.resolve_ticker(None, "fundamental BBCA") == "BBCA")
    check("flags unknown ticker-like ZZZZ",
          su.unknown_ticker_like(None, "analisis ZZZZ") == "ZZZZ")

    print("T21: per-request cache dedup (live API)")
    tools = ToolRegistry()
    c2 = RequestCache()
    tools.call("get_company_report", {"symbol": "BBCA", "sections": "overview"}, c2)
    tools.call("get_company_report", {"symbol": "BBCA", "sections": "overview"}, c2)
    check("no duplicate unique calls", not c2.has_duplicates() and c2.stats()["unique_calls"] == 1,
          str(c2.stats()))

    print("T15: hash integrity (simulated check)")
    # verify_integrity already ran at load without error for pristine base
    try:
        reg.verify_integrity()
        check("pristine base passes integrity", True)
    except IntegrityError:
        check("pristine base passes integrity", False)

    print("\nFactory create (compose+modify) end-to-end (no LLM):")
    import os, glob
    for f in glob.glob("data/agents/derived/*.json"):
        os.remove(f)
    if os.path.exists("data/agents/registry.json"):
        os.remove("data/agents/registry.json")
    reg2 = AgentRegistry(); reg2.verify_integrity(); fac2 = AgentFactory(reg2)
    d = fac2.decide(["complete_beginner", "wealth_preservation"],
                    ["investment_education", "risk_analysis"], ["simple_language"], "demo")
    res = fac2.create(d, ["complete_beginner", "wealth_preservation"],
                      ["investment_education", "risk_analysis"], ["simple_language"], "demo")
    check("factory creates derived agent", res["ok"], res.get("operation"))
    check("all validations pass", all(res["validations"].values()), str(res["validations"]))
    check("language_level=simple applied",
          res["spec"]["output_format"]["language_level"] == "simple")
    # reuse
    d2 = fac2.decide(["complete_beginner", "wealth_preservation"],
                     ["investment_education", "risk_analysis"], ["simple_language"], "demo again")
    check("REUSE on repeat (no duplicate)", d2.action == "reuse", d2.action)
    check("base still 9 after factory", len(reg2.base_agents()) == 9)

    print("\nMacro scraper tools (public keyless sources):")
    from backend.utcp import macro_scraper as ms
    ind = ms.fetch_macro_indicators()
    names = {i["name"] for i in ind["indicators"]}
    check("inflation indicator sourced", "inflation_annual" in names,
          f"{len(ind['indicators'])} indikator")
    check("usd_idr indicator sourced", "usd_idr" in names)
    check("BI Rate honestly unavailable", "bi_rate" in ind["unavailable"])
    check("every indicator has source+as_of",
          all(i.get("source") and i.get("as_of") is not None for i in ind["indicators"]))
    news_id = ms.fetch_macro_news_id(limit=3)
    check("macro news ID fetched", bool(news_id), f"{len(news_id or [])} item")
    news_g = ms.fetch_macro_news_global(limit=3)
    check("macro news global fetched", bool(news_g), f"{len(news_g or [])} item")
    tools_m = ToolRegistry(); cm = RequestCache()
    rm = tools_m.call("get_macro_indicators", {}, cm)
    check("get_macro_indicators tool -> ok", rm.result_status == "ok")

    print("\nBPS source + versatile news search:")
    check("BPS key-optional (fallback to World Bank when no key)",
          (ms.fetch_bps_inflation() is None) == (not __import__("config").config.BPS_API_KEY))
    gen = ms.search_general_news("harga emas", scope="id", limit=4)
    check("general news search (id) returns results", bool(gen), f"{len(gen or [])} item")
    check("news items carry source", all(x.get("source") for x in (gen or [])))
    glob = ms.search_general_news("federal reserve", scope="global", limit=3)
    check("general news search (global) returns results", bool(glob), f"{len(glob or [])} item")
    rw = tools_m.call("search_web_news", {"query": "harga emas", "scope": "id", "limit": 4}, cm)
    check("search_web_news tool -> ok", rw.result_status == "ok", f"{len(rw.data or [])} item")

    print("\nTime tool + fact de-duplication + news fallback:")
    rt = tools_m.call("get_time", {}, cm)
    check("get_time tool -> ok", rt.result_status == "ok",
          rt.data.get("tanggal_id") if rt.data else "")
    check("get_time has date+year+tz",
          all(k in (rt.data or {}) for k in ("date_wib", "year", "timezone")))

    from backend.grounding.fact_ledger import FactLedger
    L = FactLedger()
    f1 = L.add("last_close_price", 6100, "idr", evidence_id="ev_0001", as_of="2026-10-02")
    f2 = L.add("last_close_price", 6100, "idr", evidence_id="ev_0002", as_of="2026-10-02")
    f3 = L.add("last_close_price", 6075, "idr", evidence_id="ev_0003", as_of="2026-09-30")
    check("duplicate fact collapsed to same id", f1.fact_id == f2.fact_id, f"{f1.fact_id}=={f2.fact_id}")
    check("distinct fact kept separate", f3.fact_id != f1.fact_id)
    check("ledger has 2 unique facts, not 3", len(L.all()) == 2, str(len(L.all())))

    # news auto-fallback when primary tools fail (empty Sectors API key).
    # Use investment_guide: its only tool is get_company_report (Sectors-only),
    # so an empty Sectors key forces the No-Data Gate -> news fallback.
    # (fundamental_analyst now also has yfinance-backed quarterly/shareholders
    #  tools that do NOT depend on the Sectors key, so it stays resilient.)
    from backend.utcp.client import SectorsClient
    from backend.runtime.agent_runner import AgentRunner
    from backend.agent_factory.registry import AgentRegistry as AR2
    reg3 = AR2()
    broken_tools = ToolRegistry(SectorsClient(api_key=""))
    runner_fb = AgentRunner(tool_registry=broken_tools)
    out_fb = runner_fb.run(reg3.get("investment_guide"), "BBCA", "analisis BBCA", RequestCache())
    check("news fallback on tool failure", out_fb["agent_id"] == "news_fallback",
          out_fb.get("status"))

    # yfinance replacement for Sectors 404 endpoints -----------------------
    print("\nyfinance replacement (Sectors 404 -> Yahoo Finance):")
    from backend.utcp import yf_client
    from backend.runtime import facts_extractor as fx2
    from backend.grounding.fact_ledger import FactLedger as FL2
    reg_yf = ToolRegistry()
    check("get_company_quarterly now available", reg_yf.is_available("get_company_quarterly"))
    check("get_shareholders now available", reg_yf.is_available("get_shareholders"))
    check("yfinance library importable", yf_client.available())

    cq = reg_yf.call("get_company_quarterly", {"symbol": "BBCA"}, RequestCache())
    check("quarterly via yfinance -> ok", cq.result_status == "ok", cq.result_status)
    if cq.is_ok:
        check("quarterly carries Yahoo Finance source",
              "Yahoo Finance" in (cq.data or {}).get("source", ""))
        Lq = FL2()
        ids = fx2.extract_quarterly(Lq, cq.data, "ev_q", is_bank=True)
        check("quarterly facts extracted with source", len(ids) > 0, f"{len(ids)} fakta")
        check("quarterly facts not anomalous", all(not f.anomaly for f in Lq.all()))

    sh = reg_yf.call("get_shareholders", {"symbol": "BBCA"}, RequestCache())
    check("shareholders via yfinance -> ok", sh.result_status == "ok", sh.result_status)
    if sh.is_ok:
        Ls = FL2()
        ids2 = fx2.extract_shareholders(Ls, sh.data, "ev_s")
        check("shareholders facts extracted", len(ids2) > 0, f"{len(ids2)} fakta")
        check("ownership % within 0-100 (no anomaly)", all(not f.anomaly for f in Ls.all()))

    # -- Web-Cards: Presentation Composer + card_builder (W-T1..W-T10) -------
    print("\nWeb-Cards (Presentation Composer + card builder):")
    from backend.presentation import card_builder as cb
    from backend.agent_factory import merge_rules as mr
    pc = reg.get("presentation_composer")
    check("presentation_composer is base", pc is not None and pc.get("kind") == "base")
    check("presentation_composer has presentation block", bool(pc and pc.get("presentation")))

    card_result = {
        "ticker": "BBCA", "answer": "Ringkasan: BBCA adalah bank. LDR 78,34% tinggi. "
        "Tidak terdapat kontradiksi dalam narasi agent. Risiko: sensitivitas valuasi.",
        "agents_used": ["fundamental_analyst"], "agent_factory": {"invoked": False},
        "tool_calls": [{"tool": "get_company_report", "result_status": "ok", "glyph": "ok"},
                       {"tool": "get_shareholders", "result_status": "error", "glyph": "x"}],
        "limitations": ["NIM tidak tersedia"], "contradictions": [],
        "facts": [
            {"fact_id": "f_001", "metric": "last_close_price", "value": 10200, "unit": "idr",
             "as_of": "2026-09-30", "evidence_id": "ev_1", "field_path": "overview.last_close_price",
             "derived": False, "anomaly": False, "source": "Sectors"},
            {"fact_id": "f_002", "metric": "ldr", "value": 78.34, "unit": "%", "as_of": "2025",
             "evidence_id": "ev_1", "field_path": "financials", "derived": True, "anomaly": False,
             "source": "Sectors"},
            {"fact_id": "f_003", "metric": "ldr", "value": 78.34, "unit": "%", "as_of": "2025",
             "evidence_id": "ev_1", "field_path": "financials", "derived": True, "anomaly": False,
             "source": "Sectors"},
            {"fact_id": "f_004", "metric": "pe_ratio", "value": 1.28e10, "unit": "x", "as_of": "2025",
             "evidence_id": "ev_1", "field_path": "valuation.pe", "derived": False, "anomaly": True,
             "source": "Sectors"},
        ],
        "evidence": [{"tool": "get_daily_price", "result_status": "ok",
                      "payload": [{"date": f"2026-09-0{i}", "close": 10000 + i * 20}
                                  for i in range(1, 9)]}],
        "_trace": {"agent_outputs": [{"identity": {"company_name": "Bank Central Asia",
                                                   "sector": "Financials", "subsector": "Banks"},
                                      "facts": []}]},
    }
    cards = cb.build_cards(card_result, pc)
    ids = [c["id"] for c in cards["cards"]]
    check("W-T1 trace card is last", ids[-1] == "trace")
    perf = next((c for c in cards["cards"] if c["id"] == "performance"), None)
    ldr_ct = sum(1 for f in (perf["facts"] if perf else []) if f["label"].startswith("LDR"))
    check("W-T2 duplicate LDR collapsed to 1", ldr_ct <= 1, f"{ldr_ct}")
    trace = cards["cards"][-1]
    check("W-T4 anomaly in trace not as number",
          any("anomali" in b.lower() for b in trace["bullets"]))
    check("W-T5 failed tool listed in trace",
          any(it["title"] == "get_shareholders" for it in trace["items"]))
    summ = next((c for c in cards["cards"] if c["id"] == "summary"), None)
    leak = any(("tinggi" in b.lower() or "kontradiksi" in b.lower())
               for b in (summ["bullets"] if summ else []))
    check("W-T7/W-T8 no judgement/meta leak into bullets", not leak)
    check("W-T9 chart built (>=5 points)", "chart" in ids)

    # W-T6: no structured facts -> summary + risk + trace from text
    cards_txt = cb.build_cards({"ticker": "BBCA", "answer": "Analisis. Risiko: fluktuasi.",
                                "agents_used": ["x"], "agent_factory": {}, "tool_calls": [],
                                "limitations": [], "contradictions": [], "facts": [],
                                "evidence": [], "_trace": {"agent_outputs": []}}, pc)
    check("W-T6 text-only still yields trace", cards_txt["cards"][-1]["id"] == "trace")

    # W-T10: derived card_order without trace rejected; max_facts>8 rejected
    base_body = {"personas": list(pc["personas"]), "capabilities": list(pc["capabilities"]),
                 "tools": [], "constraints": [], "locked_constraints": list(pc["locked_constraints"]),
                 "priority_order": [], "reasoning_style": {"primary": "", "secondary": []},
                 "output_format": dict(pc["output_format"]), "collaboration": {"may_call": []},
                 "presentation": dict(pc["presentation"])}
    bad = {"agent_id": "derived_cards_bad", "version": "1.0.0", "kind": "derived",
           "status": "active", "immutable": False, **base_body,
           "lineage": {"parents": [{"agent_id": "presentation_composer", "version": "1.0.0"}],
                       "operation": "modify"}}
    bad["presentation"] = {**bad["presentation"], "card_order": ["summary", "valuation"]}
    errs_notrace = validator.validate_derived(bad, [pc])
    check("W-T10 card_order without trace rejected",
          any("trace" in e for e in errs_notrace))
    bad2 = {**bad, "presentation": {**base_body["presentation"], "max_facts_per_card": 12}}
    check("W4 max_facts_per_card>8 rejected",
          any("max_facts" in e for e in validator.validate_derived(bad2, [pc])))

    total = len(results)
    passed = sum(1 for _, c in results if c)
    print(f"\n{'='*50}\nRESULT: {passed}/{total} checks passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
