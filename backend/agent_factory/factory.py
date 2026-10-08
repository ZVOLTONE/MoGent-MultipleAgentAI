"""Agent Factory (PRD 9) - the core feature.

Decides whether to REUSE / COMPOSE / MODIFY an agent for a detected persona
need, builds the derived spec via merge rules, validates it (9.7), smoke
tests it (9.4 step 7), and registers it append-only. Base agents are never
touched.
"""
from __future__ import annotations

from config import config
from . import merge_rules, validator, smoke_test, lineage as lineage_mod, fingerprint
from .registry import AgentRegistry

# persona -> primary base agent
PERSONA_TO_AGENT = {
    "complete_beginner": "investment_guide",
    "fundamental_investor": "fundamental_analyst",
    "macro_strategist": "macro_intelligence",
    "wealth_preservation": "wealth_guardian",
    "senior_investor": "wealth_guardian",
}

# which persona is "dominant" (risk/preservation wins tie as per 9.5)
DOMINANCE_RANK = {
    "wealth_preservation": 3,
    "senior_investor": 3,
    "macro_strategist": 2,
    "fundamental_investor": 2,
    "complete_beginner": 1,
}


class FactoryDecision:
    def __init__(self, action: str, **kw):
        self.action = action  # "use_existing" | "reuse" | "compose" | "modify" | "fallback"
        self.__dict__.update(kw)

    def to_public(self) -> dict:
        d = dict(self.__dict__)
        # avoid dumping full specs
        for k in ("spec", "parents_specs"):
            d.pop(k, None)
        return d


