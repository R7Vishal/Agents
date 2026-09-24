import json
from pathlib import Path

from coding_agent.agent import CodingAgent


def test_agent_run_plan_generates_report(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    plan = {
        "tasks": [
            {
                "task_id": "T1",
                "description": "simple command",
                "rationale": "smoke",
                "command": "python -c \"print('ok')\"",
                "dependencies": [],
            }
        ]
    }

    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(workspace)

    report = agent.run_controlled_plan(
        repo_path=repo,
        requirement="execute plan",
        plan_file=plan_file,
        max_repair_attempts_per_task=1,
    )

    assert "## EXECUTION SUMMARY" in report
    assert "## TASK RESULTS" in report
    assert "## COMPLETION GATE" in report
