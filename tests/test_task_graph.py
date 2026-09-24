from pathlib import Path

from coding_agent.models import TaskGraph, TaskNode, TaskStatus
from coding_agent.task_graph import get_ready_tasks, validate_task_graph


def test_task_graph_detects_unknown_dependency() -> None:
    graph = TaskGraph(
        tasks=[
            TaskNode(
                task_id="T1",
                description="x",
                rationale="x",
                command="python -c \"print(1)\"",
                dependencies=["UNKNOWN"],
            )
        ]
    )

    try:
        validate_task_graph(graph)
    except ValueError as exc:
        assert "unknown task" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for unknown dependency")


def test_task_graph_marks_dependent_blocked() -> None:
    first = TaskNode(task_id="T1", description="x", rationale="x", command="x", status=TaskStatus.FAILED)
    second = TaskNode(
        task_id="T2",
        description="y",
        rationale="y",
        command="y",
        dependencies=["T1"],
    )
    graph = TaskGraph(tasks=[first, second])

    ready = get_ready_tasks(graph)

    assert ready == []
    assert second.status == TaskStatus.BLOCKED
