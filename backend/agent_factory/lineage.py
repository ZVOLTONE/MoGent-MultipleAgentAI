"""Lineage block construction and rendering (PRD 9.2, 9.9)."""
from __future__ import annotations

from datetime import datetime, timezone


def build(parents: list[dict], operation: str, trigger_query: str, rationale: str,
          overrides: dict | None = None, modifiers: list[str] | None = None) -> dict:
    return {
        "parents": [{"agent_id": p["agent_id"], "version": p.get("version", "1.0.0")}
                    for p in parents],
        "operation": operation,
        "created_by": "agent_factory",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "trigger_query": trigger_query,
        "rationale": rationale,
        "overrides": overrides or {},
        "modifiers": modifiers or [],
    }


def render(spec: dict) -> str:
    lin = spec.get("lineage", {}) or {}
    parents = lin.get("parents", [])
    parent_str = ", ".join(f"{p['agent_id']}@{p.get('version','1.0.0')}" for p in parents) or "(tidak ada)"
    lines = [
        f"Agent     : {spec.get('agent_id')}@{spec.get('version')}  (kind: {spec.get('kind')})",
        f"Operasi   : {lin.get('operation')}",
        f"Induk     : {parent_str}",
        f"Dibuat    : {lin.get('created_at')}",
        f"Pemicu    : {lin.get('trigger_query')}",
        f"Alasan    : {lin.get('rationale')}",
    ]
    if lin.get("overrides"):
        lines.append(f"Override  : {lin.get('overrides')}")
    return "\n".join(lines)
