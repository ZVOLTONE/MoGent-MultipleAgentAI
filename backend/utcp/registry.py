"""UTCP Tool Registry (PRD 12.1 / 12.5).

Defines the MVP tool catalogue aligned with Sectors API v2 and executes
tools through the SectorsClient + per-request cache. Agents only ever
reference tools by name; they never see URLs, params or the API key.

Field shapes below reflect VERIFIED live responses for this API tier:
  * company/report sections overview, valuation, financials, dividend -> OK
  * corporate-actions, news, idx-total, foreign-flow, companies -> OK
  * index-daily/{index} -> OK but index code must be lowercase
  * company/quarterly, shareholders -> 404 (not in tier) -> served via yfinance
Endpoints that 404 on Sectors (company/quarterly, company/shareholders) are
transparently sourced from Yahoo Finance (yfinance) instead, so the tools stay
available with real data. See backend/utcp/yf_client.py.
"""
from __future__ import annotations

from datetime import date, timedelta

from .client import SectorsClient
from .cache import RequestCache
from .envelope import ToolResponse, error, ok, empty
from . import macro_scraper
from . import clock
from . import yf_client

# ---- date helpers -----------------------------------------------------------

def _default_range(days: int = 30, max_days: int = 90) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=min(days, max_days))
    return start.isoformat(), end.isoformat()


def _norm_symbol(sym: str) -> str:
    return (sym or "").strip().upper().replace(".JK", "")


# ---- tool metadata (for discovery / agent-card / manual) --------------------

TOOL_SPECS: dict[str, dict] = {
    "get_company_report": {
        "endpoint": "GET /v2/company/report/{symbol}/",
        "params": ["symbol", "sections"],
        "description": "Fundamental, valuasi, dividen, kepemilikan, peer untuk emiten IDX.",
        "available": True,
    },
    "get_company_quarterly": {
        "endpoint": "yfinance quarterly_income_stmt + quarterly_balance_sheet",
        "params": ["symbol"],
        "description": "Laporan keuangan kuartalan terbaru (revenue, laba, net interest income, ekuitas, aset) via Yahoo Finance. Sectors API 404 pada tier ini.",
        "available": True,
        "source": "yfinance",
    },
    "get_daily_price": {
        "endpoint": "GET /v2/daily/{symbol}/",
        "params": ["symbol", "start", "end"],
        "description": "OHLCV harian + market cap (maks 90 hari).",
        "available": True,
    },
    "get_company_corporate_actions": {
        "endpoint": "GET /v2/company/corporate-actions/{symbol}/",
        "params": ["symbol"],
        "description": "Dividen, rights issue, split, buyback, AGM.",
        "available": True,
    },
    "search_idx_news": {
        "endpoint": "GET /v2/news/",
        "params": ["symbols", "keyword", "start", "end", "limit", "tags"],
        "description": "Berita IDX berdasarkan ticker/kata kunci/tag/rentang tanggal.",
        "available": True,
    },
    "get_filings": {
        "endpoint": "GET /v2/filings/",
        "params": ["symbol", "transaction_type", "holder_type", "start", "end", "limit"],
        "description": "Filing transaksi insider.",
        "available": True,
    },
    "get_foreign_flow": {
        "endpoint": "GET /v2/foreign-flow/{symbol}/",
        "params": ["symbol", "start", "end"],
        "description": "Net foreign buy/sell harian.",
        "available": True,
    },
    "get_shareholders": {
        "endpoint": "yfinance major_holders + institutional_holders",
        "params": ["symbol"],
        "description": "Komposisi kepemilikan saham (insider %, institusi %, pemegang institusi teratas) via Yahoo Finance. Sectors API 404 pada tier ini.",
        "available": True,
        "source": "yfinance",
    },
    "get_idx_total": {
        "endpoint": "GET /v2/idx-total/",
        "params": ["start", "end"],
        "description": "Total market cap IDX (proksi kondisi pasar).",
        "available": True,
    },
    "get_index_daily": {
        "endpoint": "GET /v2/index-daily/{index}/",
        "params": ["index", "start", "end"],
        "description": "Level penutupan indeks IDX (proksi kondisi pasar).",
        "available": True,
    },
    "screen_companies": {
        "endpoint": "GET /v2/companies/",
        "params": ["where", "order_by", "q"],
        "description": "Screener perusahaan IDX.",
        "available": True,
    },
    "get_macro_indicators": {
        "endpoint": "SCRAPE World Bank + exchangerate-api",
        "params": [],
        "description": "Indikator makro Indonesia: inflasi tahunan, suku bunga riil, kurs USD/IDR. BI Rate tidak tersedia dari sumber keyless -> dilaporkan jujur.",
        "available": True,
        "scraper": True,
    },
    "search_macro_news_id": {
        "endpoint": "SCRAPE Antara/Google News RSS (id)",
        "params": ["keyword", "limit"],
        "description": "Berita makro/ekonomi Indonesia.",
        "available": True,
        "scraper": True,
    },
    "search_macro_news_global": {
        "endpoint": "SCRAPE Google News RSS (global)",
        "params": ["keyword", "limit"],
        "description": "Berita makro global (Fed, inflasi, komoditas, kurs).",
        "available": True,
        "scraper": True,
    },
    "search_web_news": {
        "endpoint": "SCRAPE CNN Indonesia + Google News (query bebas)",
        "params": ["query", "scope", "limit"],
        "description": "Pencarian berita umum sesuai permintaan pengguna (scope: id/global/all).",
        "available": True,
        "scraper": True,
    },
    "get_time": {
        "endpoint": "LOCAL clock (WIB)",
        "params": [],
        "description": "Tanggal & waktu saat ini (WIB) untuk konteks kebaruan data.",
        "available": True,
        "scraper": False,
    },
}

