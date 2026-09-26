from __future__ import annotations

from pathlib import Path
from typing import Any

from .capabilities import CapabilityManager
from .registry import ToolRegistry


class AgentDoctor:
    def __init__(self, registry: ToolRegistry, capability_manager: CapabilityManager, workspace_root: Path) -> None:
        self.registry = registry
        self.capability_manager = capability_manager
        self.workspace_root = workspace_root

    def report(self) -> dict[str, Any]:
        tools = self.registry.list_tools()
        capability_map = self.capability_manager.as_dict()

        checks = {
            "LLM Integration": self._check_any_tool(["project_structure"]),
            "Chat Interface": True,
            "File Read": self._check_any_tool(["read_file"]),
            "File Write": self._check_any_tool(["write_file", "create_file"]),
            "File Edit": self._check_any_tool(["edit_file"]),
            "Workspace Search": self._check_any_tool(["search_files", "search_text"]),
            "Command Execution": self._check_any_tool(["execute_command"]),
            "Testing": self._check_any_tool(["run_tests"]),
            "Git": self._check_any_tool(["git_status", "git_diff"]),
            "Planning": True,
            "Error Recovery": self._check_any_tool(["execute_command", "run_tests"]),
            "Project Memory": (self.workspace_root / ".agent_state").exists(),
            "Deployment": False,
        }

        improvements = [
            "Add repository indexing for faster semantic search.",
            "Add persistent long-term project memory with embeddings.",
            "Integrate real LLM providers with policy-based model routing.",
            "Add deployment pipeline integrations with approval gates.",
        ]

        return {
            "health": checks,
            "tool_count": len(tools),
            "capabilities": capability_map,
            "recommended_improvements": improvements,
        }

    def render_markdown(self) -> str:
        report = self.report()
        lines = ["CODING AGENT HEALTH", ""]
        for key, ok in report["health"].items():
            mark = "✓" if ok else "✗"
            if key == "Project Memory" and ok:
                mark = "⚠"
            lines.append(f"{key:<20} {mark}")

        lines.extend(["", "Recommended Improvements", ""])
        for index, item in enumerate(report["recommended_improvements"], start=1):
            lines.append(f"{index}. {item}")
        return "\n".join(lines)

    def _check_any_tool(self, names: list[str]) -> bool:
        return any(self.registry.has(name) for name in names)
