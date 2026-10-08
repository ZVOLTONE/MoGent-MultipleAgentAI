"""Per-request tool cache (PRD 12.4).

Key = (tool, normalized args). The same (tool, args) call within a single
user request is executed only once. This directly fixes the UAT finding of
17 duplicate tool calls and backs test T21.

The cache is explicitly request-scoped: a new RequestCache is created per
orchestrator request so results never leak across turns (memory hygiene,
PRD 13).
"""
from __future__ import annotations

import json
from typing import Callable

from .envelope import ToolResponse


def _key(tool: str, args: dict) -> str:
    norm = {k: v for k, v in sorted(args.items()) if v is not None}
    return tool + "|" + json.dumps(norm, sort_keys=True, ensure_ascii=False, default=str)


class RequestCache:
    def __init__(self) -> None:
        self._store: dict[str, ToolResponse] = {}
        self._order: list[str] = []
        self.hits = 0
        self.misses = 0

    def get_or_call(self, tool: str, args: dict, fn: Callable[[], ToolResponse]) -> ToolResponse:
        k = _key(tool, args)
        if k in self._store:
            self.hits += 1
            return self._store[k]
        self.misses += 1
        resp = fn()
        self._store[k] = resp
        self._order.append(k)
        return resp

    def all_calls(self) -> list[ToolResponse]:
        return [self._store[k] for k in self._order]

    def call_signatures(self) -> list[str]:
        return list(self._order)

    def has_duplicates(self) -> bool:
        return len(self._order) != len(set(self._order))

    def stats(self) -> dict:
        return {"unique_calls": len(self._order), "hits": self.hits, "misses": self.misses}
