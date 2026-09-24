import json
from pathlib import Path

from coding_agent.agent import CodingAgent
from coding_agent.models import LifecycleState


def test_run_plan_resume_from_checkpoint(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    plan = {
        "tasks": [
            {
                "task_id": "T1",
                "description": "complete first task",
                "rationale": "checkpoint",
                "command": "python -c \"print('done1')\"",
                "dependencies": [],
            },
            {
                "task_id": "T2",
                "description": "fails until flag exists",
                "rationale": "resume",
                "command": "python -c \"import pathlib,sys; sys.exit(0 if pathlib.Path('resume.flag').exists() else 1)\"",
                "dependencies": ["T1"],
            },
        ]
    }

    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(workspace)

    report_1 = agent.run_controlled_plan(
        repo_path=repo,
        requirement="execute plan",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
    )
    assert "Status: BLOCKED" in report_1

    latest = agent.state_store.latest_run()
    assert latest is not None
    run_id = latest.run_id
    assert latest.state == LifecycleState.BLOCKED

    (repo / "resume.flag").write_text("ok", encoding="utf-8")

    report_2 = agent.run_controlled_plan(
        repo_path=repo,
        requirement="resume",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
        resume_run_id=run_id,
    )
    assert "Status: PASS" in report_2

    resumed = agent.state_store.load(run_id)
    assert resumed.state == LifecycleState.COMPLETED

    log_file = workspace / ".agent_logs" / f"{run_id}.jsonl"
    assert log_file.exists()
