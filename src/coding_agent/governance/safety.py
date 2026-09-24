from __future__ import annotations

import shlex
from pathlib import Path


class SafetyError(RuntimeError):
    pass


BLOCKED_COMMAND_TOKENS = {
    "rm -rf",
    "format",
    "del /s",
    "rmdir /s",
    "git reset --hard",
    "git clean -fd",
    "shutdown",
    "reboot",
}

DEFAULT_ALLOWED_PREFIXES = {
    "python",
    "py",
    "pytest",
    "pip",
    "npm",
    "npx",
    "mvn",
    "gradle",
    "echo",
    "type",
    "cat",
    "dir",
    "ls",
    "git",
    "docker",
}

WRITE_OPERATION_TOKENS = {
    " > ",
    ">>",
    "copy ",
    "move ",
    "mv ",
    "cp ",
    "set-content",
    "add-content",
    "out-file",
}


def validate_command(
    command: str,
    *,
    require_allowlist: bool = False,
    allowed_prefixes: set[str] | None = None,
    repo_path: Path | None = None,
    scoped_write_paths: list[Path] | None = None,
) -> None:
    normalized = command.lower()
    for token in BLOCKED_COMMAND_TOKENS:
        if token in normalized:
            raise SafetyError(f"Blocked unsafe command: {token}")

    if require_allowlist:
        prefixes = allowed_prefixes or DEFAULT_ALLOWED_PREFIXES
        first_token = _first_command_token(command).lower()
        first_name = Path(first_token).name.lower() if first_token else ""
        allowed = first_token in prefixes or first_name in prefixes or first_name.startswith("python")
        if first_token and not allowed:
            raise SafetyError(f"Command is not in allowlist: {first_token}")

    if repo_path and scoped_write_paths and _looks_like_write_command(normalized):
        _assert_scoped_paths(command=command, repo_path=repo_path, scoped_write_paths=scoped_write_paths)


def assert_no_target_write(discovery_only: bool) -> None:
    if not discovery_only:
        return


def _looks_like_write_command(normalized_command: str) -> bool:
    return any(token in normalized_command for token in WRITE_OPERATION_TOKENS)


def _assert_scoped_paths(command: str, repo_path: Path, scoped_write_paths: list[Path]) -> None:
    allowed_roots = [path.resolve() for path in scoped_write_paths]
    tokens = [chunk.strip('"\'') for chunk in command.split()]
    candidates = [token for token in tokens if _looks_like_path_token(token)]

    for token in candidates:
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = (repo_path / candidate).resolve()
        if not any(_is_relative_to(candidate, root) for root in allowed_roots):
            raise SafetyError(f"Write path is outside allowed scope: {candidate}")


def _looks_like_path_token(token: str) -> bool:
    if token.startswith("-"):
        return False
    return any(separator in token for separator in ["/", "\\", "."])


def _first_command_token(command: str) -> str:
    stripped = command.strip()
    if not stripped:
        return ""
    try:
        parts = shlex.split(stripped, posix=False)
    except ValueError:
        parts = stripped.split()
    if not parts:
        return ""
    return parts[0].strip('"').strip("'")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
