from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..governance.approval import ApprovalPolicy, enforce_approval
from ..governance.safety import validate_command
from ..models import CommandRunResult


@dataclass(frozen=True)
class SandboxPolicy:
    profile: str = "local"
    require_allowlist: bool = True
    allowed_prefixes: set[str] = field(default_factory=set)
    scoped_write_paths: list[Path] = field(default_factory=list)
    approval_policy: ApprovalPolicy | None = None


def run_command(
    command: str,
    repo_path: Path,
    timeout_seconds: int = 600,
    policy: SandboxPolicy | None = None,
) -> CommandRunResult:
    effective_command = _normalize_command(command)
    active_policy = policy or SandboxPolicy()
    validate_command(
        effective_command,
        require_allowlist=active_policy.require_allowlist,
        allowed_prefixes=active_policy.allowed_prefixes or None,
        repo_path=repo_path,
        scoped_write_paths=active_policy.scoped_write_paths or None,
    )

    if active_policy.approval_policy:
        enforce_approval(effective_command, active_policy.approval_policy)

    command_to_run = effective_command
    if active_policy.profile == "container":
        command_to_run = _build_container_command(effective_command, repo_path)

    try:
        proc = subprocess.run(
            command_to_run,
            cwd=repo_path,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()[:8000]
        return CommandRunResult(command=command, exit_code=proc.returncode, output=output)
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()[:8000]
        return CommandRunResult(command=command, exit_code=124, output=output, timed_out=True)


def _normalize_command(command: str) -> str:
    stripped = command.strip()
    lowered = stripped.lower()
    if lowered.startswith("python "):
        remainder = stripped.split(" ", 1)[1]
        return f'"{sys.executable}" {remainder}'
    return command


def _build_container_command(command: str, repo_path: Path) -> str:
    safe_repo = str(repo_path).replace('"', "")
    return (
        "docker run --rm "
        f"-v \"{safe_repo}\":/workspace "
        "-w /workspace python:3.12 "
        f"sh -lc \"{command.replace('"', '\\\"')}\""
    )
