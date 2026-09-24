from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .lifecycle import assert_transition
from .models import AgentRunRecord, LifecycleState


class StateStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, run_id: str) -> Path:
        return self.state_dir / f"{run_id}.json"

    def save(self, record: AgentRunRecord) -> None:
        record.updated_at = datetime.now(timezone.utc).isoformat()
        path = self._path_for(record.run_id)
        path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")

    def load(self, run_id: str) -> AgentRunRecord:
        path = self._path_for(run_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return AgentRunRecord(
            run_id=data["run_id"],
            requirement=data["requirement"],
            state=LifecycleState(data["state"]),
            repo_path=data["repo_path"],
            notes=data.get("notes", {}),
            updated_at=data.get("updated_at", ""),
        )

    def transition(self, record: AgentRunRecord, target: LifecycleState) -> None:
        assert_transition(record.state, target)
        record.state = target
        self.save(record)

    def latest_run(self) -> AgentRunRecord | None:
        files = sorted(self.state_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        run_id = files[0].stem
        return self.load(run_id)
