"""A2A protocol (PRD 15).

Structured messages for Orchestrator <-> agent and agent <-> specialist.
Rules enforced here:
  * max call depth (default 3) to prevent loops
  * an agent must not be called twice with an identical task in one trace
  * every message is recorded so --debug can show the raw messages
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from config import config


def _ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class A2AMessage:
    trace_id: str
    message_id: str
    sender: str
    receiver: str
    task: str
    context: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_ts)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class A2AResponse:
    trace_id: str
    sender: str
    receiver: str
    status: str  # success | partial | no_data | error
    result: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_ts)

    def to_dict(self) -> dict:
        return asdict(self)


class A2ABus:
    """Records messages, enforces depth & dedup within a trace."""

    def __init__(self, trace_id: str, max_depth: int | None = None):
        self.trace_id = trace_id
        self.max_depth = max_depth if max_depth is not None else config.MAX_A2A_DEPTH
        self.messages: list[A2AMessage] = []
        self.responses: list[A2AResponse] = []
        self._task_signatures: set[tuple[str, str]] = set()
        self._counter = 0
        self.depth = 0

    def can_call(self, receiver: str, task: str) -> tuple[bool, str]:
        if self.depth >= self.max_depth:
            return False, f"kedalaman A2A maksimum ({self.max_depth}) tercapai"
        sig = (receiver, task.strip().lower())
        if sig in self._task_signatures:
            return False, f"task identik untuk {receiver} sudah dijalankan di trace ini"
        return True, ""

    def send(self, sender: str, receiver: str, task: str, context: dict) -> A2AMessage:
        self._counter += 1
        msg = A2AMessage(
            trace_id=self.trace_id,
            message_id=f"m_{self._counter:03d}",
            sender=sender, receiver=receiver, task=task, context=context,
        )
        self.messages.append(msg)
        self._task_signatures.add((receiver, task.strip().lower()))
        return msg

    def receive(self, msg: A2AMessage, status: str, result: dict) -> A2AResponse:
        resp = A2AResponse(
            trace_id=self.trace_id, sender=msg.receiver, receiver=msg.sender,
            status=status, result=result,
        )
        self.responses.append(resp)
        return resp

    def enter(self):
        self.depth += 1

    def leave(self):
        self.depth = max(0, self.depth - 1)

    def debug_dump(self) -> list[dict]:
        out = []
        for m in self.messages:
            out.append({"type": "message", **m.to_dict()})
        for r in self.responses:
            out.append({"type": "response", **r.to_dict()})
        return out
