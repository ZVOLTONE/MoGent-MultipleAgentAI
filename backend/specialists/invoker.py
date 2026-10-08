"""Specialist invoker (PRD 6.2, 15, 16).

Specialists (risk_challenger, valuation_analyst, catalyst_analyst,
news_sentiment) are declarative base-agent specs executed by the SAME
agent_runner. This module wraps that execution for A2A collaboration so a
persona agent can call a specialist and receive a result that references
fact_ids rather than free text numbers.

Keeping specialists as specs (not bespoke Python) means the Agent Factory can
also compose them, per PRD "agent adalah spec JSON".
"""
from __future__ import annotations

from backend.a2a.protocol import A2ABus
from backend.runtime.agent_runner import AgentRunner
from backend.utcp.cache import RequestCache

SPECIALIST_IDS = ["risk_challenger", "valuation_analyst", "catalyst_analyst", "news_sentiment"]


def is_specialist(agent_id: str) -> bool:
    return agent_id in SPECIALIST_IDS


class SpecialistInvoker:
    def __init__(self, registry, runner: AgentRunner):
        self.reg = registry
        self.runner = runner

    def call(self, specialist_id: str, caller: str, ticker: str, user_query: str,
             bus: A2ABus, cache: RequestCache, context: dict | None = None,
             shared_identity=None) -> dict:
        """Run a specialist via A2A. Returns the A2A response dict."""
        task = f"{specialist_id}: analyze {ticker}"
        allowed, reason = bus.can_call(specialist_id, task)
        if not allowed:
            return {"status": "error", "result": {"reason": reason}}

        spec = self.reg.get(specialist_id)
        if not spec:
            return {"status": "error", "result": {"reason": f"specialist {specialist_id} tidak ada"}}

        msg = bus.send(caller, specialist_id, task, context or {"ticker": ticker})
        bus.enter()
        try:
            out = self.runner.run(spec, ticker, user_query, cache,
                                  shared_identity=shared_identity)
        finally:
            bus.leave()

        result = {
            "agent_id": specialist_id,
            "analysis_text": out.get("analysis_text", ""),
            "fact_ids": [f["fact_id"] for f in out.get("facts", [])],
            "evidence_ids": out.get("evidence_ids", []),
            "confidence": out.get("confidence", 0.0),
            "limitations": out.get("limitations", []),
            "_agent_output": out,
        }
        bus.receive(msg, out.get("status", "success"), result)
        return {"status": out.get("status", "success"), "result": result}
