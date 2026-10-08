"""yfinance data client for endpoints Sectors API does NOT serve on this tier.

Live probing (see Documentation.md) confirmed that two Sectors v2 endpoints
return HTTP 404 on the current API tier:

    GET /v2/company/quarterly/{symbol}/     -> 404
    GET /v2/company/shareholders/{symbol}/  -> 404

Rather than leave those tools permanently ``no_data``, we source the SAME
information from Yahoo Finance via the ``yfinance`` library, which does serve
IDX tickers (suffix ``.JK``):

  * quarterly financials  -> quarterly_income_stmt + quarterly_balance_sheet
  * shareholders          -> major_holders + institutional_holders

This module is pure transport: it knows nothing about agents or the Fact
Ledger. It returns plain dicts that the registry wraps into ToolResponse and
the facts_extractor maps to grounded facts (every number keeps a source).

Grounding note: all numbers come from the live Yahoo payload. On any failure
(network, rate limit, empty) we return ``None`` so the registry emits an
``error``/``empty`` envelope and the No-Data Gate stays honest -- we never
fabricate values.
"""
from __future__ import annotations

import math
from typing import Any

try:
    import yfinance as yf
except Exception:  # pragma: no cover - yfinance is a declared dependency
    yf = None


def _yf_symbol(symbol: str) -> str:
    """Map an IDX ticker to its Yahoo Finance symbol (``BBCA`` -> ``BBCA.JK``)."""
    s = (symbol or "").strip().upper().replace(".JK", "")
    return f"{s}.JK" if s else s


def _num(v: Any) -> float | None:
    """Coerce a value to a clean float, treating NaN/inf/None as missing."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def available() -> bool:
    return yf is not None


# -- quarterly financials -----------------------------------------------------

# Yahoo row label -> canonical field name used by facts_extractor.
_INCOME_FIELDS = {
    "Total Revenue": "revenue",
    "Net Income": "earnings",
    "Net Interest Income": "net_interest_income",
    "Diluted EPS": "eps",
    "Basic EPS": "eps_basic",
    "Operating Income": "operating_income",
    "Pretax Income": "pretax_income",
}

_BALANCE_FIELDS = {
    "Stockholders Equity": "total_equity",
    "Total Assets": "total_assets",
    "Total Debt": "total_debt",
    "Total Liabilities Net Minority Interest": "total_liabilities",
    "Ordinary Shares Number": "shares_outstanding",
}


def _latest_series(df, fields: dict[str, str]) -> tuple[str | None, dict[str, float]]:
    """Pull the most-recent column from a yfinance statement DataFrame."""
    out: dict[str, float] = {}
    if df is None or getattr(df, "empty", True):
        return None, out
    try:
        col = df.columns[0]  # yfinance orders newest first
        period = str(col.date()) if hasattr(col, "date") else str(col)
    except Exception:
        return None, out
    for label, canonical in fields.items():
        if label in df.index:
            val = _num(df.loc[label, col])
            if val is not None:
                out[canonical] = val
    return period, out


def fetch_quarterly(symbol: str) -> dict | None:
    """Return latest-quarter financials for an IDX symbol, or None on failure."""
    if yf is None:
        return None
    ysym = _yf_symbol(symbol)
    if not ysym:
        return None
    try:
        t = yf.Ticker(ysym)
        income = t.quarterly_income_stmt
        balance = t.quarterly_balance_sheet
    except Exception:
        return None

    period, inc = _latest_series(income, _INCOME_FIELDS)
    bperiod, bal = _latest_series(balance, _BALANCE_FIELDS)
    merged = {**inc, **bal}
    if not merged:
        return None
    return {
        "symbol": _yf_symbol(symbol).replace(".JK", ""),
        "source": "Yahoo Finance (yfinance)",
        "report_date": period or bperiod,
        "fields": merged,
    }


# -- shareholders -------------------------------------------------------------

def fetch_shareholders(symbol: str) -> dict | None:
    """Return ownership breakdown + top institutional holders, or None."""
    if yf is None:
        return None
    ysym = _yf_symbol(symbol)
    if not ysym:
        return None
    try:
        t = yf.Ticker(ysym)
    except Exception:
        return None

    breakdown: dict[str, float] = {}
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty and "Value" in mh.columns:
            for key in ("insidersPercentHeld", "institutionsPercentHeld",
                        "institutionsFloatPercentHeld", "institutionsCount"):
                if key in mh.index:
                    v = _num(mh.loc[key, "Value"])
                    if v is not None:
                        breakdown[key] = v
    except Exception:
        breakdown = {}

    holders: list[dict] = []
    try:
        ih = t.institutional_holders
        if ih is not None and not ih.empty:
            for _, row in ih.head(10).iterrows():
                holders.append({
                    "holder": str(row.get("Holder", "")),
                    "pct_held": _num(row.get("pctHeld")),
                    "shares": _num(row.get("Shares")),
                    "date_reported": str(row.get("Date Reported", "")),
                })
    except Exception:
        holders = []

    if not breakdown and not holders:
        return None
    return {
        "symbol": _yf_symbol(symbol).replace(".JK", ""),
        "source": "Yahoo Finance (yfinance)",
        "breakdown": breakdown,
        "institutional_holders": holders,
    }
