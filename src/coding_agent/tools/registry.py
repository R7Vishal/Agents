from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ToolExecutor = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, str]
    safety: str
    executor: ToolExecutor


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "parameters": definition.parameters,
                "safety": definition.safety,
            }
            for definition in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def has(self, name: str) -> bool:
        return name in self._tools

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        definition = self._tools.get(name)
        if not definition:
            return {
                "success": False,
                "operation": name,
                "error": f"Unknown tool: {name}",
            }
        try:
            result = definition.executor(arguments)
            if "operation" not in result:
                result["operation"] = name
            return result
        except Exception as exc:
            return {
                "success": False,
                "operation": name,
                "error": str(exc),
            }
