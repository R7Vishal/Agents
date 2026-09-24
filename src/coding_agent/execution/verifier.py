from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..governance.safety import validate_command
from ..models import BaselineCheckResult


CANDIDATE_CHECKS = [
    ("python-tests", "pytest -q"),
    ("python-lint", "python -m compileall src"),
    ("node-tests", "npm test -- --watch=false"),
    ("maven-tests", "mvn test -q"),
]


def _tool_exists(command: str) -> bool:
    exe = command.strip().split()[0]
    return shutil.which(exe) is not None


def run_baseline_checks(repo_path: Path, execute: bool) -> list[BaselineCheckResult]:
    results: list[BaselineCheckResult] = []

    for name, command in CANDIDATE_CHECKS:
        available = _tool_exists(command)
        executed = False
        passed = None
        exit_code = None
        output = ""

        if available and execute:
            validate_command(command)
            executed = True
            proc = subprocess.run(
                command,
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            exit_code = proc.returncode
            passed = proc.returncode == 0
            output = (proc.stdout + "\n" + proc.stderr).strip()[:4000]

        results.append(
            BaselineCheckResult(
                name=name,
                command=command,
                available=available,
                executed=executed,
                passed=passed,
                exit_code=exit_code,
                output=output,
            )
        )

    return results
