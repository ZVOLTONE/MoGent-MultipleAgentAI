"""Identity Lock (PRD 10.7).

The first step of any company analysis is to fetch ``overview`` and store
the ground-truth identity (company name, sector, subsector). This block is
injected into every agent as a fixed fact. If a narrative mentions a sector
or line of business that contradicts the ground truth (UAT: BBCA described
as "pertanian"), the validator rejects it.
"""
from __future__ import annotations

from dataclasses import dataclass

# Sector keyword -> forbidden contradicting words.
# If identity sector is Financials/Banks, these words must NOT appear.
SECTOR_FORBIDDEN = {
    "financials": [
        "pertanian", "sawit", "kelapa sawit", "jagung", "apel", "perkebunan",
        "tambang", "pertambangan", "manufaktur", "pabrik", "konstruksi",
        "ritel", "retail", "properti", "telekomunikasi", "rumah sakit",
        "hasil panen", "produk konsumen", "otomotif",
    ],
}

# Words that identify the bank/financial template.
BANK_SUBSECTORS = {"banks", "bank", "financing service", "insurance", "financials"}


@dataclass
class Identity:
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    subsector: str | None = None
    source: str = "tool"  # "tool" or "user_correction"

    def to_public(self) -> dict:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "sector": self.sector,
            "subsector": self.subsector,
            "source": self.source,
        }

    def is_bank(self) -> bool:
        s = (self.subsector or "").lower()
        sec = (self.sector or "").lower()
        return any(k in s for k in BANK_SUBSECTORS) or sec == "financials"

    def template(self) -> str:
        return "bank" if self.is_bank() else "general"


def build_identity_from_overview(symbol: str, overview: dict, company_name: str | None) -> Identity:
    ov = overview or {}
    return Identity(
        symbol=symbol.upper().replace(".JK", ""),
        company_name=company_name or ov.get("company_name"),
        sector=ov.get("sector"),
        subsector=ov.get("sub_sector") or ov.get("subsector"),
        source="tool",
    )


def check_narrative_against_identity(text: str, identity: Identity) -> list[str]:
    """Return list of contradiction phrases found in the narrative."""
    if not identity or not identity.sector:
        return []
    sector_key = identity.sector.lower()
    forbidden = SECTOR_FORBIDDEN.get(sector_key, [])
    low = (text or "").lower()
    hits = [w for w in forbidden if w in low]
    return hits
