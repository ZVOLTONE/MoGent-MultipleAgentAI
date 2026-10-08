"""UTCP tool-response envelope (PRD 12.3) and result-status taxonomy (10.1).

All tool calls return a uniform ToolResponse. The ``result_status`` is the
single source of truth for the terminal check-mark: a green check (ok) is
shown ONLY when result_status == "ok".
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

# result_status taxonomy (PRD 10.1)
OK = "ok"
EMPTY = "empty"
ERROR = "error"
INVALID_SCHEMA = "invalid_schema"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_of(obj: Any) -> str:
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        raw = str(obj)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ToolResponse:
    tool: str
    args: dict
    result_status: str = ERROR
    http_status: int | None = None
    data: Any = None
    error: str | None = None
    fetched_at: str = field(default_factory=_now_iso)

    @property
    def is_ok(self) -> bool:
        return self.result_status == OK

    @property
    def payload_sha256(self) -> str:
        return sha256_of(self.data)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["payload_sha256"] = self.payload_sha256
        return d

    def status_glyph(self) -> str:
        """Terminal glyph with a short reason."""
        if self.result_status == OK:
            return "\u2713"  # check
        reason = {
            EMPTY: "empty",
            INVALID_SCHEMA: "schema",
            ERROR: f"HTTP {self.http_status}" if self.http_status else "error",
        }.get(self.result_status, self.result_status)
        return f"\u2717 ({reason})"  # cross


def ok(tool: str, args: dict, data: Any, http_status: int = 200) -> ToolResponse:
    return ToolResponse(tool=tool, args=args, result_status=OK, http_status=http_status, data=data)


def empty(tool: str, args: dict, http_status: int = 200, reason: str = "no rows") -> ToolResponse:
    return ToolResponse(tool=tool, args=args, result_status=EMPTY, http_status=http_status,
                        data=None, error=reason)


def error(tool: str, args: dict, http_status: int | None, reason: str) -> ToolResponse:
    return ToolResponse(tool=tool, args=args, result_status=ERROR, http_status=http_status,
                        data=None, error=reason)


def invalid_schema(tool: str, args: dict, reason: str, http_status: int = 200) -> ToolResponse:
    return ToolResponse(tool=tool, args=args, result_status=INVALID_SCHEMA, http_status=http_status,
                        data=None, error=reason)
