from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from ..models import FailureType, TaskExecutionResult, TaskGraph, TaskStatus
from .command_runner import SandboxPolicy, run_command
from .repair import classify_failure
from .repair_strategies import apply_repair_proposal, build_repair_proposals
from .task_graph import all_done, get_ready_tasks


def execute_task_graph(
    graph: TaskGraph,
    repo_path: Path,
    max_repair_attempts_per_task: int,
    sandbox_policy: SandboxPolicy | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> list[TaskExecutionResult]:
    results: list[TaskExecutionResult] = []
    recorded_terminal_tasks: set[str] = set()
    task_started_times: dict[str, float] = {}

    while not all_done(graph):
        ready = get_ready_tasks(graph)

        for task in graph.tasks:
            if task.status == TaskStatus.BLOCKED and task.task_id not in recorded_terminal_tasks:
                results.append(
                    TaskExecutionResult(
                        task_id=task.task_id,
                        status=TaskStatus.BLOCKED,
                        attempts=task.attempts,
                        repair_attempts=task.repair_attempts,
                        message="Task blocked by failed dependency",
                    )
                )
                recorded_terminal_tasks.add(task.task_id)
                if on_event:
                    on_event({"type": "task_blocked", "task_id": task.task_id, "message": "dependency failed"})

        if not ready:
            for task in graph.tasks:
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.BLOCKED
                    results.append(
                        TaskExecutionResult(
                            task_id=task.task_id,
                            status=TaskStatus.BLOCKED,
                            attempts=task.attempts,
                            repair_attempts=task.repair_attempts,
                            message="No executable path remaining due to failed dependencies",
                        )
                    )
                    recorded_terminal_tasks.add(task.task_id)
                    if on_event:
                        on_event({"type": "task_blocked", "task_id": task.task_id, "message": "no executable path"})
            break

        for task in ready:
            task.status = TaskStatus.RUNNING
            task.attempts += 1
            task_started_times[task.task_id] = time.perf_counter()
            if on_event:
                on_event({"type": "task_started", "task_id": task.task_id, "attempt": task.attempts})

            run_result = run_command(task.command, repo_path=repo_path, policy=sandbox_policy)
            if run_result.exit_code != 0:
                final_failure = _attempt_repair(
                    task=task,
                    repo_path=repo_path,
                    max_repair_attempts_per_task=max_repair_attempts_per_task,
                    sandbox_policy=sandbox_policy,
                    failed_command=task.command,
                    failed_output=run_result.output,
                    timed_out=run_result.timed_out,
                )
                if final_failure:
                    task.status = TaskStatus.FAILED
                    task.failure_type = final_failure
                    task.last_error = run_result.output
                    duration_ms = int((time.perf_counter() - task_started_times.get(task.task_id, time.perf_counter())) * 1000)
                    results.append(
                        TaskExecutionResult(
                            task_id=task.task_id,
                            status=task.status,
                            attempts=task.attempts,
                            repair_attempts=task.repair_attempts,
                            failure_type=final_failure,
                            message="Task command failed after repair budget",
                            duration_ms=duration_ms,
                        )
                    )
                    recorded_terminal_tasks.add(task.task_id)
                    if on_event:
                        on_event(
                            {
                                "type": "task_failed",
                                "task_id": task.task_id,
                                "failure_type": final_failure.value,
                                "message": "task command failed after repair budget",
                                "duration_ms": duration_ms,
                            }
                        )
                    continue

            if task.validate_command:
                validate_result = run_command(task.validate_command, repo_path=repo_path, policy=sandbox_policy)
                if validate_result.exit_code != 0:
                    final_failure = _attempt_repair(
                        task=task,
                        repo_path=repo_path,
                        max_repair_attempts_per_task=max_repair_attempts_per_task,
                        sandbox_policy=sandbox_policy,
                        failed_command=task.validate_command,
                        failed_output=validate_result.output,
                        timed_out=validate_result.timed_out,
                    )
                    if final_failure:
                        task.status = TaskStatus.FAILED
                        task.failure_type = final_failure
                        task.last_error = validate_result.output
                        duration_ms = int((time.perf_counter() - task_started_times.get(task.task_id, time.perf_counter())) * 1000)
                        results.append(
                            TaskExecutionResult(
                                task_id=task.task_id,
                                status=task.status,
                                attempts=task.attempts,
                                repair_attempts=task.repair_attempts,
                                failure_type=final_failure,
                                message="Validation failed after repair budget",
                                duration_ms=duration_ms,
                            )
                        )
                        recorded_terminal_tasks.add(task.task_id)
                        if on_event:
                            on_event(
                                {
                                    "type": "task_failed",
                                    "task_id": task.task_id,
                                    "failure_type": final_failure.value,
                                    "message": "validation failed after repair budget",
                                    "duration_ms": duration_ms,
                                }
                            )
                        continue

            task.status = TaskStatus.COMPLETED
            task.failure_type = None
            duration_ms = int((time.perf_counter() - task_started_times.get(task.task_id, time.perf_counter())) * 1000)
            results.append(
                TaskExecutionResult(
                    task_id=task.task_id,
                    status=task.status,
                    attempts=task.attempts,
                    repair_attempts=task.repair_attempts,
                    message="Task completed",
                    duration_ms=duration_ms,
                )
            )
            recorded_terminal_tasks.add(task.task_id)
            if on_event:
                on_event({"type": "task_completed", "task_id": task.task_id, "duration_ms": duration_ms})

    return results


def _attempt_repair(
    task,
    repo_path: Path,
    max_repair_attempts_per_task: int,
    sandbox_policy: SandboxPolicy | None,
    failed_command: str,
    failed_output: str,
    timed_out: bool,
) -> FailureType | None:
    failure_type = classify_failure(failed_output, timed_out=timed_out, command=failed_command)

    proposals = build_repair_proposals(repo_path=repo_path, failed_output=failed_output, failed_command=failed_command)
    for proposal in proposals:
        if apply_repair_proposal(repo_path=repo_path, proposal=proposal):
            retry_result = run_command(task.command, repo_path=repo_path, policy=sandbox_policy)
            if retry_result.exit_code == 0:
                return None
            failure_type = classify_failure(
                retry_result.output,
                timed_out=retry_result.timed_out,
                command=task.command,
            )

        for proposal_command in proposal.commands:
            proposal_result = run_command(proposal_command, repo_path=repo_path, policy=sandbox_policy)
            if proposal_result.exit_code != 0:
                continue
            retry_result = run_command(task.command, repo_path=repo_path, policy=sandbox_policy)
            if retry_result.exit_code == 0:
                return None
            failure_type = classify_failure(
                retry_result.output,
                timed_out=retry_result.timed_out,
                command=task.command,
            )

    while task.repair_attempts < max_repair_attempts_per_task:
        if not task.repair_commands:
            break

        repair_command = task.repair_commands[min(task.repair_attempts, len(task.repair_commands) - 1)]
        task.repair_attempts += 1
        repair_result = run_command(repair_command, repo_path=repo_path, policy=sandbox_policy)
        if repair_result.exit_code != 0:
            failure_type = classify_failure(
                repair_result.output,
                timed_out=repair_result.timed_out,
                command=repair_command,
            )
            continue

        retry_result = run_command(task.command, repo_path=repo_path, policy=sandbox_policy)
        if retry_result.exit_code == 0:
            return None

        failure_type = classify_failure(
            retry_result.output,
            timed_out=retry_result.timed_out,
            command=task.command,
        )

    return failure_type
