"""Factory validation (PRD 9.7).

A derived agent is rejected if:
  1. schema invalid
  2. uses a tool outside the registry OR outside the union of parent tools
  3. locked_constraints are reduced vs parents
  4. agent_id collides (handled by versioned filename, not here)
  5. smoke test fails (separate module)
  6. parents > 3 OR lineage depth > 3
"""
from __future__ import annotations

from config import config
from backend.utcp.registry import TOOL_SPECS

REQUIRED_FIELDS = [
    "agent_id", "version", "kind", "status", "personas", "capabilities",
    "tools", "output_format", "locked_constraints", "lineage",
]


class ValidationError(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def validate_derived(spec: dict, parents: list[dict]) -> list[str]:
    """Return list of validation errors (empty => valid)."""
    errors: list[str] = []

    # 1. schema
    for f in REQUIRED_FIELDS:
        if f not in spec:
            errors.append(f"skema: field wajib '{f}' hilang")
    if spec.get("kind") != "derived":
        errors.append("skema: kind harus 'derived'")

    # 6. parents / lineage depth
    if len(parents) > config.FACTORY_MAX_PARENTS:
        errors.append(f"induk {len(parents)} > maks {config.FACTORY_MAX_PARENTS}")
    depth = _lineage_depth(spec, parents)
    if depth > config.FACTORY_MAX_LINEAGE_DEPTH:
        errors.append(f"kedalaman lineage {depth} > maks {config.FACTORY_MAX_LINEAGE_DEPTH}")

    # 2. tool whitelist: registry + union of parent tools
    parent_tools = set()
    for p in parents:
        parent_tools.update(p.get("tools", []))
    for t in spec.get("tools", []):
        if t not in TOOL_SPECS:
            errors.append(f"tool '{t}' tidak terdaftar di registry")
        elif t not in parent_tools:
            errors.append(f"tool '{t}' di luar whitelist induk")

    # 3. locked_constraints not reduced
    parent_locked = set()
    for p in parents:
        parent_locked.update(p.get("locked_constraints", []))
    child_locked = set(spec.get("locked_constraints", []))
    missing = parent_locked - child_locked
    if missing:
        errors.append(f"locked_constraints berkurang: hilang {sorted(missing)}")

    # 7. presentation block invariants (Web-Cards 8.1, W-T10)
    pres = spec.get("presentation")
    if isinstance(pres, dict):
        order = pres.get("card_order")
        if isinstance(order, list) and "trace" not in order:
            errors.append("presentation.card_order harus menyertakan 'trace' (W3)")
        mfc = pres.get("max_facts_per_card")
        if isinstance(mfc, (int, float)) and mfc > 8:
            errors.append("presentation.max_facts_per_card tidak boleh melebihi 8 (W4)")

    return errors


def _lineage_depth(spec: dict, parents: list[dict]) -> int:
    """Depth = 1 + max parent depth. Base agents have depth 0."""
    if not parents:
        return 1
    best = 0
    for p in parents:
        p_parents = (p.get("lineage", {}) or {}).get("parents", [])
        d = 0 if p.get("kind") == "base" else (1 + len(p_parents))
        best = max(best, d)
    return best + 1
