from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .command_runner import SandboxPolicy, run_command


@dataclass
class ValidationStageResult:
    stage: str
    command: str
    passed: bool
    attempts: int
    exit_code: int
    output: str
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class ValidationPipelineResult:
    overall_passed: bool
    stages: list[ValidationStageResult] = field(default_factory=list)


STAGED_CANDIDATES: dict[str, list[str]] = {
    "build": [
        "python -m compileall src",
        "mvn -q -DskipTests compile",
        "npm run build --if-present",
    ],
    "unit": [
        "pytest -q",
        "mvn -q test",
        "npm test -- --watch=false",
    ],
    "integration": [
        "pytest -m integration -q",
        "mvn -q -Dtest=*IT test",
    ],
    "static": [
        "python -m compileall src",
        "npm run lint --if-present",
    ],
}


def run_staged_validation(
    repo_path: Path,
    policy: SandboxPolicy,
    max_retries_per_stage: int = 1,
) -> ValidationPipelineResult:
    results: list[ValidationStageResult] = []
    stage_order = ["build", "unit", "integration", "static"]

    for stage_name in stage_order:
        command = _pick_available_command(STAGED_CANDIDATES.get(stage_name, []))
        if not command:
            results.append(
                ValidationStageResult(
                    stage=stage_name,
                    command="",
                    passed=True,
                    attempts=0,
                    exit_code=0,
                    output="",
                    skipped=True,
                    skip_reason="No available command for this stage in environment",
                )
            )
            continue

        attempts = 0
        final = None
        while attempts <= max_retries_per_stage:
            attempts += 1
            final = run_command(command=command, repo_path=repo_path, policy=policy)
            if final.exit_code == 0:
                break
            if not _should_retry(final.output, final.timed_out, attempts, max_retries_per_stage):
                break

        assert final is not None
        passed = final.exit_code == 0
        results.append(
            ValidationStageResult(
                stage=stage_name,
                command=command,
                passed=passed,
                attempts=attempts,
                exit_code=final.exit_code,
                output=final.output,
            )
        )

        if not passed:
            return ValidationPipelineResult(overall_passed=False, stages=results)

    return ValidationPipelineResult(overall_passed=True, stages=results)


def _pick_available_command(candidates: list[str]) -> str:
    for command in candidates:
        tool = command.strip().split()[0]
        if tool == "python":
            return command.replace("python", f'"{sys.executable}"', 1)
        if shutil.which(tool):
            return command
    return ""


def _should_retry(output: str, timed_out: bool, attempts: int, max_retries: int) -> bool:
    if attempts > max_retries:
        return False
    lowered = output.lower()
    transient_tokens = ["timeout", "timed out", "temporar", "connection reset", "econnreset", "503"]
    if timed_out:
        return True
    return any(token in lowered for token in transient_tokens)
