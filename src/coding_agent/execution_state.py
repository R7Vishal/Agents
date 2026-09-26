from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class AgentExecutionState:
    conversation_id: str
    workspace: str
    task: str
    plan: list[str] = field(default_factory=list)
    current_step: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tests_run: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "running"
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "workspace": self.workspace,
            "task": self.task,
            "plan": self.plan,
            "current_step": self.current_step,
            "tool_calls": self.tool_calls,
            "files_changed": self.files_changed,
            "tests_run": self.tests_run,
            "errors": self.errors,
            "status": self.status,
            "updated_at": self.updated_at,
        }


class ExecutionStateStore:
    def __init__(self) -> None:
        self._states: dict[str, AgentExecutionState] = {}

    def start(self, task: str, workspace: str, conversation_id: str | None = None) -> AgentExecutionState:
        cid = conversation_id or str(uuid.uuid4())
        state = AgentExecutionState(
            conversation_id=cid,
            workspace=workspace,
            task=task,
            updated_at=self._now(),
        )
        self._states[cid] = state
        return state

    def get(self, conversation_id: str) -> AgentExecutionState | None:
        return self._states.get(conversation_id)

    def update(self, conversation_id: str, **changes: Any) -> AgentExecutionState | None:
        state = self._states.get(conversation_id)
        if not state:
            return None
        for key, value in changes.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.updated_at = self._now()
        return state

    def finish(self, conversation_id: str, status: str = "completed") -> AgentExecutionState | None:
        state = self._states.get(conversation_id)
        if not state:
            return None
        state.status = status
        state.updated_at = self._now()
        return state

    def _now(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
