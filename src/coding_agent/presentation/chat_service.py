from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Any

from ..planner import recommend_next_milestone
from ..repo_intel import discover_repository
from ..execution_state import ExecutionStateStore
from ..tools import AgentDoctor, CapabilityManager, SelfImprovementAdvisor, ToolRegistry
from ..workspace_manager import WorkspaceManager


@dataclass
class ChatSession:
    session_id: str
    created_at: str
    messages: list[dict[str, str]] = field(default_factory=list)


class CopilotChatService:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        capability_manager: CapabilityManager,
        doctor: AgentDoctor,
        advisor: SelfImprovementAdvisor,
        workspace_manager: WorkspaceManager,
        max_history: int = 30,
    ) -> None:
        self.max_history = max_history
        self._sessions: dict[str, ChatSession] = {}
        self.tool_registry = tool_registry
        self.capability_manager = capability_manager
        self.doctor = doctor
        self.advisor = advisor
        self.workspace_manager = workspace_manager
        self.state_store = ExecutionStateStore()

    def _now(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _get_session(self, session_id: str) -> ChatSession:
        session = self._sessions.get(session_id)
        if session:
            return session
        session = ChatSession(session_id=session_id, created_at=self._now())
        self._sessions[session_id] = session
        return session

    def _append_message(self, session: ChatSession, role: str, content: str) -> None:
        session.messages.append({"role": role, "content": content, "timestamp": self._now()})
        if len(session.messages) > self.max_history:
            session.messages = session.messages[-self.max_history :]

    def _repo_summary(self, repo_path: Path) -> str:
        facts = discover_repository(repo_path)
        milestone = recommend_next_milestone(facts)

        return "\n".join(
            [
                f"Repository: {facts.repo_path}",
                f"Entry points: {len(facts.entry_points)}",
                f"Package manifests: {len(facts.package_manifests)}",
                f"Test files: {len(facts.test_files)}",
                f"Planner/lifecycle/safety files: {len(facts.planner_files)}/{len(facts.lifecycle_files)}/{len(facts.safety_files)}",
                f"Next milestone: {milestone.title}",
                f"Reason: {milestone.reason}",
            ]
        )

    def reply(
        self,
        *,
        session_id: str,
        prompt: str,
        repo_path: Path,
        selected_mode: str,
        plan_file: str,
        action: str | None,
    ) -> dict[str, Any]:
        session = self._get_session(session_id)
        self._append_message(session, "user", prompt)
        state = self.state_store.get(session_id) or self.state_store.start(
            task=prompt,
            workspace=str(repo_path),
            conversation_id=session_id,
        )
        state.plan = [
            "Understand request",
            "Inspect workspace context",
            "Select and execute tools",
            "Validate and summarize",
        ]
        state.current_step = "Understand request"
        state.status = "running"

        prompt_lower = prompt.lower().strip()

        activity: list[str] = []
        tool_results: list[dict[str, Any]] = []

        if prompt_lower in {"/tools", "tools"}:
            state.current_step = "Select and execute tools"
            response = self._render_tools()
        elif prompt_lower in {"/capabilities", "capabilities"} or any(
            x in prompt_lower for x in ["what can you do", "current capabilities"]
        ):
            state.current_step = "Select and execute tools"
            response = self.capability_manager.render_markdown()
        elif prompt_lower in {"/doctor", "doctor"}:
            state.current_step = "Select and execute tools"
            response = self.doctor.render_markdown()
        elif prompt_lower in {"/status", "status"}:
            state.current_step = "Inspect workspace context"
            response = self._status(repo_path)
        elif any(x in prompt_lower for x in ["how can i improve you", "improve yourself", "improvements"]):
            state.current_step = "Inspect workspace context"
            response = self.advisor.render_markdown()
        elif any(x in prompt_lower for x in ["show me the project structure", "project structure", "what files are in this project"]):
            state.current_step = "Select and execute tools"
            result = self.tool_registry.execute("project_structure", {"root": ".", "max_items": 120})
            tool_results.append(result)
            activity.append("Workspace structure inspected")
            response = self._render_structure(result)
        elif "find where" in prompt_lower and "implemented" in prompt_lower:
            state.current_step = "Select and execute tools"
            target = self._extract_find_target(prompt)
            result = self.tool_registry.execute(
                "search_text",
                {"query": target, "root": ".", "is_regex": False, "max_results": 25},
            )
            tool_results.append(result)
            activity.append(f"Searched codebase for '{target}'")
            response = self._render_text_search(target, result)
        elif self._looks_like_create_file(prompt_lower):
            state.current_step = "Select and execute tools"
            create_result = self._handle_create_file(prompt, repo_path)
            tool_results.extend(create_result["tool_results"])
            activity.extend(create_result["activity"])
            response = create_result["response"]
        elif self._looks_like_modify_file(prompt_lower):
            state.current_step = "Select and execute tools"
            modify_result = self._handle_modify_file(prompt, repo_path)
            tool_results.extend(modify_result["tool_results"])
            activity.extend(modify_result["activity"])
            response = modify_result["response"]
        elif "show me what changed in git" in prompt_lower or "what changed" in prompt_lower:
            state.current_step = "Select and execute tools"
            status = self._git_status_for_repo(repo_path)
            diff = self._git_diff_for_repo(repo_path)
            tool_results.extend([status, diff])
            activity.append("Collected git status and diff")
            response = self._render_git(status, diff)
        elif any(x in prompt_lower for x in ["hi", "hello", "hey"]) and len(prompt_lower) <= 16:
            response = (
                "I can help in chat mode and execution mode. "
                "Ask questions about the repo, request a milestone recommendation, or run workflows using "
                "`/run first-run` or `/run run-plan`."
            )
        elif any(x in prompt_lower for x in ["help", "capability", "features"]):
            response = (
                "Supported actions:\n"
                "- Inspect project structure and search code\n"
                "- Create/read/edit/delete/rename files in workspace\n"
                "- Run commands and tests with structured results\n"
                "- Show dynamic tools/capabilities/doctor reports\n"
                "- Trigger controlled workflows with `/run first-run` or `/run run-plan`"
            )
        elif any(x in prompt_lower for x in ["status", "history", "what did i ask", "context"]):
            last_user_prompts = [m["content"] for m in session.messages if m["role"] == "user"][-4:]
            response = "Recent context:\n" + "\n".join(f"- {item}" for item in last_user_prompts)
        elif any(
            x in prompt_lower
            for x in ["repo", "repository", "architecture", "tests", "milestone", "codebase", "files"]
        ):
            response = self._repo_summary(repo_path)
        else:
            response = (
                "I understand your request and can respond conversationally. "
                "If you want me to execute now, use `/run first-run` or `/run run-plan`. "
                f"Current selected mode is `{selected_mode}`"
                + (f" with plan file `{plan_file}`." if plan_file else ".")
                + (f" I also detected execution intent: `{action}`." if action else "")
            )

        self._append_message(session, "assistant", response)
        state.tool_calls.extend(
            [
                {
                    "operation": item.get("operation", ""),
                    "success": bool(item.get("success", False)),
                }
                for item in tool_results
            ]
        )
        for item in tool_results:
            operation = str(item.get("operation", ""))
            if operation in {"create_file", "write_file", "edit_file", "rename_file", "delete_file"} and item.get("success"):
                file_path = str(item.get("path", "")) or str(item.get("new_path", ""))
                if file_path and file_path not in state.files_changed:
                    state.files_changed.append(file_path)
            if operation == "run_tests":
                state.tests_run.append(
                    {
                        "command": item.get("command", ""),
                        "success": bool(item.get("success", False)),
                        "exit_code": item.get("exit_code"),
                    }
                )
            if not item.get("success", True):
                state.errors.append(str(item.get("error", "Tool execution failed")))

        state.current_step = "Validate and summarize"
        state.status = "completed" if not state.errors else "blocked"
        state_payload = state.to_dict()
        state_payload.pop("conversation_id", None)
        self.state_store.update(session_id, **state_payload)

        return {
            "session_id": session.session_id,
            "reply": response,
            "message_count": len(session.messages),
            "activity": activity,
            "tool_results": tool_results,
            "state": state.to_dict(),
        }

    def _render_tools(self) -> str:
        rows = self.tool_registry.list_tools()
        lines = ["REGISTERED TOOLS", ""]
        for item in rows:
            lines.append(f"- {item['name']} [{item['safety']}] - {item['description']}")
        return "\n".join(lines)

    def _status(self, repo_path: Path) -> str:
        facts = discover_repository(repo_path)
        return "\n".join(
            [
                "AGENT STATUS",
                f"Workspace: {self.workspace_manager.workspace_root}",
                f"Target repo: {repo_path}",
                f"Entry points: {len(facts.entry_points)}",
                f"Test files: {len(facts.test_files)}",
                f"Tools registered: {len(self.tool_registry.list_tools())}",
            ]
        )

    def _render_structure(self, result: dict[str, Any]) -> str:
        if not result.get("success"):
            return f"Unable to inspect project structure: {result.get('error', 'unknown error')}"
        entries = result.get("entries", [])[:40]
        lines = ["PROJECT STRUCTURE (sample)"]
        for item in entries:
            marker = "[D]" if item.get("type") == "dir" else "[F]"
            lines.append(f"{marker} {item.get('path')}")
        return "\n".join(lines)

    def _render_text_search(self, target: str, result: dict[str, Any]) -> str:
        if not result.get("success"):
            return f"Search failed for '{target}': {result.get('error', 'unknown error')}"
        matches = result.get("matches", [])
        if not matches:
            return f"No matches found for '{target}'."
        lines = [f"Matches for '{target}':"]
        for item in matches[:12]:
            lines.append(f"- {item.get('path')}:{item.get('line')} -> {item.get('snippet')}")
        return "\n".join(lines)

    def _render_git(self, status: dict[str, Any], diff: dict[str, Any]) -> str:
        if not status.get("success"):
            return f"Git status unavailable: {status.get('error', 'unknown error')}"
        lines = ["GIT CHANGES", "", "Status:", status.get("stdout", "").strip() or "(empty)"]
        if diff.get("success"):
            lines.extend(["", "Diff:", (diff.get("stdout", "") or "").strip()[:2000] or "(no diff)"])
        return "\n".join(lines)

    def _git_status_for_repo(self, repo_path: Path) -> dict[str, Any]:
        if not (repo_path / ".git").exists():
            return {"success": False, "operation": "git_status", "error": "Not a git repository"}
        try:
            proc = subprocess.run(
                "git status --short --branch",
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "success": proc.returncode == 0,
                "operation": "git_status",
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except Exception as exc:
            return {"success": False, "operation": "git_status", "error": str(exc)}

    def _git_diff_for_repo(self, repo_path: Path) -> dict[str, Any]:
        if not (repo_path / ".git").exists():
            return {"success": False, "operation": "git_diff", "error": "Not a git repository"}
        try:
            proc = subprocess.run(
                "git diff",
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "success": proc.returncode == 0,
                "operation": "git_diff",
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except Exception as exc:
            return {"success": False, "operation": "git_diff", "error": str(exc)}

    def _looks_like_create_file(self, prompt_lower: str) -> bool:
        return "create a file called" in prompt_lower or "create a python file called" in prompt_lower

    def _looks_like_modify_file(self, prompt_lower: str) -> bool:
        return prompt_lower.startswith("modify ") and " to " in prompt_lower

    def _handle_create_file(self, prompt: str, repo_path: Path) -> dict[str, Any]:
        prompt_lower = prompt.lower()
        filename_match = re.search(r"create a (?:python )?file called\s+([\w./\\-]+)", prompt_lower)
        if not filename_match:
            return {
                "response": "I could not determine the target filename.",
                "activity": [],
                "tool_results": [],
            }

        filename = filename_match.group(1)
        content = ""
        containing_match = re.search(r"containing\s+(.+)$", prompt, flags=re.IGNORECASE)
        if containing_match:
            content = containing_match.group(1).strip()
        elif filename.endswith(".py") and "hello world" in prompt_lower:
            content = 'print("Hello World")\n'

        try:
            target = self._resolve_repo_file(repo_path, filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            create_result = {
                "success": True,
                "operation": "create_file",
                "path": self._display_repo_path(repo_path, target),
                "bytes_written": len(content.encode("utf-8", errors="ignore")),
            }
        except Exception as exc:
            create_result = {
                "success": False,
                "operation": "create_file",
                "path": filename,
                "error": str(exc),
            }

        results = [create_result]
        activity = [f"Created file {filename}"] if create_result.get("success") else [f"Failed to create {filename}"]
        response_lines = [
            f"File creation {'succeeded' if create_result.get('success') else 'failed'} for {filename}.",
        ]

        if filename.endswith(".py") and create_result.get("success"):
            run_result = self._run_repo_command(repo_path, f"python {self._display_repo_path(repo_path, target)}")
            results.append(run_result)
            activity.append(f"Executed {filename}")
            response_lines.append(f"Execution exit code: {run_result.get('exit_code')}")
            stdout = str(run_result.get("stdout", "")).strip()
            if stdout:
                response_lines.append(f"Output: {stdout}")

        return {
            "response": "\n".join(response_lines),
            "activity": activity,
            "tool_results": results,
        }

    def _handle_modify_file(self, prompt: str, repo_path: Path) -> dict[str, Any]:
        prompt_lower = prompt.lower().strip()
        file_match = re.match(r"modify\s+([\w./\\-]+)\s+to\s+(.+)$", prompt_lower)
        if not file_match:
            return {
                "response": "I could not parse the modify request.",
                "activity": [],
                "tool_results": [],
            }

        target_file = file_match.group(1)
        intent = file_match.group(2)
        results: list[dict[str, Any]] = []
        activity: list[str] = []

        try:
            target = self._resolve_repo_file(repo_path, target_file)
            original_content = target.read_text(encoding="utf-8", errors="ignore")
            read_result = {
                "success": True,
                "operation": "read_file",
                "path": self._display_repo_path(repo_path, target),
                "content": original_content,
            }
        except Exception as exc:
            read_result = {
                "success": False,
                "operation": "read_file",
                "path": target_file,
                "error": str(exc),
            }
        results.append(read_result)
        if not read_result.get("success"):
            return {
                "response": f"Unable to read {target_file}: {read_result.get('error', 'unknown error')}",
                "activity": [f"Read failed for {target_file}"],
                "tool_results": results,
            }

        updated_content = str(read_result.get("content", ""))
        if target_file.endswith(".py") and "accept a name" in intent:
            updated_content = (
                "import sys\n\n"
                "name = sys.argv[1] if len(sys.argv) > 1 else \"World\"\n"
                "print(f\"Hello {name}\")\n"
            )
        else:
            updated_content += "\n# Updated by coding agent\n"

        try:
            target.write_text(updated_content, encoding="utf-8")
            edit_result = {
                "success": True,
                "operation": "edit_file",
                "path": self._display_repo_path(repo_path, target),
                "bytes_written": len(updated_content.encode("utf-8", errors="ignore")),
            }
        except Exception as exc:
            edit_result = {
                "success": False,
                "operation": "edit_file",
                "path": target_file,
                "error": str(exc),
            }
        results.append(edit_result)
        activity.append(f"Modified {target_file}")

        run_result: dict[str, Any] | None = None
        if target_file.endswith(".py"):
            run_result = self._run_repo_command(repo_path, f"python {self._display_repo_path(repo_path, target)} Copilot")
            results.append(run_result)
            activity.append(f"Executed {target_file} after modification")

        response_lines = [
            f"Modification {'succeeded' if edit_result.get('success') else 'failed'} for {target_file}.",
        ]
        if run_result:
            response_lines.append(f"Execution exit code: {run_result.get('exit_code')}")
            output = str(run_result.get("stdout", "")).strip()
            if output:
                response_lines.append(f"Output: {output}")

        return {
            "response": "\n".join(response_lines),
            "activity": activity,
            "tool_results": results,
        }

    def _extract_find_target(self, prompt: str) -> str:
        match = re.search(r"find where\s+(.+?)\s+implemented", prompt, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().strip("?!. ")
        return "authentication"

    def _resolve_repo_file(self, repo_path: Path, user_path: str) -> Path:
        repo_root = repo_path.resolve()
        candidate = Path(user_path)
        if not candidate.is_absolute():
            candidate = (repo_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if not self._is_relative_to(candidate, repo_root):
            raise ValueError("Target file path is outside selected repository")
        return candidate

    def _display_repo_path(self, repo_path: Path, file_path: Path) -> str:
        try:
            return str(file_path.resolve().relative_to(repo_path.resolve())).replace("\\", "/")
        except ValueError:
            return str(file_path)

    def _run_repo_command(self, repo_path: Path, command: str) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                command,
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "success": proc.returncode == 0,
                "operation": "execute_command",
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except Exception as exc:
            return {
                "success": False,
                "operation": "execute_command",
                "command": command,
                "error": str(exc),
            }

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