ALL_TOOLS = list(TOOL_SPECS.keys())


class ToolRegistry:
    """Executes UTCP tools. One instance per process; cache is per request."""

    def __init__(self, client: SectorsClient | None = None):
        self.client = client or SectorsClient()

    # -- discovery ------------------------------------------------------------
    def exists(self, tool: str) -> bool:
        return tool in TOOL_SPECS

    def is_available(self, tool: str) -> bool:
        return TOOL_SPECS.get(tool, {}).get("available", False)

    def spec(self, tool: str) -> dict:
        return TOOL_SPECS.get(tool, {})

    # -- invocation -----------------------------------------------------------
    def call(self, tool: str, args: dict, cache: RequestCache) -> ToolResponse:
        if tool not in TOOL_SPECS:
            return error(tool, args, None, f"tool tidak dikenal: {tool}")
        fn = getattr(self, f"_t_{tool}", None)
        if fn is None:
            return error(tool, args, None, f"tool belum diimplementasikan: {tool}")
        return cache.get_or_call(tool, args, lambda: fn(args))

    # -- individual tools -----------------------------------------------------
    def _t_get_company_report(self, args: dict) -> ToolResponse:
        symbol = _norm_symbol(args.get("symbol", ""))
        sections = args.get("sections") or "overview"
        if isinstance(sections, (list, tuple)):
            sections = ",".join(sections)
        return self.client.get(
            "get_company_report", f"company/report/{symbol}/",
            args={"symbol": symbol, "sections": sections},
            params={"sections": sections},
        )

    def _t_get_daily_price(self, args: dict) -> ToolResponse:
        symbol = _norm_symbol(args.get("symbol", ""))
        start = args.get("start")
        end = args.get("end")
        if not start or not end:
            start, end = _default_range(30)
        return self.client.get(
            "get_daily_price", f"daily/{symbol}/",
            args={"symbol": symbol, "start": start, "end": end},
            params={"start": start, "end": end},
        )

    def _t_get_company_corporate_actions(self, args: dict) -> ToolResponse:
        symbol = _norm_symbol(args.get("symbol", ""))
        return self.client.get(
            "get_company_corporate_actions", f"company/corporate-actions/{symbol}/",
            args={"symbol": symbol}, params={},
            data_extractor=lambda raw: raw.get("corporate_actions") if isinstance(raw, dict) else raw,
        )

    def _t_search_idx_news(self, args: dict) -> ToolResponse:
        params = {}
        for k in ("symbols", "keyword", "start", "end", "tags"):
            if args.get(k):
                params[k] = args[k]
        params["limit"] = min(int(args.get("limit", 10) or 10), 30)
        return self.client.get(
            "search_idx_news", "news/",
            args={**params},
            params=params,
            data_extractor=lambda raw: raw.get("results") if isinstance(raw, dict) else raw,
        )

    def _t_get_filings(self, args: dict) -> ToolResponse:
        params = {}
        if args.get("symbol"):
            params["symbol"] = _norm_symbol(args["symbol"])
        for k in ("transaction_type", "holder_type", "start", "end"):
            if args.get(k):
                params[k] = args[k]
        params["limit"] = min(int(args.get("limit", 10) or 10), 30)
        return self.client.get(
            "get_filings", "filings/", args={**params}, params=params,
            data_extractor=lambda raw: raw.get("results") if isinstance(raw, dict) else raw,
        )

    def _t_get_foreign_flow(self, args: dict) -> ToolResponse:
        symbol = _norm_symbol(args.get("symbol", ""))
        start = args.get("start")
        end = args.get("end")
        if not start or not end:
            start, end = _default_range(30)
        return self.client.get(
            "get_foreign_flow", f"foreign-flow/{symbol}/",
            args={"symbol": symbol, "start": start, "end": end},
            params={"start": start, "end": end},
            data_extractor=lambda raw: raw.get("data") if isinstance(raw, dict) else raw,
        )

    def _t_get_idx_total(self, args: dict) -> ToolResponse:
        start = args.get("start")
        end = args.get("end")
        if not start or not end:
            start, end = _default_range(30)
        return self.client.get(
            "get_idx_total", "idx-total/",
            args={"start": start, "end": end},
            params={"start": start, "end": end},
        )

    def _t_get_index_daily(self, args: dict) -> ToolResponse:
        index = (args.get("index") or "idx30").strip().lower()  # must be lowercase
        start = args.get("start")
        end = args.get("end")
        if not start or not end:
            start, end = _default_range(30)
        return self.client.get(
            "get_index_daily", f"index-daily/{index}/",
            args={"index": index, "start": start, "end": end},
            params={"start": start, "end": end},
        )

    def _t_screen_companies(self, args: dict) -> ToolResponse:
        params = {}
        for k in ("where", "order_by", "q"):
            if args.get(k):
                params[k] = args[k]
        return self.client.get(
            "screen_companies", "companies/", args={**params}, params=params,
            data_extractor=lambda raw: raw.get("results") if isinstance(raw, dict) else raw,
        )

    # Endpoints that 404 on the Sectors tier -> sourced from Yahoo Finance.
    def _t_get_company_quarterly(self, args: dict) -> ToolResponse:
        symbol = _norm_symbol(args.get("symbol", ""))
        if not symbol:
            return error("get_company_quarterly", {"symbol": symbol}, None, "symbol kosong")
        if not yf_client.available():
            return error("get_company_quarterly", {"symbol": symbol}, None,
                         "yfinance tidak terpasang")
        data = yf_client.fetch_quarterly(symbol)
        if not data or not data.get("fields"):
            return empty("get_company_quarterly", {"symbol": symbol}, http_status=200,
                         reason="data kuartalan tidak tersedia dari Yahoo Finance")
        return ok("get_company_quarterly", {"symbol": symbol}, data, http_status=200)

    def _t_get_shareholders(self, args: dict) -> ToolResponse:
        symbol = _norm_symbol(args.get("symbol", ""))
        if not symbol:
            return error("get_shareholders", {"symbol": symbol}, None, "symbol kosong")
        if not yf_client.available():
            return error("get_shareholders", {"symbol": symbol}, None,
                         "yfinance tidak terpasang")
        data = yf_client.fetch_shareholders(symbol)
        if not data:
            return empty("get_shareholders", {"symbol": symbol}, http_status=200,
                         reason="data kepemilikan tidak tersedia dari Yahoo Finance")
        return ok("get_shareholders", {"symbol": symbol}, data, http_status=200)

    # -- macro scraper tools (public keyless sources) -------------------------
    def _t_get_macro_indicators(self, args: dict) -> ToolResponse:
        data = macro_scraper.fetch_macro_indicators()
        if not data.get("indicators"):
            return empty("get_macro_indicators", {}, http_status=200,
                         reason="tidak ada indikator makro yang berhasil diambil")
        return ok("get_macro_indicators", {}, data, http_status=200)

    def _t_search_macro_news_id(self, args: dict) -> ToolResponse:
        kw = args.get("keyword")
        limit = min(int(args.get("limit", 8) or 8), 20)
        items = macro_scraper.fetch_macro_news_id(kw, limit)
        if items is None:
            return error("search_macro_news_id", {"keyword": kw}, None,
                         "gagal mengambil RSS berita makro Indonesia")
        if not items:
            return empty("search_macro_news_id", {"keyword": kw}, reason="tidak ada berita")
        return ok("search_macro_news_id", {"keyword": kw, "limit": limit}, items)

    def _t_search_macro_news_global(self, args: dict) -> ToolResponse:
        kw = args.get("keyword")
        limit = min(int(args.get("limit", 8) or 8), 20)
        items = macro_scraper.fetch_macro_news_global(kw, limit)
        if items is None:
            return error("search_macro_news_global", {"keyword": kw}, None,
                         "gagal mengambil RSS berita makro global")
        if not items:
            return empty("search_macro_news_global", {"keyword": kw}, reason="tidak ada berita")
        return ok("search_macro_news_global", {"keyword": kw, "limit": limit}, items)

    def _t_search_web_news(self, args: dict) -> ToolResponse:
        query = (args.get("query") or args.get("keyword") or "").strip()
        scope = (args.get("scope") or "id").lower()
        if scope not in ("id", "global", "all"):
            scope = "id"
        limit = min(int(args.get("limit", 8) or 8), 20)
        if not query:
            return empty("search_web_news", {}, reason="query kosong")
        items = macro_scraper.search_general_news(query, scope=scope, limit=limit)
        if items is None:
            return error("search_web_news", {"query": query, "scope": scope}, None,
                         "gagal mengambil hasil berita")
        if not items:
            return empty("search_web_news", {"query": query, "scope": scope},
                         reason="tidak ada hasil")
        return ok("search_web_news", {"query": query, "scope": scope, "limit": limit}, items)

    def _t_get_time(self, args: dict) -> ToolResponse:
        return ok("get_time", {}, clock.now_info(), http_status=200)
