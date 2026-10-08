"""Central configuration loader for AISector-MoGent.

Loads from .env (python-dotenv). Supports BOTH the PRD variable names
(ORCHESTRATOR_MODEL, SPECIALIST_MODEL, SYNTHESIZER_MODEL) and the simpler
names present in the user's .env (MODEL_NAME, MODEL_NAME_2).

The API key is read ONLY here and never logged or sent to the LLM.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is a hard dep but stay defensive
    def load_dotenv(*_a, **_k):
        return False

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
AGENTS_DIR = DATA_DIR / "agents"
BASE_AGENTS_DIR = AGENTS_DIR / "base"
DERIVED_AGENTS_DIR = AGENTS_DIR / "derived"
REGISTRY_PATH = AGENTS_DIR / "registry.json"
CONVERSATIONS_DIR = DATA_DIR / "conversations"
BACKEND_DIR = PROJECT_ROOT / "backend"
GLOSSARY_PATH = BACKEND_DIR / "grounding" / "glossary.json"
SECTOR_TEMPLATES_DIR = BACKEND_DIR / "sector_templates"
ORCH_MEMORY_PATH = BACKEND_DIR / "orchestrator" / "memory.json"

load_dotenv(PROJECT_ROOT / ".env")


def _get(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.getenv(n)
        if v is not None and v != "":
            return v
    return default


class Config:
    """Resolved runtime configuration (read-only view of env)."""

    OLLAMA_BASE_URL: str = _get("OLLAMA_BASE_URL", default="http://localhost:11434")

    # qwen2.5 is more schema-compliant -> orchestrator & synthesizer.
    # deepseek-r1 is a reasoning model -> specialists (we strip <think>).
    ORCHESTRATOR_MODEL: str = _get("ORCHESTRATOR_MODEL", "MODEL_NAME_2", default="qwen2.5:7b")
    SPECIALIST_MODEL: str = _get("SPECIALIST_MODEL", "MODEL_NAME", default="deepseek-r1:7b")
    SYNTHESIZER_MODEL: str = _get("SYNTHESIZER_MODEL", "MODEL_NAME_2", default="qwen2.5:7b")
    AGENT_MODEL: str = _get("AGENT_MODEL", "MODEL_NAME_2", default="qwen2.5:7b")

    LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", default="0.1"))

    TOOL_TIMEOUT_SECONDS: int = int(_get("TOOL_TIMEOUT_SECONDS", default="30"))
    TOOL_MAX_RETRY: int = int(_get("TOOL_MAX_RETRY", default="2"))

    MAX_A2A_DEPTH: int = int(_get("MAX_A2A_DEPTH", default="3"))
    FACTORY_MAX_PARENTS: int = int(_get("FACTORY_MAX_PARENTS", default="3"))
    FACTORY_MAX_LINEAGE_DEPTH: int = int(_get("FACTORY_MAX_LINEAGE_DEPTH", default="3"))
    FACTORY_MATCH_THRESHOLD: float = float(_get("FACTORY_MATCH_THRESHOLD", default="0.75"))

    SECTORS_API_KEY: str | None = _get("SECTORS_API_KEY")
    SECTORS_BASE_URL: str = _get("SECTORS_BASE_URL", default="https://api.sectors.app/v2")

    # Optional BPS (Badan Pusat Statistik) WebAPI key. If present, BPS is used
    # as the preferred source for Indonesian inflation; otherwise World Bank.
    BPS_API_KEY: str | None = _get("BPS_API_KEY")
    BPS_INFLATION_VAR: str = _get("BPS_INFLATION_VAR", default="2212")

    NUMBER_VALIDATOR_MAX_REGEN: int = int(_get("NUMBER_VALIDATOR_MAX_REGEN", default="2"))

    @classmethod
    def has_api_key(cls) -> bool:
        return bool(cls.SECTORS_API_KEY)

    @classmethod
    def masked_key(cls) -> str:
        k = cls.SECTORS_API_KEY or ""
        if len(k) <= 8:
            return "****" if k else "(not set)"
        return f"{k[:4]}...{k[-4:]}"

    @classmethod
    def as_public_dict(cls) -> dict:
        """Safe to expose via API / debug. Never includes the API key value."""
        return {
            "ollama_base_url": cls.OLLAMA_BASE_URL,
            "orchestrator_model": cls.ORCHESTRATOR_MODEL,
            "specialist_model": cls.SPECIALIST_MODEL,
            "synthesizer_model": cls.SYNTHESIZER_MODEL,
            "llm_temperature": cls.LLM_TEMPERATURE,
            "max_a2a_depth": cls.MAX_A2A_DEPTH,
            "factory_max_parents": cls.FACTORY_MAX_PARENTS,
            "factory_match_threshold": cls.FACTORY_MATCH_THRESHOLD,
            "sectors_api_key_present": cls.has_api_key(),
            "sectors_api_key_masked": cls.masked_key(),
        }


@lru_cache(maxsize=1)
def ensure_dirs() -> None:
    for d in (DATA_DIR, AGENTS_DIR, BASE_AGENTS_DIR, DERIVED_AGENTS_DIR, CONVERSATIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)


config = Config()
