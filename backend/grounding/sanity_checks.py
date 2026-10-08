"""Data sanity checks (PRD 10.6).

Before a fact enters the ledger as a business fact, its value is checked
against a plausible range. Out-of-range values are flagged ``anomaly`` and
are NOT narrated as business facts (UAT: "PER 12.806.979.354" was a field
mapping error, not a real P/E).
"""
from __future__ import annotations

# metric -> (min, max) plausible range
RANGES = {
    "pe_ratio": (0.0, 200.0),
    "pb_ratio": (0.0, 50.0),
    "ps_ratio": (0.0, 100.0),
    "dividend_yield": (0.0, 30.0),      # percent
    "ldr": (0.0, 300.0),                # percent
    "roe": (-100.0, 100.0),             # percent
    "payout_ratio": (0.0, 200.0),       # percent
    "q_roe_annualized": (-100.0, 100.0),         # percent
    "insider_ownership": (0.0, 100.0),           # percent
    "institutional_ownership": (0.0, 100.0),     # percent
    "institutional_float_ownership": (0.0, 100.0),  # percent
}


def is_anomalous(metric: str, value) -> bool:
    if value is None or not isinstance(value, (int, float)):
        return False
    rng = RANGES.get(metric)
    if not rng:
        return False
    lo, hi = rng
    return not (lo <= value <= hi)


def check(metric: str, value) -> tuple[bool, str | None]:
    """Return (anomalous, reason)."""
    if is_anomalous(metric, value):
        lo, hi = RANGES.get(metric, (None, None))
        return True, f"{metric}={value} di luar rentang wajar [{lo}, {hi}]"
    return False, None
