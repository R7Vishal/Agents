from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class PlanStep:
    step_id: str
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class SearchHit:
    file_path: str
    snippet: str
    score: float = 0.0
    symbol: str = ""


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    ok: bool
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    command: str
    exit_code: int
    output: str
    timed_out: bool = False


class UserInterfacePort(Protocol):
    def send_user_message(self, message: str) -> None: ...

    def send_agent_message(self, message: str) -> None: ...


class AgentOrchestratorPort(Protocol):
    def run(self, requirement: str, repo_path: Path) -> str: ...


class ReasoningEnginePort(Protocol):
    def generate(self, prompt: str, context: str = "") -> str: ...

    def generate_structured_output(self, prompt: str, schema_name: str) -> dict[str, Any]: ...


class RepositoryUnderstandingPort(Protocol):
    def discover(self, repo_path: Path) -> dict[str, Any]: ...


class CodeSearchPort(Protocol):
    def file_search(self, query: str) -> list[SearchHit]: ...

    def symbol_search(self, symbol: str) -> list[SearchHit]: ...

    def semantic_search(self, query: str) -> list[SearchHit]: ...

    def dependency_search(self, symbol: str) -> list[SearchHit]: ...

    def call_graph(self, symbol: str) -> list[SearchHit]: ...


class PlanningEnginePort(Protocol):
    def create_plan(self, requirement: str, repo_facts: dict[str, Any]) -> list[PlanStep]: ...


class ToolCallingPort(Protocol):
    def execute(self, call: ToolCall) -> ToolResult: ...


class CodeEditingEnginePort(Protocol):
    def replace_text(self, file_path: Path, old_text: str, new_text: str) -> ToolResult: ...

    def insert_after(self, file_path: Path, anchor: str, content: str) -> ToolResult: ...

    def rollback(self, checkpoint_id: str) -> ToolResult: ...


class SandboxExecutionPort(Protocol):
    def run_command(self, command: str, repo_path: Path) -> ExecutionResult: ...


class TestValidationEnginePort(Protocol):
    def run_build(self, repo_path: Path) -> ExecutionResult: ...

    def run_tests(self, repo_path: Path) -> ExecutionResult: ...

    def run_static_checks(self, repo_path: Path) -> ExecutionResult: ...


class MemoryContextPort(Protocol):
    def load_short_term(self, run_id: str) -> dict[str, Any]: ...

    def save_short_term(self, run_id: str, payload: dict[str, Any]) -> None: ...

    def load_project_memory(self, repo_path: Path) -> dict[str, Any]: ...


class SecurityGovernancePort(Protocol):
    def authorize_action(self, action: str) -> bool: ...

    def validate_command(self, command: str) -> None: ...

    def redact_sensitive(self, text: str) -> str: ...


class ObservabilityPort(Protocol):
    def emit(self, event: str, **payload: Any) -> None: ...
