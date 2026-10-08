"""Presentation profile resolution (PRD Web-Cards 8.1, 8.3).

A profile is the ``presentation`` block of the active agent spec
(presentation_composer or a derived variant). It controls ONLY ordering,
density, and explanation style — never the facts themselves.
"""
from __future__ import annotations

DEFAULT_PROFILE = {
    "card_order": ["summary", "valuation", "performance", "ownership", "macro",
                   "price", "chart", "news", "risk", "trace"],
    "density": "normal",            # compact | normal | detailed
    "explain_level": "simple",      # simple | standard | expert
    "font_scale": 1.0,
    "glossary_hints": False,
    "max_facts_per_card": 8,
}

# density -> how many bullets a summary/metrics card may show
_DENSITY_BULLETS = {"compact": 2, "normal": 3, "detailed": 3}


def resolve(agent_spec: dict | None) -> dict:
    """Merge an agent's presentation block over the defaults (clamped to W4)."""
    prof = dict(DEFAULT_PROFILE)
    block = (agent_spec or {}).get("presentation") or {}
    for k, v in block.items():
        if k in prof and v is not None:
            prof[k] = v

    # --- enforce invariants (PRD W3, W4, W-T10) --------------------------
    order = list(prof.get("card_order") or DEFAULT_PROFILE["card_order"])
    if "trace" in order:
        order = [c for c in order if c != "trace"]
    order.append("trace")                       # trace always last, never removed
    prof["card_order"] = order

    try:
        prof["max_facts_per_card"] = min(8, int(prof["max_facts_per_card"]))
    except Exception:
        prof["max_facts_per_card"] = 8

    prof["bullets_per_card"] = _DENSITY_BULLETS.get(prof["density"], 3)
    try:
        prof["font_scale"] = max(0.8, min(2.0, float(prof["font_scale"])))
    except Exception:
        prof["font_scale"] = 1.0
    return prof


def wants_glossary(profile: dict) -> bool:
    return bool(profile.get("glossary_hints")) or profile.get("explain_level") == "simple"
