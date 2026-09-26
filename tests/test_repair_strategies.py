from pathlib import Path

from coding_agent.execution.repair_strategies import apply_repair_proposal, build_repair_proposals


def test_missing_module_repair_proposal_creates_init_files(tmp_path: Path) -> None:
    package_dir = tmp_path / "myapp" / "services"
    package_dir.mkdir(parents=True)
    (package_dir / "worker.py").write_text("x = 1\n", encoding="utf-8")

    output = "ModuleNotFoundError: No module named 'myapp.services.worker'"
    proposals = build_repair_proposals(tmp_path, output, "python -m pytest -q")
    assert proposals

    patch_proposals = [item for item in proposals if item.kind == "missing_module_init_patch"]
    assert patch_proposals

    changed = apply_repair_proposal(tmp_path, patch_proposals[0])
    assert changed is True
    assert (tmp_path / "myapp" / "__init__.py").exists()
    assert (tmp_path / "myapp" / "services" / "__init__.py").exists()
