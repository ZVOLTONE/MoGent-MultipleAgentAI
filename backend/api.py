"""FastAPI server for AISector-MoGent (PRD 1: primary output for React).

Endpoints (all JSON, CORS enabled for a React dev frontend):

  GET  /health                      service + ollama + api-key status
  GET  /config                      safe public config (no secrets)
  POST /query                       main entry: {query, debug?} -> full result
  GET  /agents                      list agent cards (base + derived)
  GET  /agents/{agent_id}           full agent spec
  GET  /agents/{agent_id}/lineage   lineage of a derived agent
  GET  /tools                       UTCP tool manual (discovery)

Run:
  uvicorn backend.api:app --reload --port 8000
or:
  python -m backend.api
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import config, ensure_dirs
from backend.agent_factory.registry import AgentRegistry, IntegrityError
from backend.agent_factory import lineage as lineage_mod
from backend.a2a.agent_card import build_card
from backend.orchestrator.orchestrator import Orchestrator
from backend.llm.ollama import OllamaClient
from backend.utcp.registry import TOOL_SPECS
from backend.presentation import routes as cards_routes

app = FastAPI(title="AISector-MoGent API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev; tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards_routes.router)

_orchestrator: Orchestrator | None = None
_startup_error: str | None = None


@app.on_event("startup")
def _startup():
    global _orchestrator, _startup_error
    ensure_dirs()
    try:
        _orchestrator = Orchestrator(debug=False)
        cards_routes.set_registry(_orchestrator.registry)
    except IntegrityError as e:
        _startup_error = str(e)
    except Exception as e:  # pragma: no cover
        _startup_error = f"{type(e).__name__}: {e}"


def _orc() -> Orchestrator:
    if _orchestrator is None:
        raise HTTPException(status_code=503,
                            detail=_startup_error or "orchestrator belum siap")
    return _orchestrator


class QueryRequest(BaseModel):
    query: str
    debug: bool = False


@app.get("/health")
def health():
    ollama = OllamaClient()
    return {
        "status": "error" if _startup_error else "ok",
        "startup_error": _startup_error,
        "ollama_reachable": ollama.available(),
        "ollama_models": ollama.list_models(),
        "sectors_api_key_present": config.has_api_key(),
    }


@app.get("/config")
def get_config():
    return config.as_public_dict()


@app.post("/query")
def query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query kosong")
    orc = _orc()
    orc.debug = req.debug
    orc.runner.debug = req.debug
    result = orc.handle(req.query)
    if not req.debug:
        result.pop("_trace", None)
    return result


@app.get("/agents")
def list_agents():
    orc = _orc()
    base = [build_card(s) for s in orc.registry.base_agents()]
    derived = [build_card(s) for s in orc.registry.derived_agents()]
    return {"base": base, "derived": derived,
            "counts": {"base": len(base), "derived": len(derived)}}


@app.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    spec = _orc().registry.get(agent_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' tidak ditemukan")
    return spec


@app.get("/agents/{agent_id}/lineage")
def get_lineage(agent_id: str):
    spec = _orc().registry.get(agent_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' tidak ditemukan")
    if spec.get("kind") != "derived":
        return {"agent_id": agent_id, "kind": "base", "lineage": None,
                "note": "agent base tidak memiliki lineage turunan"}
    return {"agent_id": agent_id, "kind": "derived",
            "lineage": spec.get("lineage"),
            "lineage_render": lineage_mod.render(spec)}


@app.get("/tools")
def list_tools():
    return {"tools": [{"name": k, **v} for k, v in TOOL_SPECS.items()]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=False)
