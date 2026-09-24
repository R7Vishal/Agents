import json
from pathlib import Path

from coding_agent.agent import CodingAgent


def _make_two_task_plan(plan_file: Path) -> None:
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
    plan_file.write_text(json.dumps(plan), encoding="utf-8")


def test_resume_dry_run_preview_lists_retry_queue(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_file = tmp_path / "plan.json"
    _make_two_task_plan(plan_file)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(workspace)

    _ = agent.run_controlled_plan(
        repo_path=repo,
        requirement="execute plan",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
    )
    latest = agent.state_store.latest_run()
    assert latest is not None

    preview = agent.run_controlled_plan(
        repo_path=repo,
        requirement="preview",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
        resume_run_id=latest.run_id,
        resume_dry_run=True,
    )

    assert "## RESUME DRY RUN PREVIEW" in preview
    assert "T1" in preview
    assert "T2" in preview
    assert "## RETRY QUEUE" in preview
    assert "risk=" in preview
    assert "Reason:" in preview


def test_checkpoint_tamper_is_detected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_file = tmp_path / "plan.json"
    _make_two_task_plan(plan_file)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(workspace)

    _ = agent.run_controlled_plan(
        repo_path=repo,
        requirement="execute plan",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
    )
    latest = agent.state_store.latest_run()
    assert latest is not None

    state_file = workspace / ".agent_state" / f"{latest.run_id}.json"
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    state_data["notes"]["checkpoint"]["data"]["T1"]["status"] = "PENDING"
    state_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")

    forensic_report = agent.run_controlled_plan(
        repo_path=repo,
        requirement="resume",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
        resume_run_id=latest.run_id,
    )
    assert "## CHECKPOINT INTEGRITY FORENSICS" in forensic_report
    assert "Integrity status: FAILED" in forensic_report
    assert "Signature version:" in forensic_report
    assert "Envelope key ID:" in forensic_report
    assert "Resolved key ID:" in forensic_report
    assert "Expected signature:" in forensic_report
    assert "Actual signature:" in forensic_report


def test_duration_metrics_present_in_report_and_logs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    plan = {
        "tasks": [
            {
                "task_id": "T1",
                "description": "quick task",
                "rationale": "duration",
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
        requirement="duration",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
    )
    assert "Duration:" in report

    latest = agent.state_store.latest_run()
    assert latest is not None
    log_file = workspace / ".agent_logs" / f"{latest.run_id}.jsonl"
    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    completed_events = [item for item in lines if item.get("event") == "task_event" and item.get("type") == "task_completed"]
    assert completed_events
    assert isinstance(completed_events[0].get("duration_ms"), int)


def test_resume_max_risk_blocks_execution(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_file = tmp_path / "plan.json"
    _make_two_task_plan(plan_file)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = CodingAgent(workspace)

    _ = agent.run_controlled_plan(
        repo_path=repo,
        requirement="execute plan",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
    )
    latest = agent.state_store.latest_run()
    assert latest is not None

    policy_block = agent.run_controlled_plan(
        repo_path=repo,
        requirement="resume",
        plan_file=plan_file,
        max_repair_attempts_per_task=0,
        resume_run_id=latest.run_id,
        resume_max_risk=3,
    )

    assert "## RESUME POLICY BLOCK" in policy_block
    assert "Blocked retry tasks:" in policy_block
    assert "Recommendation:" in policy_block
