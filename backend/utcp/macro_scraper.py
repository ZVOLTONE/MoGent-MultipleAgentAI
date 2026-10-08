"""Macro data & news scrapers for Indonesia and global context.

All sources are PUBLIC and keyless, chosen for reliability and legal use:

Indicators (JSON):
  * World Bank Open Data API  -> Indonesia inflation (annual CPI %), real
    interest rate. Authoritative, no key, stable schema.
  * open.er-api.com           -> USD/IDR exchange rate (near-real-time).

News (RSS/XML):
  * Antara News (ekonomi)     -> Indonesian macro/economy headlines.
  * Google News RSS (query)   -> Indonesian & global macro headlines by topic.

Design notes aligned with the grounding contract (PRD 10):
  * BI Rate is NOT scraped from an unreliable page. If no trustworthy numeric
    source is available for it, the tool returns it as unavailable so the
    No-Data Gate / refusal still applies honestly (PRD 12.2).
  * Every numeric indicator carries its source + as_of date so facts remain
    traceable to evidence.
  * Network failures degrade to empty/error, never to fabricated values.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import requests

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")
_TIMEOUT = 20

WORLD_BANK = "https://api.worldbank.org/v2"
ER_API = "https://open.er-api.com/v6/latest/USD"
ANTARA_EKONOMI_RSS = "https://www.antaranews.com/rss/ekonomi"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #

def _wb_latest(indicator: str) -> dict | None:
    """Return the most recent non-null World Bank value for Indonesia."""
    url = f"{WORLD_BANK}/country/IDN/indicator/{indicator}"
    params = {"format": "json", "per_page": "15", "date": "2015:2026"}
    try:
        r = requests.get(url, params=params, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return None
    for row in payload[1]:  # already newest-first
        if row.get("value") is not None:
            return {
                "indicator": row["indicator"]["value"],
                "value": round(float(row["value"]), 2),
                "year": row["date"],
                "source": "World Bank Open Data (api.worldbank.org)",
            }
    return None


def fetch_bps_inflation() -> dict | None:
    """Indonesian inflation from BPS WebAPI (preferred, official).

    Requires a free BPS API key in .env (BPS_API_KEY). Without a key the BPS
    WebAPI rejects the request, so we return None and the caller falls back to
    World Bank. This keeps the pipeline honest and key-optional.
    """
    from config import config
    key = config.BPS_API_KEY
    if not key:
        return None
    var = config.BPS_INFLATION_VAR
    url = f"https://webapi.bps.go.id/v1/api/list/model/data/lang/ind/domain/0000/var/{var}/key/{key}/"
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(d, dict) or d.get("status") != "OK":
        return None
    data_vals = d.get("datacontent") or {}
    if not isinstance(data_vals, dict) or not data_vals:
        return None
    # datacontent keys are composite period codes; take the last (newest).
    try:
        last_key = sorted(data_vals.keys())[-1]
        value = float(data_vals[last_key])
    except (ValueError, IndexError, TypeError):
        return None
    return {
        "indicator": "Inflasi (BPS)",
        "value": round(value, 2),
        "as_of": last_key,
        "source": "Badan Pusat Statistik (webapi.bps.go.id)",
    }


def fetch_usd_idr() -> dict | None:
    try:
        r = requests.get(ER_API, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except (requests.RequestException, ValueError):
        return None
    if d.get("result") != "success" or "IDR" not in (d.get("rates") or {}):
        return None
    return {
        "indicator": "Kurs USD/IDR",
        "value": round(float(d["rates"]["IDR"]), 2),
        "as_of": d.get("time_last_update_utc"),
        "source": "exchangerate-api.com (open.er-api.com)",
    }


def fetch_macro_indicators() -> dict:
    """Collect available Indonesian macro indicators.

    Returns a dict with ``indicators`` (list of available ones) and
    ``unavailable`` (names we could not source). BI Rate is listed as
    unavailable unless a trustworthy numeric source is wired in.
    """
    indicators = []
    unavailable = []

    # Inflation: prefer BPS (official) when a key is configured; else World Bank.
    bps = fetch_bps_inflation()
    if bps:
        indicators.append({
            "name": "inflation_annual",
            "label": "Inflasi (BPS)",
            "value": bps["value"], "unit": "%",
            "as_of": bps["as_of"], "source": bps["source"],
        })
    else:
        infl = _wb_latest("FP.CPI.TOTL.ZG")
        if infl:
            indicators.append({
                "name": "inflation_annual",
                "label": "Inflasi tahunan (CPI)",
                "value": infl["value"], "unit": "%",
                "as_of": infl["year"], "source": infl["source"],
            })
        else:
            unavailable.append("inflation_annual")

    rate = _wb_latest("FR.INR.RINR")
    if rate:
        indicators.append({
            "name": "real_interest_rate",
            "label": "Suku bunga riil",
            "value": rate["value"], "unit": "%",
            "as_of": rate["year"], "source": rate["source"],
        })
    else:
        unavailable.append("real_interest_rate")

    fx = fetch_usd_idr()
    if fx:
        indicators.append({
            "name": "usd_idr",
            "label": "Kurs USD/IDR",
            "value": fx["value"], "unit": "idr",
            "as_of": fx.get("as_of"), "source": fx["source"],
        })
    else:
        unavailable.append("usd_idr")

    # BI Rate: no reliable keyless numeric source (BPS provides inflation, not
    # the policy rate) -> honest unavailable. Set BPS_API_KEY to prefer BPS
    # inflation; BI Rate still requires an explicit trusted source.
    unavailable.append("bi_rate")

    return {"indicators": indicators, "unavailable": unavailable,
            "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- #
# News (RSS)
# --------------------------------------------------------------------------- #

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S | re.I)
_TITLE_RE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.S | re.I)
_LINK_RE = re.compile(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", re.S | re.I)
_DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.S | re.I)
_SRC_RE = re.compile(r"<source[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</source>", re.S | re.I)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'"))
    return text.strip()


def _parse_rss(xml: str, limit: int) -> list[dict]:
    out = []
    for raw in _ITEM_RE.findall(xml)[:limit]:
        title = _TITLE_RE.search(raw)
        link = _LINK_RE.search(raw)
        pub = _DATE_RE.search(raw)
        src = _SRC_RE.search(raw)
        out.append({
            "title": _clean(title.group(1)) if title else "",
            "url": _clean(link.group(1)) if link else "",
            "published": _clean(pub.group(1)) if pub else "",
            "source": _clean(src.group(1)) if src else "",
        })
    return [x for x in out if x["title"]]


def _fetch_rss(url: str, params: dict | None, limit: int) -> list[dict] | None:
    try:
        r = requests.get(url, params=params or {}, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        r.raise_for_status()
        return _parse_rss(r.text, limit)
    except requests.RequestException:
        return None


def fetch_macro_news_id(keyword: str | None = None, limit: int = 8) -> list[dict] | None:
    """Indonesian macro/economy news.

    Uses a Google News RSS query scoped to Indonesia for topical relevance;
    falls back to Antara's economy feed when no keyword is given.
    """
    if keyword:
        q = f"{keyword} ekonomi makro Indonesia"
        return _fetch_rss(GOOGLE_NEWS_RSS,
                          {"q": q, "hl": "id", "gl": "ID", "ceid": "ID:id"}, limit)
    # default: Antara economy headlines
    items = _fetch_rss(ANTARA_EKONOMI_RSS, None, limit)
    if items:
        return items
    return _fetch_rss(GOOGLE_NEWS_RSS,
                      {"q": "ekonomi makro Indonesia inflasi suku bunga",
                       "hl": "id", "gl": "ID", "ceid": "ID:id"}, limit)


def fetch_macro_news_global(keyword: str | None = None, limit: int = 8) -> list[dict] | None:
    """Global macro news (Fed, inflation, commodities, FX)."""
    q = keyword or "global inflation OR fed rate OR central bank OR commodities"
    return _fetch_rss(GOOGLE_NEWS_RSS,
                      {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}, limit)


# --------------------------------------------------------------------------- #
# Versatile general news search (any user query)
# --------------------------------------------------------------------------- #

CNN_ID_RSS = {
    "umum": "https://www.cnnindonesia.com/rss",
    "ekonomi": "https://www.cnnindonesia.com/ekonomi/rss",
    "nasional": "https://www.cnnindonesia.com/nasional/rss",
    "internasional": "https://www.cnnindonesia.com/internasional/rss",
    "teknologi": "https://www.cnnindonesia.com/teknologi/rss",
}


def _keyword_filter(items: list[dict], keyword: str | None) -> list[dict]:
    if not keyword:
        return items
    kws = [w for w in re.split(r"\s+", keyword.lower()) if len(w) > 2]
    if not kws:
        return items
    scored = []
    for it in items:
        hay = (it.get("title", "") + " " + it.get("summary", "")).lower()
        hits = sum(1 for w in kws if w in hay)
        if hits:
            scored.append((hits, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored]


def _parse_rss_full(xml: str, limit: int, source_name: str) -> list[dict]:
    out = []
    for raw in _ITEM_RE.findall(xml)[:limit * 3]:
        title = _TITLE_RE.search(raw)
        link = _LINK_RE.search(raw)
        pub = _DATE_RE.search(raw)
        desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", raw, re.S | re.I)
        out.append({
            "title": _clean(title.group(1)) if title else "",
            "url": _clean(link.group(1)) if link else "",
            "published": _clean(pub.group(1)) if pub else "",
            "summary": _clean(desc.group(1))[:300] if desc else "",
            "source": source_name,
        })
    return [x for x in out if x["title"]]


def search_general_news(query: str, scope: str = "id", limit: int = 8) -> list[dict] | None:
    """Search news for an arbitrary user query and scrape the results.

    scope:
      "id"     -> CNN Indonesia feeds + Google News (Indonesia)
      "global" -> Google News (global, English)
      "all"    -> both

    Returns a de-duplicated, keyword-ranked list of {title, url, published,
    summary, source}. Never fabricates; returns None on total failure.
    """
    query = (query or "").strip()
    collected: list[dict] = []

    if scope in ("id", "all"):
        # CNN Indonesia: pick a relevant category feed, then keyword-filter.
        cat = "umum"
        ql = query.lower()
        if any(w in ql for w in ("ekonomi", "saham", "rupiah", "inflasi", "bisnis", "pasar")):
            cat = "ekonomi"
        elif any(w in ql for w in ("dunia", "global", "as ", "amerika", "china", "eropa")):
            cat = "internasional"
        elif any(w in ql for w in ("teknologi", "ai", "gadget", "startup")):
            cat = "teknologi"
        cnn = _fetch_rss_text(CNN_ID_RSS[cat])
        if cnn:
            collected += _parse_rss_full(cnn, limit, f"CNN Indonesia ({cat})")
        gid = _fetch_rss_text(
            GOOGLE_NEWS_RSS + f"?q={requests.utils.quote(query)}&hl=id&gl=ID&ceid=ID:id")
        if gid:
            collected += _parse_rss_full(gid, limit, "Google News (ID)")

    if scope in ("global", "all"):
        gg = _fetch_rss_text(
            GOOGLE_NEWS_RSS + f"?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en")
        if gg:
            collected += _parse_rss_full(gg, limit, "Google News (Global)")

    if not collected:
        return None

    ranked = _keyword_filter(collected, query) or collected
    # de-duplicate by title
    seen, out = set(), []
    for it in ranked:
        key = it["title"].lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= limit:
            break
    return out


def _fetch_rss_text(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.RequestException:
        return None
