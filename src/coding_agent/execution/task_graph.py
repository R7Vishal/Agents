from __future__ import annotations

import json
from pathlib import Path

from ..models import FailureType, TaskGraph, TaskNode, TaskStatus


def load_task_graph(plan_file: Path) -> TaskGraph:
    data = json.loads(plan_file.read_text(encoding="utf-8"))
    tasks = []
    for item in data.get("tasks", []):
        tasks.append(
            TaskNode(
                task_id=item["task_id"],
                description=item.get("description", ""),
                rationale=item.get("rationale", ""),
                command=item["command"],
                validate_command=item.get("validate_command", ""),
                dependencies=item.get("dependencies", []),
                expected_result=item.get("expected_result", ""),
                validation_method=item.get("validation_method", ""),
                repair_commands=item.get("repair_commands", []),
            )
        )
    return TaskGraph(tasks=tasks)


def snapshot_task_graph(graph: TaskGraph) -> dict[str, dict[str, str | int]]:
    snapshot: dict[str, dict[str, str | int]] = {}
    for task in graph.tasks:
        snapshot[task.task_id] = {
            "status": task.status.value,
            "attempts": task.attempts,
            "repair_attempts": task.repair_attempts,
            "failure_type": task.failure_type.value if task.failure_type else "",
        }
    return snapshot


def apply_task_graph_checkpoint(graph: TaskGraph, checkpoint: dict[str, dict[str, str | int]]) -> None:
    for task in graph.tasks:
        if task.task_id not in checkpoint:
            continue
        item = checkpoint[task.task_id]
        status = str(item.get("status", "")).upper()
        if status == TaskStatus.COMPLETED.value:
            task.status = TaskStatus.COMPLETED
        else:
            task.status = TaskStatus.PENDING
        task.attempts = int(item.get("attempts", 0) or 0)
        task.repair_attempts = int(item.get("repair_attempts", 0) or 0)
        failure_value = str(item.get("failure_type", "")).strip()
        task.failure_type = FailureType(failure_value) if failure_value else None


def extract_checkpoint_data(checkpoint_payload: dict[str, object] | dict[str, dict[str, str | int]]) -> dict[str, dict[str, str | int]]:
    if "data" in checkpoint_payload and isinstance(checkpoint_payload.get("data"), dict):
        return checkpoint_payload["data"]  # type: ignore[return-value]
    return checkpoint_payload  # backward compatibility with old format


def validate_task_graph(graph: TaskGraph) -> None:
    task_ids = {task.task_id for task in graph.tasks}
    if len(task_ids) != len(graph.tasks):
        raise ValueError("Task graph contains duplicate task IDs")

    for task in graph.tasks:
        for dep in task.dependencies:
            if dep not in task_ids:
                raise ValueError(f"Task {task.task_id} depends on unknown task {dep}")


def get_ready_tasks(graph: TaskGraph) -> list[TaskNode]:
    completed_ids = {task.task_id for task in graph.tasks if task.status == TaskStatus.COMPLETED}
    failed_ids = {
        task.task_id
        for task in graph.tasks
        if task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED}
    }

    for task in graph.tasks:
        if task.status != TaskStatus.PENDING:
            continue
        if any(dep in failed_ids for dep in task.dependencies):
            task.status = TaskStatus.BLOCKED

    ready: list[TaskNode] = []
    for task in graph.tasks:
        if task.status != TaskStatus.PENDING:
            continue
        if all(dep in completed_ids for dep in task.dependencies):
            ready.append(task)
    return ready


def all_done(graph: TaskGraph) -> bool:
    return all(task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED} for task in graph.tasks)
