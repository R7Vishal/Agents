from pathlib import Path

from coding_agent.execution.command_runner import SandboxPolicy
from coding_agent.execution.validation_pipeline import run_staged_validation


def test_validation_pipeline_runs_available_stages(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    result = run_staged_validation(
        repo_path=repo,
        policy=SandboxPolicy(profile="local"),
        max_retries_per_stage=0,
    )

    assert result.stages
    assert all(stage.stage for stage in result.stages)
