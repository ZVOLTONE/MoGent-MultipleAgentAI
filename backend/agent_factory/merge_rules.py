"""Merge rules for COMPOSE (PRD 9.5) and MODIFY (PRD 9.6)."""
from __future__ import annotations

import copy

LANGUAGE_LEVEL_RANK = {"simple": 0, "beginner": 0, "standard": 1, "expert": 2}

# risk/preservation-focused priorities come first in COMPOSE
RISK_FIRST = ["downside", "risiko", "resilience", "ketahanan"]

# fields MODIFY is allowed to touch (PRD 9.6 + Web-Cards 8.1)
MODIFY_ALLOWED = {
    "priority_order", "output_format", "reasoning_style", "sector_focus",
    "extra_goals", "extra_constraints", "capabilities", "tools",
    "presentation",
}
MODIFY_FORBIDDEN = {"locked_constraints", "kind", "immutable", "lineage"}


def _union(*lists) -> list:
    out = []
    for lst in lists:
        for x in (lst or []):
            if x not in out:
                out.append(x)
    return out


def _simplest_level(levels: list[str]) -> str:
    best = "standard"
    best_rank = LANGUAGE_LEVEL_RANK["standard"]
    for lv in levels:
        r = LANGUAGE_LEVEL_RANK.get(lv, 1)
        if r < best_rank:
            best_rank = r
            best = lv
    return best


def _ordered_priority(parents: list[dict]) -> list[str]:
    merged = _union(*[p.get("priority_order", []) for p in parents])
    risk = [x for x in merged if any(k in x.lower() for k in RISK_FIRST)]
    rest = [x for x in merged if x not in risk]
    return risk + rest


def compose(parents: list[dict], dominant_index: int = 0) -> dict:
    """Merge >=2 parent specs into a derived spec body (PRD 9.5)."""
    dominant = parents[dominant_index]
    others = [p for i, p in enumerate(parents) if i != dominant_index]

    personas = _union(*[p.get("personas", []) for p in parents])
    capabilities = _union(*[p.get("capabilities", []) for p in parents])
    tools = _union(*[p.get("tools", []) for p in parents])
    constraints = _union(*[p.get("constraints", []) for p in parents])
    locked = _union(*[p.get("locked_constraints", []) for p in parents])
    may_call = _union(*[(p.get("collaboration", {}) or {}).get("may_call", []) for p in parents])

    sections = _union(*[(p.get("output_format", {}) or {}).get("sections", []) for p in parents])
    if "keterbatasan" not in sections:
        sections.append("keterbatasan")

    levels = [(p.get("output_format", {}) or {}).get("language_level", "standard") for p in parents]
    language_level = _simplest_level(levels)

    reasoning = {
        "primary": dominant.get("reasoning_style", ""),
        "secondary": [p.get("reasoning_style", "") for p in others],
    }

    # carry a presentation block if any parent defines one (dominant wins)
    presentation = None
    for p in [dominant] + others:
        if p.get("presentation"):
            presentation = dict(p["presentation"])
            break

    merged = {
        "personas": personas,
        "capabilities": capabilities,
        "tools": tools,
        "constraints": constraints,
        "locked_constraints": locked,
        "priority_order": _ordered_priority(parents),
        "reasoning_style": reasoning,
        "output_format": {
            "sections": sections,
            "language": "id",
            "language_level": language_level,
        },
        "collaboration": {"may_call": may_call},
    }
    if presentation is not None:
        merged["presentation"] = presentation
    return merged


def apply_overrides(body: dict, overrides: dict) -> tuple[dict, list[str]]:
    """Apply MODIFY overrides. Returns (new_body, applied_notes).

    Forbidden fields are silently ignored here; the validator enforces that
    locked_constraints are never reduced and raises on violations.
    """
    body = copy.deepcopy(body)
    notes = []
    for key, value in (overrides or {}).items():
        root = key.split(".")[0]
        if root in MODIFY_FORBIDDEN:
            notes.append(f"ditolak: override '{key}' pada field terkunci")
            continue
        if root not in MODIFY_ALLOWED:
            notes.append(f"ditolak: override '{key}' tidak diizinkan")
            continue
        if "." in key:
            parent, child = key.split(".", 1)
            body.setdefault(parent, {})
            if isinstance(body[parent], dict):
                body[parent][child] = value
                notes.append(f"{key}={value}")
        elif key == "extra_goals":
            body["goals"] = _union(body.get("goals", []), value if isinstance(value, list) else [value])
            notes.append(f"extra_goals+={value}")
        elif key == "extra_constraints":
            body["constraints"] = _union(body.get("constraints", []),
                                         value if isinstance(value, list) else [value])
            notes.append(f"extra_constraints+={value}")
        elif key == "capabilities":
            body["capabilities"] = _union(body.get("capabilities", []),
                                          value if isinstance(value, list) else [value])
            notes.append(f"capabilities+={value}")
        elif key == "tools":
            body["tools"] = _union(body.get("tools", []),
                                   value if isinstance(value, list) else [value])
            notes.append(f"tools+={value}")
        elif key == "sector_focus":
            body["sector_focus"] = value
            notes.append(f"sector_focus={value}")
        elif key == "presentation" and isinstance(value, dict):
            # deep-merge over the parent presentation block (keeps unset keys)
            base = dict(body.get("presentation") or {})
            base.update(value)
            body["presentation"] = base
            notes.append(f"presentation+={list(value.keys())}")
        else:
            body[key] = value
            notes.append(f"{key}={value}")
    return body, notes
