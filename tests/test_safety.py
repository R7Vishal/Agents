import pytest

from coding_agent.safety import SafetyError, validate_command


def test_safety_blocks_dangerous_commands() -> None:
    with pytest.raises(SafetyError):
        validate_command("git reset --hard HEAD")


def test_safety_allows_safe_command() -> None:
    validate_command("pytest -q")
