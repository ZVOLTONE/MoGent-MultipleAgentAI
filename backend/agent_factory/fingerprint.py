"""Persona fingerprint (PRD 9.8).

A stable hash of the normalized (personas, capabilities, modifiers) set.
Used so a repeated similar request reuses an existing derived agent (T11, D).
"""
from __future__ import annotations

import hashlib
import json


def compute(personas: list[str], capabilities: list[str], modifiers: list[str]) -> str:
    norm = {
        "personas": sorted(set(p.strip().lower() for p in personas if p)),
        "capabilities": sorted(set(c.strip().lower() for c in capabilities if c)),
        "modifiers": sorted(set(m.strip().lower() for m in modifiers if m)),
    }
    raw = json.dumps(norm, sort_keys=True, ensure_ascii=False)
    return "fp_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def from_spec(spec: dict) -> str:
    return compute(
        spec.get("personas", []),
        spec.get("capabilities", []),
        (spec.get("lineage", {}) or {}).get("modifiers", []),
    )
