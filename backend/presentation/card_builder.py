"""Deterministic card builder (PRD Web-Cards 9.2, 10, 13).

Turns an Orchestrator ``/query`` result into a list of cards. The number
values are formatted by the SAME formatter the Fact Ledger uses, so a card
value is identical to the value in the text (PRD 13). No new numbers are
created here (W1).
"""
from __future__ import annotations

from backend.grounding.fact_ledger import format_value
from backend.presentation import explain
from backend.presentation.profiles import resolve, wants_glossary

# Human labels for metrics (Indonesian, baku per glossary).
METRIC_LABEL = {
    "last_close_price": "Harga Terakhir",
    "market_cap": "Kapitalisasi Pasar",
    "pe_ratio": "PER", "forward_pe": "PER (proyeksi)", "pb_ratio": "PBV",
    "intrinsic_value": "Nilai Intrinsik",
    "dividend_yield": "Imbal Hasil Dividen", "dividend_per_share": "Dividen per Saham",
    "revenue": "Pendapatan", "earnings": "Laba Bersih",
    "total_equity": "Total Ekuitas", "total_assets": "Total Aset",
    "total_debt": "Total Utang",
    "roe": "ROE", "q_roe_annualized": "ROE (kuartalan, disetahunkan)",
    "ldr": "LDR",
    "gross_loan": "Kredit Disalurkan", "total_deposit": "Dana Pihak Ketiga",
    "net_interest_income": "Pendapatan Bunga Bersih",
    "q_revenue": "Pendapatan (kuartalan)", "q_earnings": "Laba Bersih (kuartalan)",
    "q_total_equity": "Total Ekuitas (kuartalan)", "q_total_assets": "Total Aset (kuartalan)",
    "q_total_debt": "Total Utang (kuartalan)", "q_eps": "EPS (kuartalan)",
    "q_net_interest_income": "Pendapatan Bunga Bersih (kuartalan)",
    "insider_ownership": "Kepemilikan Insider",
    "institutional_ownership": "Kepemilikan Institusi",
    "institutional_float_ownership": "Kepemilikan Institusi (float)",
    "institutions_count": "Jumlah Institusi",
    "period_low": "Terendah Periode", "period_high": "Tertinggi Periode",
}

# Which metrics belong to which card group.
CARD_METRICS = {
    "summary": ["last_close_price", "market_cap", "pe_ratio", "pb_ratio", "roe", "ldr"],
    "valuation": ["pe_ratio", "forward_pe", "pb_ratio", "intrinsic_value",
                  "dividend_yield", "dividend_per_share"],
    "performance": ["revenue", "earnings", "roe", "ldr", "net_interest_income",
                    "total_equity", "total_assets", "total_debt",
                    "q_revenue", "q_earnings", "q_roe_annualized",
                    "q_net_interest_income", "q_eps"],
    "ownership": ["insider_ownership", "institutional_ownership",
                  "institutional_float_ownership", "institutions_count"],
    "price": ["last_close_price", "market_cap", "period_low", "period_high"],
}

CARD_TITLE = {
    "summary": "Ringkasan",
    "valuation": "Valuasi & Dividen",
    "performance": "Kinerja Keuangan",
    "ownership": "Kepemilikan Saham",
    "macro": "Konteks Makro",
    "price": "Harga & Pasar",
    "chart": "Pergerakan Harga",
    "news": "Berita Terkini",
    "risk": "Risiko",
    "trace": "Sumber & Keterbatasan",
    "glossary": "Istilah Penting",
}

CARD_TYPE = {
    "summary": "summary", "valuation": "metrics", "performance": "metrics",
    "ownership": "metrics", "macro": "metrics", "price": "metrics",
    "chart": "chart", "news": "news", "risk": "risk", "trace": "trace",
    "glossary": "glossary",
}

# Macro indicator metric names are dynamic; identify by field_path / source.
_MACRO_HINTS = ("macro", "inflasi", "suku bunga", "kurs", "usd/idr", "bi rate")

_DISCLAIMER = ("Alat bantu analisis dan edukasi, bukan nasihat investasi. "
               "Tidak ada rekomendasi beli/jual.")


def _label(metric: str) -> str:
    return METRIC_LABEL.get(metric, metric.replace("_", " ").title())


def _is_macro_fact(f: dict) -> bool:
    fp = (f.get("field_path") or "").lower()
    src = (f.get("source") or "").lower()
    if "macro" in fp or "macro" in src or "bps" in src or "world bank" in src:
        return True
    return any(h in (f.get("metric") or "").lower() for h in _MACRO_HINTS)


def _fact_to_card_fact(f: dict) -> dict:
    """Render one ledger fact into a card fact (value formatted once)."""
    label = _label(f.get("metric", ""))
    if f.get("derived"):
        label = f"{label} (ƒ)"
    return {
        "label": label,
        "value": format_value(f.get("value"), f.get("unit", "")),
        "as_of": f.get("as_of") or "tanggal tidak tercantum",
        "source": f.get("source") or "Sectors",
        "evidence_id": f.get("evidence_id"),
        "derived": bool(f.get("derived")),
        "formula": f.get("formula"),
    }


