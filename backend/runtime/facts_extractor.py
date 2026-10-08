"""Extract structured facts from verified Sectors payloads into the Fact Ledger.

This is where the field-mapping lives (PRD 10.6, risk item #3). It uses the
REAL response shapes verified against the live API:
  * valuation.historical_valuation -> list per year with pe/pb/ps
  * valuation.forward_pe / intrinsic_value / last_close_price
  * financials.historical_financials -> list per year (bank fields)
  * dividend.historical_dividends -> dict per year {total_yield,total_dividend}
  * daily -> list of OHLCV
Every fact is sanity-checked; out-of-range values are flagged anomaly and are
not narrated as business facts.
"""
from __future__ import annotations

from backend.grounding.fact_ledger import FactLedger
from backend.grounding import sanity_checks


def _latest_year_entry(items: list[dict]) -> dict | None:
    if not items:
        return None
    try:
        return sorted(items, key=lambda x: x.get("year", 0))[-1]
    except Exception:
        return items[-1]


def _add(ledger: FactLedger, metric, value, unit, ev_id, field_path, as_of=None,
         derived=False, formula=None):
    anomalous, _ = sanity_checks.check(metric, value)
    return ledger.add(metric, value, unit, evidence_id=ev_id, as_of=as_of,
                      field_path=field_path, derived=derived, formula=formula,
                      anomaly=anomalous)


def extract_valuation(ledger: FactLedger, payload: dict, ev_id: str) -> list[str]:
    added = []
    val = (payload or {}).get("valuation") or {}
    hv = val.get("historical_valuation") or []
    entry = _latest_year_entry(hv)
    if entry:
        year = entry.get("year")
        if entry.get("pe") is not None:
            added.append(_add(ledger, "pe_ratio", round(entry["pe"], 2), "x", ev_id,
                              "valuation.historical_valuation.pe", as_of=str(year)).fact_id)
        if entry.get("pb") is not None:
            added.append(_add(ledger, "pb_ratio", round(entry["pb"], 2), "x", ev_id,
                              "valuation.historical_valuation.pb", as_of=str(year)).fact_id)
    if val.get("forward_pe") is not None:
        added.append(_add(ledger, "forward_pe", round(val["forward_pe"], 2), "x", ev_id,
                          "valuation.forward_pe").fact_id)
    if val.get("intrinsic_value") is not None:
        added.append(_add(ledger, "intrinsic_value", val["intrinsic_value"], "idr", ev_id,
                          "valuation.intrinsic_value").fact_id)
    if val.get("last_close_price") is not None:
        added.append(_add(ledger, "last_close_price", val["last_close_price"], "idr", ev_id,
                          "valuation.last_close_price",
                          as_of=val.get("latest_close_date")).fact_id)
    return added


def extract_overview(ledger: FactLedger, payload: dict, ev_id: str) -> list[str]:
    added = []
    ov = (payload or {}).get("overview") or {}
    if ov.get("market_cap") is not None:
        added.append(_add(ledger, "market_cap", ov["market_cap"], "idr", ev_id,
                          "overview.market_cap").fact_id)
    if ov.get("last_close_price") is not None:
        added.append(_add(ledger, "last_close_price", ov["last_close_price"], "idr", ev_id,
                          "overview.last_close_price",
                          as_of=ov.get("latest_close_date")).fact_id)
    return added


def extract_financials(ledger: FactLedger, payload: dict, ev_id: str, is_bank: bool) -> list[str]:
    added = []
    fin = (payload or {}).get("financials") or {}
    hf = fin.get("historical_financials") or []
    entry = _latest_year_entry(hf)
    if not entry:
        return added
    year = str(entry.get("year"))
    for metric, field, unit in [
        ("revenue", "revenue", "idr"),
        ("earnings", "earnings", "idr"),
        ("total_equity", "total_equity", "idr"),
        ("total_assets", "total_assets", "idr"),
    ]:
        if entry.get(field) is not None:
            added.append(_add(ledger, metric, entry[field], unit, ev_id,
                              f"financials.historical_financials.{field}", as_of=year).fact_id)

    # derived ROE = earnings / total_equity
    if entry.get("earnings") and entry.get("total_equity"):
        roe = 100.0 * entry["earnings"] / entry["total_equity"]
        added.append(_add(ledger, "roe", round(roe, 2), "%", ev_id,
                          "financials", as_of=year, derived=True,
                          formula="earnings/total_equity*100").fact_id)

    if is_bank:
        for metric, field in [("gross_loan", "gross_loan"), ("total_deposit", "total_deposit"),
                              ("net_interest_income", "net_interest_income")]:
            if entry.get(field) is not None:
                added.append(_add(ledger, metric, entry[field], "idr", ev_id,
                                  f"financials.historical_financials.{field}", as_of=year).fact_id)
        # derived LDR = gross_loan / total_deposit
        if entry.get("gross_loan") and entry.get("total_deposit"):
            ldr = 100.0 * entry["gross_loan"] / entry["total_deposit"]
            added.append(_add(ledger, "ldr", round(ldr, 2), "%", ev_id, "financials",
                              as_of=year, derived=True,
                              formula="gross_loan/total_deposit*100").fact_id)
    return added


