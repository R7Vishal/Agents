from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class RepairProposal:
    kind: str
    description: str
    target_files: list[str]
    commands: list[str]


def build_repair_proposals(repo_path: Path, failed_output: str, failed_command: str) -> list[RepairProposal]:
    proposals: list[RepairProposal] = []

    if "No module named" in failed_output:
        proposal = _proposal_missing_module(repo_path, failed_output)
        if proposal:
            proposals.append(proposal)

    lowered = failed_output.lower()
    if "failed" in lowered and "test" in lowered:
        proposals.append(
            RepairProposal(
                kind="validation_retry",
                description="Retry with targeted test validation before full suite.",
                target_files=[],
                commands=[failed_command],
            )
        )

    if "syntaxerror" in lowered or "indentationerror" in lowered:
        proposals.append(
            RepairProposal(
                kind="python_compile_check",
                description="Run Python compile check to isolate syntax failures quickly.",
                target_files=[],
                commands=["python -m compileall ."],
            )
        )

    return proposals


def apply_repair_proposal(repo_path: Path, proposal: RepairProposal) -> bool:
    if proposal.kind != "missing_module_init_patch":
        return False

    changed = False
    for rel_path in proposal.target_files:
        file_path = (repo_path / rel_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text("", encoding="utf-8")
            changed = True
    return changed


def _proposal_missing_module(repo_path: Path, failed_output: str) -> RepairProposal | None:
    match = re.search(r"No module named ['\"]([A-Za-z0-9_.]+)['\"]", failed_output)
    if not match:
        return None

    module_name = match.group(1)
    parts = module_name.split(".")
    if not parts:
        return None

    target_files: list[str] = []
    for depth in range(1, len(parts)):
        package_dir = repo_path / Path(*parts[:depth])
        if not package_dir.exists() or not package_dir.is_dir():
            continue
        init_file = package_dir / "__init__.py"
        if not init_file.exists():
            target_files.append(str(init_file.relative_to(repo_path)).replace("\\", "/"))

    if not target_files:
        return None

    return RepairProposal(
        kind="missing_module_init_patch",
        description="Add missing __init__.py files for discovered package paths.",
        target_files=target_files,
        commands=[],
    )