class AgentFactory:
    def __init__(self, registry: AgentRegistry):
        self.reg = registry

    # -- scoring (9.4 step 2) -------------------------------------------------
    def score_agent(self, spec: dict, personas: list[str], capabilities: list[str]) -> float:
        ap = set(spec.get("personas", []))
        ac = set(spec.get("capabilities", []))
        want_p = set(personas)
        want_c = set(capabilities)
        p_score = len(ap & want_p) / len(want_p) if want_p else 0.0
        c_score = len(ac & want_c) / len(want_c) if want_c else 0.0
        # agent should not bring many unwanted personas
        extra_penalty = 0.1 * len(ap - want_p)
        return max(0.0, 0.6 * p_score + 0.4 * c_score - extra_penalty)

    def best_existing(self, personas, capabilities) -> tuple[dict | None, float]:
        best, best_score = None, 0.0
        for spec in self.reg.all_active():
            if not spec.get("personas"):
                continue  # specialists are not persona matches
            s = self.score_agent(spec, personas, capabilities)
            if s > best_score:
                best, best_score = spec, s
        return best, best_score

    # -- decide (9.4 step 3-4) ------------------------------------------------
    def decide(self, personas, capabilities, modifiers, trigger_query) -> FactoryDecision:
        personas = [p for p in (personas or []) if p]
        capabilities = capabilities or []
        modifiers = modifiers or []

        fp = fingerprint.compute(personas, capabilities, modifiers)

        # REUSE: identical fingerprint already produced a derived agent (9.8, D)
        existing_derived = self.reg.find_by_fingerprint(fp)
        if existing_derived:
            return FactoryDecision("reuse", agent_id=existing_derived["agent_id"],
                                   version=existing_derived["version"], fingerprint=fp,
                                   spec=existing_derived, scores={})

        best, best_score = self.best_existing(personas, capabilities)
        scores = {s["agent_id"]: round(self.score_agent(s, personas, capabilities), 2)
                  for s in self.reg.all_active() if s.get("personas")}

        # single existing agent is good enough AND no simplifying modifier needed
        if best and best_score >= config.FACTORY_MATCH_THRESHOLD and not modifiers:
            return FactoryDecision("use_existing", agent_id=best["agent_id"],
                                   version=best["version"], score=round(best_score, 2),
                                   fingerprint=fp, spec=best, scores=scores)

        # choose parents = base agents for each detected persona
        parent_ids = []
        for p in personas:
            aid = PERSONA_TO_AGENT.get(p)
            if aid and aid not in parent_ids:
                parent_ids.append(aid)
        if not parent_ids and best:
            parent_ids = [best["agent_id"]]
        parent_ids = parent_ids[: config.FACTORY_MAX_PARENTS]

        parents_specs = [self.reg.get(aid) for aid in parent_ids if self.reg.get(aid)]
        if not parents_specs:
            return FactoryDecision("fallback", reason="tidak ada induk yang dapat dipakai",
                                   fingerprint=fp, scores=scores)

        operation = "compose" if len(parents_specs) >= 2 else "modify"
        if modifiers:
            operation = "compose_modify" if len(parents_specs) >= 2 else "modify"

        return FactoryDecision(operation, parent_ids=parent_ids, parents_specs=parents_specs,
                               fingerprint=fp, scores=scores, best_score=round(best_score, 2))

    # -- build + validate + register (9.4 step 5-8) ---------------------------
    def create(self, decision: FactoryDecision, personas, capabilities, modifiers,
               trigger_query) -> dict:
        parents = decision.parents_specs
        dominant_index = self._dominant_index(parents, personas)

        if len(parents) >= 2:
            body = merge_rules.compose(parents, dominant_index=dominant_index)
            op = "compose"
        else:
            parent = parents[0]
            body = {
                "personas": list(parent.get("personas", [])),
                "capabilities": list(parent.get("capabilities", [])),
                "tools": list(parent.get("tools", [])),
                "constraints": list(parent.get("constraints", [])),
                "locked_constraints": list(parent.get("locked_constraints", [])),
                "priority_order": list(parent.get("priority_order", [])),
                "reasoning_style": {"primary": parent.get("reasoning_style", ""), "secondary": []},
                "output_format": dict(parent.get("output_format", {})),
                "collaboration": dict(parent.get("collaboration", {"may_call": []})),
            }
            if parent.get("presentation"):
                body["presentation"] = dict(parent["presentation"])
            op = "modify"

        overrides = self._overrides_from_modifiers(modifiers, personas)
        applied_notes = []
        if overrides:
            body, applied_notes = merge_rules.apply_overrides(body, overrides)
            if op == "compose":
                op = "compose_modify"

        agent_id = self._derive_id(personas, modifiers)
        spec = {
            "agent_id": agent_id,
            "version": "1.0.0",
            "kind": "derived",
            "status": "active",
            "immutable": False,
            "display_name": agent_id.replace("_", " ").title(),
            "role": self._derive_role(parents),
            "goals": merge_rules._union(*[p.get("goals", []) for p in parents]),
            **body,
            "persona_fingerprint": decision.fingerprint,
            "lineage": lineage_mod.build(
                parents, op, trigger_query,
                rationale=self._rationale(parents, modifiers),
                overrides=overrides, modifiers=modifiers,
            ),
            "use_count": 0,
        }

        errors = validator.validate_derived(spec, parents)
        validations = {
            "schema": not any(e.startswith("skema") for e in errors),
            "tool_whitelist": not any("tool" in e for e in errors),
            "locked_constraints": not any("locked_constraints" in e for e in errors),
            "parents_depth": not any("induk" in e or "lineage" in e for e in errors),
        }
        if errors:
            return {"ok": False, "errors": errors, "validations": validations,
                    "operation": op, "override_notes": applied_notes, "spec": spec}

        passed, smoke_detail = smoke_test.run(spec)
        validations["smoke_test"] = passed
        if not passed:
            return {"ok": False, "errors": [smoke_detail], "validations": validations,
                    "operation": op, "override_notes": applied_notes, "spec": spec}

        path = self.reg.register_derived(spec)
        return {"ok": True, "errors": [], "validations": validations, "operation": op,
                "override_notes": applied_notes, "spec": spec, "path": str(path),
                "smoke_detail": smoke_detail}

    # -- helpers --------------------------------------------------------------
    def _dominant_index(self, parents, personas) -> int:
        best_i, best_rank = 0, -1
        for i, p in enumerate(parents):
            rank = max((DOMINANCE_RANK.get(x, 0) for x in p.get("personas", [])), default=0)
            if rank > best_rank:
                best_rank, best_i = rank, i
        return best_i

    def _overrides_from_modifiers(self, modifiers, personas) -> dict:
        ov = {}
        if "simple_language" in modifiers or "complete_beginner" in personas:
            ov["output_format.language_level"] = "simple"
        if "sector_bank" in modifiers:
            ov["sector_focus"] = "bank"
        if "downside_focus" in modifiers or "wealth_preservation" in personas:
            ov["extra_constraints"] = ["tidak membahas strategi spekulatif atau leverage"]
        return ov

    def _derive_id(self, personas, modifiers) -> str:
        parts = ["derived"]
        tag = {
            "complete_beginner": "beginner",
            "wealth_preservation": "wealth",
            "senior_investor": "senior",
            "fundamental_investor": "fundamental",
            "macro_strategist": "macro",
        }
        for p in personas:
            if p in tag and tag[p] not in parts:
                parts.append(tag[p])
        if "sector_bank" in modifiers and "bank" not in parts:
            parts.append("bank")
        if len(parts) == 1:
            parts.append("custom")
        base = "_".join(parts)
        # avoid collision -> suffix (append-only, never overwrite)
        if self.reg.exists(base):
            n = 2
            while self.reg.exists(f"{base}_{n}"):
                n += 1
            base = f"{base}_{n}"
        return base

    def _derive_role(self, parents) -> str:
        return "Agent turunan gabungan: " + " + ".join(p.get("display_name", p["agent_id"]) for p in parents)

    def _rationale(self, parents, modifiers) -> str:
        names = " + ".join(p["agent_id"] for p in parents)
        mod = f" dengan penyesuaian {modifiers}" if modifiers else ""
        return f"Tidak ada agent tunggal yang mencakup kebutuhan; menggabungkan {names}{mod}."
