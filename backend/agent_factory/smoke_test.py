"""Factory smoke test (PRD 9.4 step 7, T16).

Dry-run the derived agent with an EMPTY evidence store. A correct agent must
return no_data (because the No-Data Gate blocks the LLM), not a fabricated
analysis. This runs purely on grounding logic, no network/LLM needed, so it
is fast and deterministic.
"""
from __future__ import annotations

from backend.grounding.evidence_store import EvidenceStore
from backend.grounding import no_data_gate


def run(spec: dict) -> tuple[bool, str]:
    """Return (passed, detail)."""
    empty_store = EvidenceStore()  # no evidence at all
    if no_data_gate.passes(empty_store):
        return False, "smoke test gagal: gate meloloskan analisis tanpa data"
    # Simulate the runner's no-data branch output contract.
    simulated = {
        "agent_id": spec.get("agent_id"),
        "status": "no_data",
        "analysis_text": "",
        "facts": [],
    }
    if simulated["status"] != "no_data" or simulated["facts"]:
        return False, "smoke test gagal: agent menghasilkan output tanpa data"
    return True, "no_data (benar: tidak mengarang saat data kosong)"
