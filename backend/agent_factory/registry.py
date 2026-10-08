"""Agent Registry (PRD 9.8).

* base agents are read-only; their sha256 is locked in registry.json
* derived agents are append-only (filename includes version, never overwritten)
* at startup, base file hashes are compared with registry.json; mismatch -> stop
* NO delete function is exposed (P3)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config import (BASE_AGENTS_DIR, DERIVED_AGENTS_DIR, REGISTRY_PATH, ensure_dirs)


class IntegrityError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class AgentRegistry:
    def __init__(self) -> None:
        ensure_dirs()
        self._agents: dict[str, dict] = {}       # key: agent_id (active, latest version)
        self._versions: dict[str, list[str]] = {}  # agent_id -> [versions]
        self._all_specs: dict[str, dict] = {}    # key: agent_id@version -> spec
        self.load()

    # -- loading --------------------------------------------------------------
    def load(self) -> None:
        self._agents.clear()
        self._versions.clear()
        self._all_specs.clear()
        for p in sorted(BASE_AGENTS_DIR.glob("*.json")):
            spec = _load_json(p)
            self._register_in_memory(spec, path=p)
        for p in sorted(DERIVED_AGENTS_DIR.glob("*.json")):
            spec = _load_json(p)
            self._register_in_memory(spec, path=p)

    def _register_in_memory(self, spec: dict, path: Path | None = None) -> None:
        aid = spec["agent_id"]
        ver = spec.get("version", "1.0.0")
        self._all_specs[f"{aid}@{ver}"] = spec
        self._versions.setdefault(aid, [])
        if ver not in self._versions[aid]:
            self._versions[aid].append(ver)
        # latest active becomes the resolvable agent
        if spec.get("status", "active") == "active":
            cur = self._agents.get(aid)
            if cur is None or _ver_key(ver) >= _ver_key(cur.get("version", "0.0.0")):
                self._agents[aid] = spec

    # -- integrity ------------------------------------------------------------
    def verify_integrity(self) -> None:
        """Compare base file hashes with registry.json. Raise on mismatch."""
        if not REGISTRY_PATH.exists():
            self.rebuild_registry_file()
            return
        reg = _load_json(REGISTRY_PATH)
        locked = {e["agent_id"]: e for e in reg.get("agents", []) if e.get("kind") == "base"}
        for p in sorted(BASE_AGENTS_DIR.glob("*.json")):
            spec = _load_json(p)
            aid = spec["agent_id"]
            actual = _sha256_file(p)
            entry = locked.get(aid)
            if entry is None:
                # new base agent not yet in registry -> record it
                continue
            if entry.get("sha256") and entry["sha256"] != actual:
                raise IntegrityError(
                    f"Hash base agent '{aid}' tidak cocok dengan registry.json. "
                    f"File base diubah manual. Sistem berhenti (PRD 9.8/T15)."
                )

    def rebuild_registry_file(self) -> None:
        """(Re)write registry.json index. Used at first startup."""
        entries = []
        for p in sorted(BASE_AGENTS_DIR.glob("*.json")):
            spec = _load_json(p)
            entries.append(self._registry_entry(spec, _sha256_file(p)))
        for p in sorted(DERIVED_AGENTS_DIR.glob("*.json")):
            spec = _load_json(p)
            entries.append(self._registry_entry(spec, _sha256_file(p)))
        self._write_registry(entries)

    def _registry_entry(self, spec: dict, sha: str) -> dict:
        aid = spec["agent_id"]
        return {
            "agent_id": aid,
            "versions": self._versions.get(aid, [spec.get("version", "1.0.0")]),
            "kind": spec.get("kind", "base"),
            "status": spec.get("status", "active"),
            "parents": [f"{p['agent_id']}@{p.get('version','1.0.0')}"
                        for p in (spec.get("lineage", {}) or {}).get("parents", [])],
            "persona_fingerprint": spec.get("persona_fingerprint"),
            "created_at": (spec.get("lineage", {}) or {}).get("created_at"),
            "use_count": spec.get("use_count", 0),
            "sha256": sha,
        }

    def _write_registry(self, entries: list[dict]) -> None:
        REGISTRY_PATH.write_text(
            json.dumps({"agents": entries}, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- queries --------------------------------------------------------------
    def get(self, agent_id: str) -> dict | None:
        return self._agents.get(agent_id)

    def get_version(self, agent_id: str, version: str) -> dict | None:
        return self._all_specs.get(f"{agent_id}@{version}")

    def exists(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def all_active(self) -> list[dict]:
        return [s for s in self._agents.values() if s.get("status", "active") == "active"]

    def base_agents(self) -> list[dict]:
        return [s for s in self.all_active() if s.get("kind") == "base"]

    def derived_agents(self) -> list[dict]:
        return [s for s in self.all_active() if s.get("kind") == "derived"]

    def versions_of(self, agent_id: str) -> list[str]:
        return self._versions.get(agent_id, [])

    def find_by_fingerprint(self, fp: str) -> dict | None:
        for s in self.derived_agents():
            if s.get("persona_fingerprint") == fp:
                return s
        return None

    # -- append-only registration (NO delete, NO overwrite) ------------------
    def register_derived(self, spec: dict) -> Path:
        aid = spec["agent_id"]
        ver = spec.get("version", "1.0.0")
        fname = f"{aid}__{ver}.json"
        path = DERIVED_AGENTS_DIR / fname
        if path.exists():
            raise IntegrityError(f"Agent turunan {fname} sudah ada; append-only menolak overwrite.")
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        self._register_in_memory(spec, path=path)
        self._append_registry_entry(spec, _sha256_file(path))
        return path

    def _append_registry_entry(self, spec: dict, sha: str) -> None:
        reg = _load_json(REGISTRY_PATH) if REGISTRY_PATH.exists() else {"agents": []}
        reg.setdefault("agents", [])
        reg["agents"] = [e for e in reg["agents"] if e["agent_id"] != spec["agent_id"]]
        reg["agents"].append(self._registry_entry(spec, sha))
        self._write_registry(reg["agents"])

    def bump_use_count(self, agent_id: str) -> None:
        if REGISTRY_PATH.exists():
            reg = _load_json(REGISTRY_PATH)
            for e in reg.get("agents", []):
                if e["agent_id"] == agent_id:
                    e["use_count"] = e.get("use_count", 0) + 1
            self._write_registry(reg["agents"])


def _ver_key(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)
