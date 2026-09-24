from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..planner import recommend_next_milestone
from ..repo_intel import discover_repository


@dataclass
class ChatSession:
    session_id: str
    created_at: str
    messages: list[dict[str, str]] = field(default_factory=list)


class CopilotChatService:
    def __init__(self, max_history: int = 30) -> None:
        self.max_history = max_history
        self._sessions: dict[str, ChatSession] = {}

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
    ) -> dict[str, str | int]:
        session = self._get_session(session_id)
        self._append_message(session, "user", prompt)

        prompt_lower = prompt.lower().strip()

        if any(x in prompt_lower for x in ["hi", "hello", "hey"]) and len(prompt_lower) <= 16:
            response = (
                "I can help in chat mode and execution mode. "
                "Ask questions about the repo, request a milestone recommendation, or run workflows using "
                "`/run first-run` or `/run run-plan`."
            )
        elif any(x in prompt_lower for x in ["help", "what can you do", "capability", "features"]):
            response = (
                "Supported actions:\n"
                "- Explain project structure and current capabilities\n"
                "- Summarize tests, manifests, and architecture hints\n"
                "- Suggest next milestone and acceptance criteria\n"
                "- Trigger execution with `/run first-run` or `/run run-plan`\n"
                "- Keep multi-turn context in this chat session"
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
        return {
            "session_id": session.session_id,
            "reply": response,
            "message_count": len(session.messages),
        }