def build_cards(query_result: dict, agent_spec: dict | None = None) -> dict:
    """Main entry: /query result -> {cards, meta}."""
    profile = resolve(agent_spec)
    facts = [f for f in (query_result.get("facts") or [])]

    # anomalies never shown as numbers (W-T4) — collected for the trace card.
    anomalies = [f for f in facts if f.get("anomaly")]
    clean = [f for f in facts if not f.get("anomaly")]

    # de-duplicate on (metric, value, as_of) (W-T2 / PRD 10 display rule).
    seen, deduped = set(), []
    for f in clean:
        key = (f.get("metric"), f.get("value"), f.get("as_of"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    macro_facts = [f for f in deduped if _is_macro_fact(f)]
    by_metric: dict[str, list[dict]] = {}
    for f in deduped:
        by_metric.setdefault(f.get("metric"), []).append(f)

    answer = query_result.get("answer", "")
    max_facts = profile["max_facts_per_card"]
    n_bullets = profile["bullets_per_card"]

    builders = {
        "summary": lambda: _summary_card(query_result, by_metric, answer, max_facts, n_bullets),
        "valuation": lambda: _metric_card("valuation", by_metric, max_facts),
        "performance": lambda: _metric_card("performance", by_metric, max_facts),
        "ownership": lambda: _metric_card("ownership", by_metric, max_facts),
        "price": lambda: _metric_card("price", by_metric, max_facts),
        "macro": lambda: _macro_card(macro_facts, max_facts),
        "chart": lambda: _chart_card(query_result),
        "news": lambda: _news_card(query_result),
        "risk": lambda: _risk_card(answer),
        "trace": lambda: _trace_card(query_result, anomalies),
    }

    cards: list[dict] = []
    shown_metrics: list[str] = []
    for cid in profile["card_order"]:
        if cid == "trace":
            continue  # appended last
        card = builders.get(cid, lambda: None)()
        if card:
            cards.append(card)
            for cf in card.get("facts", []):
                shown_metrics.append(cf.get("label"))

    # glossary card (beginner profiles) — before trace.
    if wants_glossary(profile):
        metrics_shown = [f.get("metric") for f in deduped]
        g = explain.glossary_for_metrics(metrics_shown)
        if g:
            cards.append({"id": "glossary", "type": "glossary",
                          "title": CARD_TITLE["glossary"],
                          "facts": [], "bullets": [], "items": g})

    # trace card is ALWAYS present and ALWAYS last (W3).
    cards.append(builders["trace"]())

    return {
        "cards": cards,
        "meta": {
            "agent": f"{(agent_spec or {}).get('agent_id', 'presentation_composer')}@"
                     f"{(agent_spec or {}).get('version', '1.0.0')}",
            "n_facts": len(deduped),
            "profile": _profile_name(agent_spec),
            "font_scale": profile["font_scale"],
            "density": profile["density"],
        },
    }


# -- individual card builders ------------------------------------------------
def _collect(group: str, by_metric: dict, max_facts: int) -> list[dict]:
    out = []
    for metric in CARD_METRICS.get(group, []):
        for f in by_metric.get(metric, []):
            out.append(_fact_to_card_fact(f))
            if len(out) >= max_facts:
                return out
    return out


def _metric_card(group: str, by_metric: dict, max_facts: int) -> dict | None:
    facts = _collect(group, by_metric, max_facts)
    if not facts:
        return None
    return {"id": group, "type": CARD_TYPE[group], "title": CARD_TITLE[group],
            "facts": facts, "bullets": [], "items": [], "series": []}


def _summary_card(query_result, by_metric, answer, max_facts, n_bullets) -> dict | None:
    facts = _collect("summary", by_metric, max_facts)
    identity = _identity(query_result)
    bullets = explain.extract_bullets(answer, max_items=n_bullets)
    if not facts and not bullets:
        return None
    subtitle = None
    if identity:
        subtitle = " · ".join(x for x in [identity.get("sector"),
                                          identity.get("subsector")] if x)
    return {
        "id": "summary", "type": "summary",
        "title": _title_for_summary(query_result, identity),
        "subtitle": subtitle,
        "facts": facts, "bullets": bullets, "items": [], "series": [],
    }


def _macro_card(macro_facts, max_facts) -> dict | None:
    if not macro_facts:
        return None
    facts = [_fact_to_card_fact(f) for f in macro_facts[:max_facts]]
    return {"id": "macro", "type": "metrics", "title": CARD_TITLE["macro"],
            "facts": facts, "bullets": [], "items": [], "series": []}


def _chart_card(query_result) -> dict | None:
    rows = _price_series(query_result)
    if len(rows) < 5:  # W-T9: too few points -> no chart card
        return None
    first, last = rows[0], rows[-1]
    closes = [r["c"] for r in rows]
    change = None
    if first["c"]:
        change = round((last["c"] - first["c"]) / first["c"] * 100, 2)
    facts = [
        {"label": "Awal", "value": format_value(first["c"], "idr"),
         "as_of": first["d"], "source": "Sectors (harga harian)", "derived": False},
        {"label": "Akhir", "value": format_value(last["c"], "idr"),
         "as_of": last["d"], "source": "Sectors (harga harian)", "derived": False},
        {"label": "Terendah", "value": format_value(min(closes), "idr"),
         "as_of": f"{first['d']}..{last['d']}", "source": "Sectors (harga harian)",
         "derived": False},
        {"label": "Tertinggi", "value": format_value(max(closes), "idr"),
         "as_of": f"{first['d']}..{last['d']}", "source": "Sectors (harga harian)",
         "derived": False},
    ]
    if change is not None:
        facts.append({"label": "Perubahan", "value": f"{change:+.2f}%",
                      "as_of": f"{first['d']}..{last['d']}",
                      "source": "Sectors (harga harian)", "derived": True,
                      "formula": "(akhir-awal)/awal*100"})
    return {"id": "chart", "type": "chart", "title": CARD_TITLE["chart"],
            "facts": facts, "bullets": [], "items": [], "series": rows}


def _news_card(query_result) -> dict | None:
    items = _news_items(query_result)
    if not items:
        return None
    return {"id": "news", "type": "news", "title": CARD_TITLE["news"],
            "facts": [], "bullets": [], "items": items[:6], "series": []}


def _risk_card(answer) -> dict | None:
    bullets = explain.extract_risk_bullets(answer, max_items=5)
    if not bullets:
        return None
    return {"id": "risk", "type": "risk", "title": CARD_TITLE["risk"],
            "facts": [], "bullets": bullets, "items": [], "series": []}


def _trace_card(query_result, anomalies) -> dict:
    tool_calls = query_result.get("tool_calls", [])
    ok = [t for t in tool_calls if t.get("result_status") == "ok"]
    failed = [t for t in tool_calls if t.get("result_status") != "ok"]
    items = []
    for t in failed:
        items.append({"title": t.get("tool"), "source": t.get("glyph", "✗"),
                      "date": t.get("result_status"), "url": None})
    af = query_result.get("agent_factory", {})
    bullets = []
    bullets.append(f"Agent dipakai: {', '.join(query_result.get('agents_used', [])) or '—'}")
    bullets.append(f"Tool berhasil: {len(ok)} · gagal: {len(failed)}")
    if af.get("invoked"):
        op = af.get("operation", "")
        nid = af.get("new_agent_id", "")
        parents = ", ".join(af.get("parents", []))
        bullets.append(f"Agent Factory: {op} → {nid} (induk: {parents}; "
                       f"base agent tidak berubah)")
    for lim in query_result.get("limitations", [])[:5]:
        bullets.append(f"Keterbatasan: {lim}")
    for c in query_result.get("contradictions", [])[:3]:
        bullets.append(f"Kontradiksi: {c}")
    for a in anomalies[:5]:
        bullets.append(f"Data anomali (tidak ditampilkan sebagai angka): "
                       f"{_label(a.get('metric',''))}")
    bullets.append(_DISCLAIMER)
    return {"id": "trace", "type": "trace", "title": CARD_TITLE["trace"],
            "facts": [], "bullets": bullets, "items": items, "series": []}


# -- extraction helpers ------------------------------------------------------
def _identity(query_result) -> dict | None:
    for out in query_result.get("_trace", {}).get("agent_outputs", []):
        if out.get("identity"):
            return out["identity"]
    return None


def _title_for_summary(query_result, identity) -> str:
    ticker = query_result.get("ticker")
    if identity and identity.get("company_name"):
        name = identity["company_name"]
        return f"{ticker} — {name}" if ticker else name
    return ticker or "Ringkasan Analisis"


def _price_series(query_result) -> list[dict]:
    for ev in query_result.get("evidence", []):
        if ev.get("tool") == "get_daily_price" and ev.get("payload"):
            rows = ev["payload"]
            out = []
            if isinstance(rows, list):
                for r in rows:
                    if isinstance(r, dict) and r.get("close") is not None and r.get("date"):
                        out.append({"d": r["date"], "c": r["close"]})
            return out
    return []


def _news_items(query_result) -> list[dict]:
    news_tools = {"search_idx_news", "search_web_news",
                  "search_macro_news_id", "search_macro_news_global"}
    seen, items = set(), []
    for ev in query_result.get("evidence", []):
        if ev.get("tool") in news_tools and isinstance(ev.get("payload"), list):
            for it in ev["payload"]:
                if not isinstance(it, dict):
                    continue
                title = it.get("title")
                if not title or title in seen:
                    continue
                seen.add(title)
                items.append({
                    "title": title,
                    "source": it.get("source", ""),
                    "date": it.get("published") or it.get("created_at") or it.get("date") or "",
                    "url": it.get("url") or it.get("link") or "",
                })
    return items


def _profile_name(agent_spec) -> str:
    if not agent_spec:
        return "default"
    aid = agent_spec.get("agent_id", "")
    return "default" if aid == "presentation_composer" else aid
