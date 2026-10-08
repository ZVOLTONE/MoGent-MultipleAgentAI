"""IDX stock universe loaded from a local CSV (offline ticker validation).

Validating a ticker against this list is free (no API credit, no LLM token).
Used by the orchestrator to:
  * reject non-existent tickers without hitting the Sectors API (T19)
  * avoid treating finance abbreviations (EPS, ROE, PBV, PER) as tickers

CSV format (header): Kode,Nama Perusahaan,Tanggal Pencatatan
The file is resolved relative to the project root; name is configurable.
"""
from __future__ import annotations

import csv
from functools import lru_cache

from config import PROJECT_ROOT

CSV_CANDIDATES = [
    "Daftar Saham - 20261004.csv",
    "Daftar Saham.csv",
]

# Common finance abbreviations that look like 3-4 letter tickers but are NOT.
NON_TICKER_WORDS = {
    "EPS", "ROE", "ROA", "PER", "PBV", "PEG", "PSR", "PCF", "LDR", "NIM",
    "NPL", "CAR", "CASA", "DPK", "IPO", "IDX", "BEI", "OJK", "ESG", "AGM",
    "RUPS", "ETF", "NAV", "YTD", "YOY", "QOQ", "USD", "IDR", "APA", "ATAU",
    "YANG", "SAHA", "SAHAM", "BANK", "RATE",
}


@lru_cache(maxsize=1)
def _load() -> dict[str, str]:
    path = None
    for name in CSV_CANDIDATES:
        p = PROJECT_ROOT / name
        if p.exists():
            path = p
            break
    if path is None:
        # also try any CSV at project root
        for p in PROJECT_ROOT.glob("*.csv"):
            path = p
            break
    universe: dict[str, str] = {}
    if path is None:
        return universe
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get("Kode") or row.get("kode") or "").strip().upper()
                name = (row.get("Nama Perusahaan") or row.get("nama") or "").strip()
                if code:
                    universe[code] = name
    except Exception:
        return {}
    return universe


def is_loaded() -> bool:
    return len(_load()) > 0


def count() -> int:
    return len(_load())


def exists(ticker: str) -> bool:
    if not ticker:
        return False
    return ticker.strip().upper().replace(".JK", "") in _load()


def company_name(ticker: str) -> str | None:
    return _load().get((ticker or "").strip().upper().replace(".JK", ""))


def is_non_ticker_word(token: str) -> bool:
    return (token or "").strip().upper() in NON_TICKER_WORDS


def resolve_ticker(candidate: str | None, text: str) -> str | None:
    """Return a valid IDX ticker found in `candidate` or `text`, else None.

    A candidate is accepted only if it exists in the CSV universe. We also scan
    4-letter uppercase tokens in the text and keep the first that is a real
    ticker (and not a finance abbreviation).
    """
    uni = _load()
    if candidate:
        c = candidate.strip().upper().replace(".JK", "")
        if c in uni:
            return c
    import re
    for tok in re.findall(r"\b[A-Z]{4}\b", (text or "").upper()):
        if tok in uni and not is_non_ticker_word(tok):
            return tok
    return None


def unknown_ticker_like(candidate: str | None, text: str) -> str | None:
    """Return a ticker-like token (4 uppercase letters, not a finance word)
    that is NOT in the universe - i.e. the user named a code that does not
    exist. Used to give a precise "not registered" message without API cost.
    """
    import re
    uni = _load()
    cands = []
    if candidate:
        cands.append(candidate.strip().upper().replace(".JK", ""))
    cands += re.findall(r"\b[A-Z]{4}\b", (text or "").upper())
    for tok in cands:
        if (re.fullmatch(r"[A-Z]{4}", tok) and tok not in uni
                and not is_non_ticker_word(tok)):
            return tok
    return None
