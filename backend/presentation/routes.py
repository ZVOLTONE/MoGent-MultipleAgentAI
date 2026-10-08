"""POST /cards (PRD Web-Cards 12).

Body = a /query result (the full JSON, including facts/evidence/_trace when
available). Response = the card schema (9.2). Stateless and fast: no LLM, no
tool calls on the MVP.

Presentation profile selection (PRD 8.3):
  * if the /query result used an Agent Factory presentation profile
    (agent_factory.new_agent_id points to a derived cards agent) use it;
  * otherwise fall back to the base presentation_composer spec.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.presentation import card_builder

router = APIRouter()

# Lazily shared registry (set by api.py at startup); falls back to its own.
_registry = None


def set_registry(registry) -> None:
    global _registry
    _registry = registry


def _get_registry():
    global _registry
    if _registry is None:
        from backend.agent_factory.registry import AgentRegistry
        _registry = AgentRegistry()
    return _registry


class CardsRequest(BaseModel):
    # Accept the whole /query result. Use a permissive model so the frontend
    # can forward the response verbatim.
    class Config:
        extra = "allow"

    answer: str = ""
    ticker: str | None = None
    facts: list[dict] = []
    evidence: list[dict] = []
    agents_used: list[str] = []
    agent_factory: dict = {}
    limitations: list[Any] = []
    contradictions: list[Any] = []
    persona: list[str] = []
    tool_calls: list[dict] = []


@router.post("/cards")
def build_cards_endpoint(req: CardsRequest):
    result = req.model_dump()
    # the trace (with agent_outputs/identity) may be forwarded under _trace
    extra = getattr(req, "model_extra", None) or {}
    if "_trace" in extra:
        result["_trace"] = extra["_trace"]

    agent_spec = _select_profile_spec(result)
    return card_builder.build_cards(result, agent_spec)


def _select_profile_spec(result: dict) -> dict | None:
    reg = _get_registry()
    af = result.get("agent_factory") or {}
    new_id = af.get("new_agent_id")
    # Only use a derived agent as a *presentation* profile if it actually
    # carries a presentation block (i.e., a cards-* profile). Analysis-only
    # derived agents must not reshape cards.
    if new_id:
        spec = reg.get(new_id)
        if spec and (spec.get("presentation") or spec.get("capabilities", []) and
                     "card_composition" in spec.get("capabilities", [])):
            if spec.get("presentation"):
                return spec
    return reg.get("presentation_composer")
