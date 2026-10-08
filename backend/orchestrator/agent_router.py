"""Agent router (PRD 14).

Maps a detected intent to one of the four routing lanes. The orchestrator
uses this to decide its path. Kept small and pure for testability.
"""
from __future__ import annotations

SIMPLE = "simple"
SINGLE_CAPABILITY = "single_capability"
MULTI_CAPABILITY = "multi_capability"
PERSONA_MISMATCH = "persona_mismatch"
REJECT = "reject"


def route(intent: str, personas: list[str], needs_macro_numbers: bool) -> str:
    if needs_macro_numbers or intent == "out_of_scope":
        return REJECT
    if intent == "price":
        return SIMPLE
    if intent in ("single_metric",):
        return SINGLE_CAPABILITY
    if intent == "multi_analysis":
        return MULTI_CAPABILITY
    # mixed persona -> factory lane
    if len(set(personas)) >= 2:
        return PERSONA_MISMATCH
    return SINGLE_CAPABILITY
