"""A2A agent discovery registry (PRD 15).

Thin discovery layer over the factory AgentRegistry: lists agent cards and
resolves an agent spec by id for A2A routing.
"""
from __future__ import annotations

from backend.agent_factory.registry import AgentRegistry
from .agent_card import build_card


class A2AAgentRegistry:
    def __init__(self, registry: AgentRegistry):
        self.reg = registry

    def cards(self) -> list[dict]:
        return [build_card(s) for s in self.reg.all_active()]

    def card(self, agent_id: str) -> dict | None:
        spec = self.reg.get(agent_id)
        return build_card(spec) if spec else None

    def resolve(self, agent_id: str) -> dict | None:
        return self.reg.get(agent_id)
