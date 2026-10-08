"""Evidence Store (PRD 10.1) - per request.

Every tool call that an agent performs is recorded here as an immutable
evidence record. Facts in the Fact Ledger must point to an evidence_id, and
the terminal check-mark is derived from the evidence result_status.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.utcp.envelope import ToolResponse, OK


@dataclass
class EvidenceRecord:
    evidence_id: str
    tool: str
    args: dict
    http_status: int | None
    result_status: str
    fetched_at: str
    payload_sha256: str
    payload: Any

    def to_public(self) -> dict:
        # payload omitted by default to keep debug output readable
        return {
            "evidence_id": self.evidence_id,
            "tool": self.tool,
            "args": self.args,
            "http_status": self.http_status,
            "result_status": self.result_status,
            "fetched_at": self.fetched_at,
            "payload_sha256": self.payload_sha256[:12],
        }


class EvidenceStore:
    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []
        self._counter = 0

    def add(self, resp: ToolResponse) -> EvidenceRecord:
        self._counter += 1
        rec = EvidenceRecord(
            evidence_id=f"ev_{self._counter:04d}",
            tool=resp.tool,
            args=resp.args,
            http_status=resp.http_status,
            result_status=resp.result_status,
            fetched_at=resp.fetched_at,
            payload_sha256=resp.payload_sha256,
            payload=resp.data,
        )
        self._records.append(rec)
        return rec

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        for r in self._records:
            if r.evidence_id == evidence_id:
                return r
        return None

    def all(self) -> list[EvidenceRecord]:
        return list(self._records)

    def ok_records(self) -> list[EvidenceRecord]:
        return [r for r in self._records if r.result_status == OK]

    def has_ok(self) -> bool:
        return any(r.result_status == OK for r in self._records)

    def ok_ids(self) -> list[str]:
        return [r.evidence_id for r in self.ok_records()]
