from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..governance.safety import SafetyError, validate_command
from .approval_tokens import ApprovalTokenManager
from ..workspace_manager import WorkspaceAccessError, WorkspaceManager
from .registry import ToolDefinition, ToolRegistry


DESTRUCTIVE_GIT_COMMANDS = {"git reset", "git clean", "git push", "git merge", "git checkout --"}


def _git_available(workspace_root: Path) -> bool:
    return (workspace_root / ".git").exists()


def _run_process(command: str, cwd: Path, timeout: int) -> tuple[int, str, str, float]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = round(time.perf_counter() - start, 4)
        return proc.returncode, proc.stdout, proc.stderr, duration
    except subprocess.TimeoutExpired as exc:
        duration = round(time.perf_counter() - start, 4)
        return 124, (exc.stdout or ""), (exc.stderr or ""), duration


def register_default_tools(
    registry: ToolRegistry,
    workspace: WorkspaceManager,
    *,
    mode: str = "auto",
    approval_tokens: ApprovalTokenManager | None = None,
) -> None:
    normalized_mode = mode.strip().lower()

    def _is_safe_mode() -> bool:
        return normalized_mode == "safe"

    def _require_write_allowed(tool_name: str, approved: bool = False) -> dict[str, Any] | None:
        if _is_safe_mode() and not approved:
            return {
                "success": False,
                "operation": tool_name,
                "error": "SAFE mode blocks write operations unless approved=true",
            }
        return None

    def _require_approval_token(action: str, args: dict[str, Any]) -> dict[str, Any] | None:
        manager = approval_tokens
        if manager is None:
            return {
                "success": False,
                "operation": action,
                "error": "Approval token manager is not configured",
            }
        token = str(args.get("approval_token", "")).strip()
        if not token:
            request = manager.request(action=action, details=str(args))
            return {
                "success": False,
                "operation": action,
                "error": "Approval token required for destructive action",
                "approval_required": True,
                "approval_request": request,
            }
        if not manager.consume(token=token, action=action):
            return {
                "success": False,
                "operation": action,
                "error": "Invalid, expired, or already used approval token",
                "approval_required": True,
            }
        return None

    registry.register(
        ToolDefinition(
            name="read_file",
            description="Read file contents inside workspace.",
            parameters={"path": "string"},
            safety="read",
            executor=lambda args: workspace.read_file(str(args.get("path", ""))),
        )
    )
    registry.register(
        ToolDefinition(
            name="write_file",
            description="Overwrite or create file inside workspace.",
            parameters={"path": "string", "content": "string", "approved": "bool(optional)"},
            safety="write",
            executor=lambda args: (
                _require_write_allowed("write_file", bool(args.get("approved", False)))
                or workspace.write_file(str(args.get("path", "")), str(args.get("content", "")))
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="create_file",
            description="Create a new file with optional content.",
            parameters={"path": "string", "content": "string(optional)", "overwrite": "bool(optional)", "approved": "bool(optional)"},
            safety="write",
            executor=lambda args: (
                _require_write_allowed("create_file", bool(args.get("approved", False)))
                or workspace.create_file(
                    str(args.get("path", "")),
                    str(args.get("content", "")),
                    overwrite=bool(args.get("overwrite", False)),
                )
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="edit_file",
            description="Edit file by replacement or full-content update.",
            parameters={
                "path": "string",
                "old_text": "string(optional)",
                "new_text": "string(optional)",
                "content": "string(optional)",
                "approved": "bool(optional)",
            },
            safety="write",
            executor=lambda args: (
                _require_write_allowed("edit_file", bool(args.get("approved", False)))
                or workspace.edit_file(
                    str(args.get("path", "")),
                    old_text=str(args.get("old_text")) if args.get("old_text") is not None else None,
                    new_text=str(args.get("new_text")) if args.get("new_text") is not None else None,
                    content=str(args.get("content")) if args.get("content") is not None else None,
                )
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="delete_file",
            description="Delete a file inside workspace.",
            parameters={"path": "string", "approved": "bool(required in safe/auto for destructive ops)"},
            safety="destructive",
            executor=lambda args: (
                _require_write_allowed("delete_file", bool(args.get("approved", False)))
                or _require_approval_token("delete_file", args)
                or (
                    workspace.delete_file(str(args.get("path", "")))
                    if bool(args.get("approved", False))
                    else {
                        "success": False,
                        "operation": "delete_file",
                        "error": "delete_file requires approved=true",
                    }
                )
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="rename_file",
            description="Rename/move a file inside workspace.",
            parameters={"old_path": "string", "new_path": "string", "approved": "bool(optional)"},
            safety="write",
            executor=lambda args: (
                _require_write_allowed("rename_file", bool(args.get("approved", False)))
                or workspace.rename_file(str(args.get("old_path", "")), str(args.get("new_path", "")))
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="list_directory",
            description="List directory entries inside workspace.",
            parameters={"path": "string(optional)"},
            safety="read",
            executor=lambda args: workspace.list_directory(str(args.get("path", "."))),
        )
    )
    registry.register(
        ToolDefinition(
            name="search_files",
            description="Search files by glob-like name/path pattern.",
            parameters={"pattern": "string", "root": "string(optional)"},
            safety="read",
            executor=lambda args: workspace.search_files(str(args.get("pattern", "*")), root=str(args.get("root", "."))),
        )
    )
    registry.register(
        ToolDefinition(
            name="search_text",
            description="Search text/regex in files in workspace.",
            parameters={"query": "string", "root": "string(optional)", "is_regex": "bool(optional)", "max_results": "int(optional)"},
            safety="read",
            executor=lambda args: workspace.search_text(
                str(args.get("query", "")),
                root=str(args.get("root", ".")),
                is_regex=bool(args.get("is_regex", False)),
                max_results=int(args.get("max_results", 200) or 200),
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="project_structure",
            description="Return project structure snapshot.",
            parameters={"root": "string(optional)", "max_items": "int(optional)"},
            safety="read",
            executor=lambda args: workspace.project_structure(
                root=str(args.get("root", ".")),
                max_items=int(args.get("max_items", 300) or 300),
            ),
        )
    )

    def _execute_command(args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", "")).strip()
        timeout = int(args.get("timeout", 120) or 120)
        if not command:
            return {"success": False, "operation": "execute_command", "error": "command is required"}

        try:
            validate_command(command, require_allowlist=True, repo_path=workspace.workspace_root)
        except SafetyError as exc:
            return {"success": False, "operation": "execute_command", "error": str(exc)}

        exit_code, stdout, stderr, duration = _run_process(command, workspace.workspace_root, timeout)
        return {
            "success": exit_code == 0,
            "operation": "execute_command",
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration": duration,
        }

    registry.register(
        ToolDefinition(
            name="execute_command",
            description="Run an allowed shell command in workspace.",
            parameters={"command": "string", "timeout": "int(optional)"},
            safety="execute",
            executor=_execute_command,
        )
    )

    def _run_tests(args: dict[str, Any]) -> dict[str, Any]:
        detected = _detect_test_command(workspace.workspace_root)
        if not detected:
            return {
                "success": False,
                "operation": "run_tests",
                "error": "No known test command detected",
            }
        timeout = int(args.get("timeout", 300) or 300)
        exit_code, stdout, stderr, duration = _run_process(detected, workspace.workspace_root, timeout)
        return {
            "success": exit_code == 0,
            "operation": "run_tests",
            "command": detected,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration": duration,
        }

    registry.register(
        ToolDefinition(
            name="run_tests",
            description="Detect and execute project tests.",
            parameters={"timeout": "int(optional)"},
            safety="execute",
            executor=_run_tests,
        )
    )

    def _git_command(args: dict[str, Any], command: str, op: str) -> dict[str, Any]:
        if not _git_available(workspace.workspace_root):
            return {"success": False, "operation": op, "error": "Not a git repository"}
        timeout = int(args.get("timeout", 60) or 60)
        exit_code, stdout, stderr, duration = _run_process(command, workspace.workspace_root, timeout)
        return {
            "success": exit_code == 0,
            "operation": op,
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration": duration,
        }

    registry.register(
        ToolDefinition(
            name="git_status",
            description="Get git working tree status.",
            parameters={},
            safety="read",
            executor=lambda args: _git_command(args, "git status --short --branch", "git_status"),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_diff",
            description="Get git diff.",
            parameters={"staged": "bool(optional)"},
            safety="read",
            executor=lambda args: _git_command(
                args,
                "git diff --cached" if bool(args.get("staged", False)) else "git diff",
                "git_diff",
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_log",
            description="Get git commit history.",
            parameters={"limit": "int(optional)"},
            safety="read",
            executor=lambda args: _git_command(
                args,
                f"git log --oneline -n {int(args.get('limit', 10) or 10)}",
                "git_log",
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="git_branch",
            description="List branches.",
            parameters={},
            safety="read",
            executor=lambda args: _git_command(args, "git branch --all", "git_branch"),
        )
    )

    def _git_create_branch(args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name", "")).strip()
        if not name:
            return {"success": False, "operation": "git_create_branch", "error": "name is required"}
        if _is_safe_mode() and not bool(args.get("approved", False)):
            return {"success": False, "operation": "git_create_branch", "error": "SAFE mode requires approved=true"}
        return _git_command(args, f"git checkout -b {name}", "git_create_branch")

    registry.register(
        ToolDefinition(
            name="git_create_branch",
            description="Create and checkout new branch.",
            parameters={"name": "string", "approved": "bool(optional)"},
            safety="write",
            executor=_git_create_branch,
        )
    )

    def _git_checkout(args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name", "")).strip()
        if not name:
            return {"success": False, "operation": "git_checkout", "error": "name is required"}
        if _is_safe_mode() and not bool(args.get("approved", False)):
            return {"success": False, "operation": "git_checkout", "error": "SAFE mode requires approved=true"}
        return _git_command(args, f"git checkout {name}", "git_checkout")

    registry.register(
        ToolDefinition(
            name="git_checkout",
            description="Checkout existing branch.",
            parameters={"name": "string", "approved": "bool(optional)"},
            safety="write",
            executor=_git_checkout,
        )
    )

    def _git_add(args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pathspec", ".")).strip() or "."
        if _is_safe_mode() and not bool(args.get("approved", False)):
            return {"success": False, "operation": "git_add", "error": "SAFE mode requires approved=true"}
        return _git_command(args, f"git add {pattern}", "git_add")

    registry.register(
        ToolDefinition(
            name="git_add",
            description="Stage changes for commit.",
            parameters={"pathspec": "string(optional)", "approved": "bool(optional)"},
            safety="write",
            executor=_git_add,
        )
    )

    def _git_commit(args: dict[str, Any]) -> dict[str, Any]:
        message = str(args.get("message", "")).strip()
        if not message:
            return {"success": False, "operation": "git_commit", "error": "message is required"}
        token_error = _require_approval_token("git_commit", args)
        if token_error:
            return token_error
        if normalized_mode != "full" and not bool(args.get("approved", False)):
            return {
                "success": False,
                "operation": "git_commit",
                "error": "git_commit requires approved=true unless running in FULL mode",
            }
        return _git_command(args, f'git commit -m "{message.replace("\"", "\\\"")}"', "git_commit")

    registry.register(
        ToolDefinition(
            name="git_commit",
            description="Create git commit (approval required unless FULL mode).",
            parameters={"message": "string", "approved": "bool(optional)"},
            safety="destructive",
            executor=_git_commit,
        )
    )

    def _block_destructive(args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", "")).strip()
        lowered = command.lower()
        if any(token in lowered for token in DESTRUCTIVE_GIT_COMMANDS):
            return {
                "success": False,
                "operation": "git_dangerous",
                "error": "Destructive git operation requires explicit manual approval outside tool registry",
            }
        return {"success": True, "operation": "git_dangerous", "message": "No dangerous operation detected"}

    registry.register(
        ToolDefinition(
            name="git_dangerous_guard",
            description="Guardrail checker for dangerous git commands.",
            parameters={"command": "string"},
            safety="read",
            executor=_block_destructive,
        )
    )


def _detect_test_command(workspace_root: Path) -> str:
    if (workspace_root / "pyproject.toml").exists() or (workspace_root / "pytest.ini").exists() or (workspace_root / "tests").exists():
        return "pytest"
    if (workspace_root / "package.json").exists():
        return "npm test"
    if (workspace_root / "pom.xml").exists():
        return "mvn test"
    if (workspace_root / "build.gradle").exists() or (workspace_root / "build.gradle.kts").exists():
        return "gradle test"
    if any(workspace_root.glob("*.sln")) or any(workspace_root.rglob("*.csproj")):
        return "dotnet test"
    return ""
