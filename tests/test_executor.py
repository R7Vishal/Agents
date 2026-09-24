from pathlib import Path

from coding_agent.executor import execute_task_graph
from coding_agent.models import FailureType, TaskGraph, TaskNode, TaskStatus


def test_executor_blocks_downstream_on_failure(tmp_path: Path) -> None:
    graph = TaskGraph(
        tasks=[
            TaskNode(
                task_id="T1",
                description="always fail",
                rationale="test",
                command='python -c "import sys; sys.exit(1)"',
            ),
            TaskNode(
                task_id="T2",
                description="depends on T1",
                rationale="test",
                command='python -c "print(2)"',
                dependencies=["T1"],
            ),
        ]
    )

    results = execute_task_graph(graph=graph, repo_path=tmp_path, max_repair_attempts_per_task=1)

    by_task = {item.task_id: item for item in results}
    assert by_task["T1"].status == TaskStatus.FAILED
    assert by_task["T2"].status == TaskStatus.BLOCKED


def test_executor_repair_succeeds_within_budget(tmp_path: Path) -> None:
    command = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'ok.flag\').exists() else 1)"'
    repair = 'python -c "import pathlib; pathlib.Path(\'ok.flag\').write_text(\'ok\')"'

    graph = TaskGraph(
        tasks=[
            TaskNode(
                task_id="T1",
                description="create flag via repair",
                rationale="test",
                command=command,
                repair_commands=[repair],
            )
        ]
    )

    results = execute_task_graph(graph=graph, repo_path=tmp_path, max_repair_attempts_per_task=1)

    assert results[0].status == TaskStatus.COMPLETED
    assert results[0].repair_attempts == 1


def test_executor_respects_repair_budget(tmp_path: Path) -> None:
    graph = TaskGraph(
        tasks=[
            TaskNode(
                task_id="T1",
                description="fail with no repair",
                rationale="test",
                command='python -c "import sys; sys.exit(1)"',
            )
        ]
    )

    results = execute_task_graph(graph=graph, repo_path=tmp_path, max_repair_attempts_per_task=0)

    assert results[0].status == TaskStatus.FAILED
    assert results[0].failure_type in {FailureType.UNKNOWN, FailureType.RUNTIME_ERROR, FailureType.TEST_FAILURE}
