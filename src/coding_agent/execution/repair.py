from __future__ import annotations

from ..models import FailureType


def classify_failure(output: str, timed_out: bool, command: str) -> FailureType:
    normalized = output.lower()
    command_lower = command.lower()

    if timed_out:
        return FailureType.TIMEOUT
    if "syntaxerror" in normalized:
        return FailureType.SYNTAX_ERROR
    if "modulenotfounderror" in normalized or "cannot import" in normalized:
        return FailureType.IMPORT_ERROR
    if "pip" in command_lower and "error" in normalized:
        return FailureType.DEPENDENCY_ERROR
    if "mypy" in command_lower or "type error" in normalized:
        return FailureType.TYPE_ERROR
    if "assert" in normalized or "failed" in normalized and "test" in normalized:
        return FailureType.TEST_FAILURE
    if "build" in command_lower and "error" in normalized:
        return FailureType.BUILD_FAILURE
    if "permission denied" in normalized or "unauthorized" in normalized:
        return FailureType.CONFIGURATION_ERROR
    if "command not found" in normalized or "is not recognized" in normalized:
        return FailureType.ENVIRONMENT_ERROR
    if "exception" in normalized or "traceback" in normalized:
        return FailureType.RUNTIME_ERROR
    return FailureType.UNKNOWN
