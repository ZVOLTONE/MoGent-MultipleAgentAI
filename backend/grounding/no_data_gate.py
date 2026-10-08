"""No-Data Gate (PRD 10.2).

Before calling the LLM for an agent, check the Evidence Store. If there is
no ``ok`` evidence for that agent, the LLM is NOT called and the agent
returns {status: no_data, reason: ...}. This is what stops Macro Intelligence
from writing a BI Rate when it has no macro tool (T18), and what makes every
agent return no_data when the API key is disabled (T20).
"""
from __future__ import annotations

from backend.grounding.evidence_store import EvidenceStore


def passes(store: EvidenceStore) -> bool:
    return store.has_ok()


def reason_from_store(store: EvidenceStore) -> str:
    records = store.all()
    if not records:
        return "tidak ada tool yang dipanggil untuk agent ini"
    reasons = []
    for r in records:
        if r.result_status != "ok":
            reasons.append(f"{r.tool}: {r.result_status}" + (f" ({r.http_status})" if r.http_status else ""))
    if reasons:
        return "semua tool gagal/kosong -> " + "; ".join(reasons)
    return "tidak ada data valid"
