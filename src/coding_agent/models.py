from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    REPAIRING = "REPAIRING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class FailureType(str, Enum):
    SYNTAX_ERROR = "SYNTAX_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass
class BaselineCheckResult:
    name: str
    command: str
    available: bool
    executed: bool
    passed: bool | None
    exit_code: int | None
    output: str = ""


@dataclass
class RepositoryFacts:
    repo_path: str
    entry_points: list[str] = field(default_factory=list)
    package_manifests: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    docker_files: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    planner_files: list[str] = field(default_factory=list)
    lifecycle_files: list[str] = field(default_factory=list)
    safety_files: list[str] = field(default_factory=list)
    persistence_files: list[str] = field(default_factory=list)
    todo_markers: list[str] = field(default_factory=list)


@dataclass
class MilestoneRecommendation:
    title: str
    reason: str
    acceptance_criteria: list[str]
    likely_files: list[str]


@dataclass
class FirstRunAssessment:
    current_state: list[str]
    architecture_map: list[str]
    working_capabilities: list[str]
    incomplete_capabilities: list[str]
    risks: list[str]
    test_baseline: list[str]
    recommended_milestone: MilestoneRecommendation


@dataclass
class AgentRunRecord:
    run_id: str
    requirement: str
    state: LifecycleState
    repo_path: str
    notes: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""


@dataclass
class TaskNode:
    task_id: str
    description: str
    rationale: str
    command: str
    validate_command: str = ""
    dependencies: list[str] = field(default_factory=list)
    expected_result: str = ""
    validation_method: str = ""
    repair_commands: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    repair_attempts: int = 0
    failure_type: FailureType | None = None
    last_error: str = ""


@dataclass
class TaskGraph:
    tasks: list[TaskNode]


@dataclass
class CommandRunResult:
    command: str
    exit_code: int
    output: str
    timed_out: bool = False


@dataclass
class TaskExecutionResult:
    task_id: str
    status: TaskStatus
    attempts: int
    repair_attempts: int
    failure_type: FailureType | None = None
    message: str = ""
    duration_ms: int | None = None
