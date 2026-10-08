"""Number Validator (PRD 10.5).

The LLM is instructed to write numbers ONLY as {{f_xxx}} markers. This
validator scans the raw LLM narrative (before marker substitution) and
rejects any stray numeric token that is not part of a marker and not in a
small allow-list (years, list indices, glossary abbreviations like PER/PBV).

Flow:
  * validate(raw_text) -> (ok, offending_numbers)
  * caller may regenerate up to N times with a correction instruction
  * if still failing -> deterministic template (fact table, no narrative)
"""
from __future__ import annotations

import re

from backend.grounding.fact_ledger import FactLedger, _MARKER_RE

# Numbers that are allowed to appear literally in narrative.
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# Any digit sequence (optionally with . , % and x) that could be a figure.
_NUM_RE = re.compile(r"\d[\d.,]*\s*%?x?")

# Allowed standalone small ordinals / enumerations (1. 2. 3.) handled separately.
_LIST_PREFIX_RE = re.compile(r"^\s*\d+[\.\)]\s", re.MULTILINE)


def _strip_allowed(text: str) -> str:
    # remove markers
    t = _MARKER_RE.sub(" ", text)
    # remove years
    t = _YEAR_RE.sub(" ", t)
    # remove list prefixes like "1. "
    t = _LIST_PREFIX_RE.sub(" ", t)
    return t


def _is_financial_figure(tok: str) -> bool:
    """A token is a (forbidden) financial figure if it looks like a real number
    rather than a small prose count/enumeration.

    Forbidden patterns (the UAT hallucination shapes):
      * decimals: 15.3, 0,85
      * thousands separators: 6.100, 12.806.979.354
      * suffixes: 5%, 22x
      * large integers (>=3 digits): 6100, 100
    Allowed (ignored):
      * bare 1-2 digit integers used in prose like "2 hal utama"
    """
    t = tok.strip()
    if not any(ch.isdigit() for ch in t):
        return False
    if t.endswith("%") or t.endswith("x"):
        return True
    if "." in t or "," in t:
        return True
    # pure integer now
    digits = "".join(ch for ch in t if ch.isdigit())
    return len(digits) >= 3


def find_stray_numbers(raw_text: str) -> list[str]:
    stripped = _strip_allowed(raw_text or "")
    hits = []
    for m in _NUM_RE.finditer(stripped):
        tok = m.group(0).strip()
        if _is_financial_figure(tok):
            hits.append(tok)
    return hits


def validate(raw_text: str) -> tuple[bool, list[str]]:
    stray = find_stray_numbers(raw_text)
    return (len(stray) == 0, stray)


def correction_instruction(stray: list[str]) -> str:
    sample = ", ".join(stray[:6])
    return (
        "REVISI WAJIB: Anda menulis angka mentah (" + sample + "). "
        "Dilarang menulis angka apa pun secara langsung. "
        "Gunakan HANYA penanda seperti {{f_001}} untuk setiap angka. "
        "Tulis ulang jawaban dengan hanya memakai penanda fakta yang tersedia."
    )


def deterministic_template(ledger: FactLedger, identity_block: str = "") -> str:
    """Fallback when the LLM cannot stop fabricating numbers (PRD 10.5).

    Produces a structured, readable table grouped by metric category so the
    user can verify all data points directly from the tool outputs.
    """
    # Group metrics into categories for readability
    VALUATION_METRICS = {"pe_ratio", "pb_ratio", "forward_pe", "ps_ratio",
                         "intrinsic_value", "enterprise_to_ebitda"}
    FINANCIAL_METRICS = {"revenue", "earnings", "total_equity", "total_assets",
                         "roe", "gross_loan", "total_deposit", "net_interest_income",
                         "ldr", "dividend_yield", "dividend_per_share"}
    PRICE_METRICS = {"last_close_price", "period_low", "period_high", "market_cap"}
    MACRO_METRICS = {"inflation", "real_interest_rate", "usd_idr", "bi_rate"}

    groups = {
        "Valuasi": [], "Keuangan": [], "Harga & Market Cap": [],
        "Makro": [], "Lainnya": [],
    }

    facts_valid = [f for f in ledger.all() if not f.anomaly]
    for f in facts_valid:
        rendered = ledger.rendered_value(f.fact_id)
        asof = f" (per {f.as_of})" if f.as_of else ""
        src = f" [ev: {f.evidence_id}]"
        derived_tag = " *turunan*" if f.derived else ""
        line = f"  • {f.metric}: **{rendered}**{asof}{derived_tag}{src}"
        if f.metric in VALUATION_METRICS:
            groups["Valuasi"].append(line)
        elif f.metric in FINANCIAL_METRICS:
            groups["Keuangan"].append(line)
        elif f.metric in PRICE_METRICS:
            groups["Harga & Market Cap"].append(line)
        elif f.metric in MACRO_METRICS:
            groups["Makro"].append(line)
        else:
            groups["Lainnya"].append(line)

    lines = []
    if identity_block:
        lines.append(f"**{identity_block}**")
        lines.append("")

    lines.append("## Data dari Tool (mode deterministik)\n")
    for group_name, items in groups.items():
        if items:
            lines.append(f"### {group_name}")
            lines.extend(items)
            lines.append("")

    if not facts_valid:
        lines.append("_(Tidak ada fakta valid yang berhasil diambil dari tool.)_")

    lines.append("\n> **Catatan:** Narasi otomatis dinonaktifkan karena validator angka "
                 "menolak keluaran model. Data di atas berasal langsung dari API Sectors. "
                 "Simbol `*` menandai metrik turunan yang dihitung dari data mentah.")
    return "\n".join(lines)
