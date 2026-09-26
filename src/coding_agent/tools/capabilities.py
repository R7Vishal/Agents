from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .registry import ToolRegistry


@dataclass(frozen=True)
class CapabilitySection:
    name: str
    checks: list[dict[str, Any]]


class CapabilityManager:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_operations": self._section(
                [
                    ("Read files", "read_file"),
                    ("Create files", "create_file"),
                    ("Modify files", "edit_file"),
                    ("Delete files", "delete_file"),
                    ("Rename files", "rename_file"),
                    ("Search files", "search_files"),
                    ("Search text", "search_text"),
                    ("List directories", "list_directory"),
                ]
            ),
            "execution": self._section(
                [
                    ("Run commands", "execute_command"),
                    ("Run tests", "run_tests"),
                ]
            ),
            "git": self._section(
                [
                    ("Git status", "git_status"),
                    ("Git diff", "git_diff"),
                    ("Git log", "git_log"),
                    ("Branch list", "git_branch"),
                    ("Create branch", "git_create_branch"),
                    ("Checkout branch", "git_checkout"),
                    ("Git add", "git_add"),
                    ("Git commit", "git_commit"),
                ]
            ),
            "code_intelligence": self._section(
                [
                    ("Project structure", "project_structure"),
                    ("Workspace search", "search_text"),
                ]
            ),
        }

    def render_markdown(self) -> str:
        data = self.as_dict()
        lines: list[str] = ["CODING AGENT CAPABILITIES", ""]
        for section_name, rows in data.items():
            lines.append(section_name.replace("_", " ").title())
            for row in rows:
                mark = "✓" if row["available"] else "✗"
                lines.append(f"{mark} {row['name']}")
            lines.append("")
        return "\n".join(lines).strip()

    def _section(self, checks: list[tuple[str, str]]) -> list[dict[str, Any]]:
        return [
            {"name": label, "tool": tool, "available": self.registry.has(tool)}
            for label, tool in checks
        ]
