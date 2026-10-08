"""Fact Ledger (PRD 10.3) + controlled number rendering (PRD 10.4).

Agents never type numbers. They write narrative with ``{{fact_id}}`` markers.
Python owns the Fact Ledger and substitutes markers with formatted values.
A fact always references an evidence_id (or is marked derived with a formula
and still references the evidence it was derived from).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_MARKER_RE = re.compile(r"\{\{\s*(f_\d+)\s*\}\}")


def _round_key(value):
    """Normalize a value for the de-duplication index."""
    if isinstance(value, float):
        return round(value, 4)
    return value


@dataclass
class Fact:
    fact_id: str
    metric: str
    value: Any
    unit: str = ""
    as_of: str | None = None
    evidence_id: str | None = None
    field_path: str | None = None
    derived: bool = False
    formula: str | None = None
    anomaly: bool = False

    def to_public(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "as_of": self.as_of,
            "evidence_id": self.evidence_id,
            "field_path": self.field_path,
            "derived": self.derived,
            "formula": self.formula,
            "anomaly": self.anomaly,
        }


def format_value(value: Any, unit: str) -> str:
    if value is None:
        return "(tidak tersedia)"
    u = (unit or "").lower()
    if isinstance(value, (int, float)):
        if u in ("x", "kali"):
            return f"{value:.2f}x"
        if u in ("%", "persen"):
            return f"{value:.2f}%"
        if u in ("idr", "rp", "rupiah"):
            return _format_rupiah(value)
        if u in ("idr_tn", "triliun"):
            return f"Rp{value:,.2f} triliun"
        # plain number
        if float(value).is_integer():
            return f"{int(value):,}".replace(",", ".")
        return f"{value:,.2f}"
    return str(value)


def _format_rupiah(v: float) -> str:
    av = abs(v)
    if av >= 1e12:
        return f"Rp{v/1e12:,.2f} triliun"
    if av >= 1e9:
        return f"Rp{v/1e9:,.2f} miliar"
    if av >= 1e6:
        return f"Rp{v/1e6:,.2f} juta"
    return f"Rp{v:,.0f}".replace(",", ".")


class FactLedger:
    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}
        self._counter = 0
        self._index: dict[tuple, str] = {}  # (metric, value, unit, as_of) -> fact_id

    def add(self, metric: str, value: Any, unit: str = "", *, evidence_id: str | None = None,
            as_of: str | None = None, field_path: str | None = None, derived: bool = False,
            formula: str | None = None, anomaly: bool = False) -> Fact:
        # De-duplicate identical facts (same metric/value/unit/as_of). This stops
        # last_close_price (from overview, valuation AND daily) and merged
        # multi-agent ledgers from producing repeated facts.
        key = (metric, _round_key(value), unit, as_of)
        existing_id = self._index.get(key)
        if existing_id is not None:
            return self._facts[existing_id]
        self._counter += 1
        fid = f"f_{self._counter:03d}"
        fact = Fact(fact_id=fid, metric=metric, value=value, unit=unit, as_of=as_of,
                    evidence_id=evidence_id, field_path=field_path, derived=derived,
                    formula=formula, anomaly=anomaly)
        self._facts[fid] = fact
        self._index[key] = fid
        return fact

    def get(self, fact_id: str) -> Fact | None:
        return self._facts.get(fact_id)

    def all(self) -> list[Fact]:
        return list(self._facts.values())

    def ids(self) -> list[str]:
        return list(self._facts.keys())

    def is_empty(self) -> bool:
        return not self._facts

    def rendered_value(self, fact_id: str) -> str:
        f = self._facts.get(fact_id)
        if not f:
            return "(fakta tidak dikenal)"
        return format_value(f.value, f.unit)

    def render_markers(self, text: str) -> str:
        """Replace every {{f_xxx}} with its formatted value."""
        def _sub(m: re.Match) -> str:
            fid = m.group(1)
            if fid in self._facts:
                return self.rendered_value(fid)
            return "(data tidak tersedia)"
        return _MARKER_RE.sub(_sub, text or "")

    @staticmethod
    def extract_markers(text: str) -> list[str]:
        return _MARKER_RE.findall(text or "")

    def facts_for_prompt(self) -> list[dict]:
        """Compact list given to the LLM so it knows which markers exist."""
        out = []
        for f in self._facts.values():
            if f.anomaly:
                continue
            out.append({
                "fact_id": f.fact_id,
                "metric": f.metric,
                "rendered": self.rendered_value(f.fact_id),
                "as_of": f.as_of,
            })
        return out
