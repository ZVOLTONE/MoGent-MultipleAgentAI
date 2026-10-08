"""A2A agent card (PRD 25 item 5).

A compact, discoverable description of an agent built from its spec. Used by
the orchestrator and exposed in debug / API.
"""
from __future__ import annotations


def build_card(spec: dict) -> dict:
    return {
        "agent_id": spec.get("agent_id"),
        "version": spec.get("version", "1.0.0"),
        "kind": spec.get("kind"),
        "display_name": spec.get("display_name"),
        "role": spec.get("role"),
        "personas": spec.get("personas", []),
        "capabilities": spec.get("capabilities", []),
        "tools": spec.get("tools", []),
        "may_call": (spec.get("collaboration", {}) or {}).get("may_call", []),
        "locked_constraints": spec.get("locked_constraints", []),
        "status": spec.get("status", "active"),
    }
