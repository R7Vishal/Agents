from pathlib import Path

from coding_agent.command_runner import run_command


def test_command_runner_uses_current_python(tmp_path: Path) -> None:
    result = run_command("python -c \"print('ok')\"", repo_path=tmp_path)
    assert result.exit_code == 0
    assert "ok" in result.output
