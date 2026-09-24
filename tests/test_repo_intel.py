from pathlib import Path

from coding_agent.repo_intel import discover_repository


def test_discover_repository_collects_basic_facts(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('x')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("TODO: fill\n", encoding="utf-8")

    facts = discover_repository(tmp_path)

    assert "src/main.py" in facts.entry_points
    assert "requirements.txt" in facts.package_manifests
    assert any("test_sample.py" in item for item in facts.test_files)
    assert "notes.md" in facts.todo_markers