def extract_dividend(ledger: FactLedger, payload: dict, ev_id: str) -> list[str]:
    added = []
    div = (payload or {}).get("dividend") or {}
    hist = div.get("historical_dividends") or {}
    if not isinstance(hist, dict) or not hist:
        return added
    latest_year = sorted(hist.keys())[-1]
    entry = hist[latest_year]
    if isinstance(entry, dict):
        if entry.get("total_yield") is not None:
            added.append(_add(ledger, "dividend_yield", round(entry["total_yield"] * 100, 2), "%",
                              ev_id, "dividend.historical_dividends.total_yield",
                              as_of=latest_year).fact_id)
        if entry.get("total_dividend") is not None:
            added.append(_add(ledger, "dividend_per_share", entry["total_dividend"], "idr", ev_id,
                              "dividend.historical_dividends.total_dividend",
                              as_of=latest_year).fact_id)
    return added


def extract_daily_price(ledger: FactLedger, payload, ev_id: str) -> list[str]:
    added = []
    rows = payload if isinstance(payload, list) else []
    if not rows:
        return added
    last = rows[-1]
    if last.get("close") is not None:
        added.append(_add(ledger, "last_close_price", last["close"], "idr", ev_id,
                          "daily.close", as_of=last.get("date")).fact_id)
    closes = [r["close"] for r in rows if r.get("close") is not None]
    if closes:
        added.append(_add(ledger, "period_low", min(closes), "idr", ev_id, "daily.close",
                          as_of=f"{rows[0].get('date')}..{rows[-1].get('date')}").fact_id)
        added.append(_add(ledger, "period_high", max(closes), "idr", ev_id, "daily.close",
                          as_of=f"{rows[0].get('date')}..{rows[-1].get('date')}").fact_id)
    return added


def extract_quarterly(ledger: FactLedger, payload: dict, ev_id: str, is_bank: bool) -> list[str]:
    """Map yfinance quarterly payload (fetch_quarterly) into facts.

    payload shape: {"symbol","source","report_date","fields": {canonical:value}}
    Facts are tagged with the Yahoo Finance source via field_path and as_of.
    """
    added = []
    fields = (payload or {}).get("fields") or {}
    as_of = (payload or {}).get("report_date")
    src = "yfinance.quarterly"

    for metric, unit in [
        ("revenue", "idr"),
        ("earnings", "idr"),
        ("total_equity", "idr"),
        ("total_assets", "idr"),
        ("total_debt", "idr"),
        ("eps", "idr"),
    ]:
        if fields.get(metric) is not None:
            added.append(_add(ledger, f"q_{metric}", fields[metric], unit, ev_id,
                              f"{src}.{metric}", as_of=as_of).fact_id)

    if is_bank and fields.get("net_interest_income") is not None:
        added.append(_add(ledger, "q_net_interest_income", fields["net_interest_income"], "idr",
                          ev_id, f"{src}.net_interest_income", as_of=as_of).fact_id)

    # derived quarterly ROE (annualised) = earnings*4 / total_equity
    if fields.get("earnings") and fields.get("total_equity"):
        roe = 100.0 * (fields["earnings"] * 4) / fields["total_equity"]
        added.append(_add(ledger, "q_roe_annualized", round(roe, 2), "%", ev_id,
                          f"{src}", as_of=as_of, derived=True,
                          formula="earnings*4/total_equity*100").fact_id)
    return added


def extract_shareholders(ledger: FactLedger, payload: dict, ev_id: str) -> list[str]:
    """Map yfinance shareholders payload (fetch_shareholders) into facts.

    Percentages come as fractions (0.19534 -> 19.53%). Each fact keeps the
    Yahoo Finance source via field_path.
    """
    added = []
    bd = (payload or {}).get("breakdown") or {}
    src = "yfinance.shareholders"
    pct_map = {
        "insidersPercentHeld": "insider_ownership",
        "institutionsPercentHeld": "institutional_ownership",
        "institutionsFloatPercentHeld": "institutional_float_ownership",
    }
    for key, metric in pct_map.items():
        if bd.get(key) is not None:
            added.append(_add(ledger, metric, round(bd[key] * 100, 2), "%", ev_id,
                              f"{src}.{key}").fact_id)
    if bd.get("institutionsCount") is not None:
        added.append(_add(ledger, "institutions_count", int(bd["institutionsCount"]), "",
                          ev_id, f"{src}.institutionsCount").fact_id)
    return added


def extract_macro_indicators(ledger: FactLedger, payload: dict, ev_id: str) -> list[str]:
    """Map get_macro_indicators payload into facts (each with source + as_of)."""
    added = []
    for ind in (payload or {}).get("indicators", []):
        name = ind.get("name")
        value = ind.get("value")
        unit = ind.get("unit", "")
        if value is None:
            continue
        f = _add(ledger, name, value, unit, ev_id,
                 field_path=f"get_macro_indicators.{name}", as_of=ind.get("as_of"))
        added.append(f.fact_id)
    return added
