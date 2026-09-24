from pathlib import Path

from coding_agent.agent import CodingAgent


def test_first_run_returns_required_sections(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    agent = CodingAgent(workspace)
    report = agent.first_run_assessment(repo_path=repo, requirement="analyze", run_baseline=False)

    assert "## CURRENT STATE" in report
    assert "## ARCHITECTURE MAP" in report
    assert "## WORKING CAPABILITIES" in report
    assert "## INCOMPLETE CAPABILITIES" in report
    assert "## RISKS / TECHNICAL DEBT" in report
    assert "## TEST BASELINE" in report
    assert "## RECOMMENDED NEXT MILESTONE" in report
    assert "## FILES LIKELY TO CHANGE" in report
    assert "## ACCEPTANCE CRITERIA" in report
