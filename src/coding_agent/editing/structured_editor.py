from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..layers.contracts import ToolResult


class StructuredEditor:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.checkpoint_dir = workspace_root / ".agent_state" / "edit_checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def replace_text(self, file_path: Path, old_text: str, new_text: str) -> ToolResult:
        abs_path = self._resolve_path(file_path)
        try:
            original = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, output=f"Unable to read file: {exc}")

        if old_text not in original:
            return ToolResult(ok=False, output="Anchor text not found for replace_text")

        checkpoint_id = self._write_checkpoint(abs_path, original, operation="replace_text")
        updated = original.replace(old_text, new_text, 1)
        abs_path.write_text(updated, encoding="utf-8")
        return ToolResult(
            ok=True,
            output="replace_text applied",
            metadata={"checkpoint_id": checkpoint_id, "file_path": str(abs_path)},
        )

    def insert_after(self, file_path: Path, anchor: str, content: str) -> ToolResult:
        abs_path = self._resolve_path(file_path)
        try:
            original = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, output=f"Unable to read file: {exc}")

        idx = original.find(anchor)
        if idx < 0:
            return ToolResult(ok=False, output="Anchor text not found for insert_after")

        checkpoint_id = self._write_checkpoint(abs_path, original, operation="insert_after")
        insert_pos = idx + len(anchor)
        updated = original[:insert_pos] + content + original[insert_pos:]
        abs_path.write_text(updated, encoding="utf-8")
        return ToolResult(
            ok=True,
            output="insert_after applied",
            metadata={"checkpoint_id": checkpoint_id, "file_path": str(abs_path)},
        )

    def rollback(self, checkpoint_id: str) -> ToolResult:
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if not checkpoint_path.exists():
            return ToolResult(ok=False, output="Checkpoint not found")

        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        target_file = Path(payload.get("file_path", ""))
        if not target_file:
            return ToolResult(ok=False, output="Invalid checkpoint payload")

        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(str(payload.get("original_content", "")), encoding="utf-8")
        return ToolResult(ok=True, output="rollback applied", metadata={"file_path": str(target_file)})

    def _resolve_path(self, file_path: Path) -> Path:
        if file_path.is_absolute():
            return file_path
        return (self.workspace_root / file_path).resolve()

    def _write_checkpoint(self, file_path: Path, original_content: str, operation: str) -> str:
        checkpoint_id = str(uuid.uuid4())
        payload = {
            "id": checkpoint_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "file_path": str(file_path),
            "original_content": original_content,
        }
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return checkpoint_id
