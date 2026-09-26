from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..planner import recommend_next_milestone
from ..repo_intel import discover_repository
from ..reasoning import LLMGateway, ModelRouter


@dataclass
class ChatSession:
    session_id: str
    created_at: str
    messages: list[dict[str, str]] = field(default_factory=list)


class CopilotChatService:
    def __init__(
        self,
        max_history: int = 30,
        llm_gateway: LLMGateway | None = None,
        model_router: ModelRouter | None = None,
    ) -> None:
        self.max_history = max_history
        self.llm_gateway = llm_gateway
        self.model_router = model_router
        self._sessions: dict[str, ChatSession] = {}

    def _now(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _get_session(self, session_id: str) -> ChatSession:
        session = self._sessions.get(session_id)
        if session:
            return session

        session = ChatSession(
            session_id=session_id,
            created_at=self._now(),
        )
        self._sessions[session_id] = session
        return session

    def _append_message(
        self,
        session: ChatSession,
        role: str,
        content: str,
    ) -> None:
        session.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": self._now(),
            }
        )

        if len(session.messages) > self.max_history:
            session.messages = session.messages[-self.max_history:]

    def _repo_summary(self, repo_path: Path) -> str:
        facts = discover_repository(repo_path)
        milestone = recommend_next_milestone(facts)

        return "\n".join(
            [
                f"Repository: {facts.repo_path}",
                f"Entry points: {len(facts.entry_points)}",
                f"Package manifests: {len(facts.package_manifests)}",
                f"Test files: {len(facts.test_files)}",
                (
                    "Planner/lifecycle/safety files: "
                    f"{len(facts.planner_files)}/"
                    f"{len(facts.lifecycle_files)}/"
                    f"{len(facts.safety_files)}"
                ),
                f"Next milestone: {milestone.title}",
                f"Reason: {milestone.reason}",
            ]
        )

    def _llm_reply(
        self,
        session: ChatSession,
        prompt: str,
        repo_path: Path,
    ) -> str:
        if self.llm_gateway is None or self.model_router is None:
            return (
                "The local LLM is not connected to the chat service yet. "
                "The Router → Gateway → LM Studio path is available, "
                "but the chat service has not been configured with it."
            )

        # Keep the context intentionally bounded for the local 7B model.
        repo_context = self._repo_summary(repo_path)

        history_items = session.messages[-8:]
        history = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history_items
        )

        context = (
            "You are the local AI coding assistant for this repository.\n\n"
            "REPOSITORY CONTEXT:\n"
            f"{repo_context}\n\n"
            "RECENT CHAT:\n"
            f"{history}\n\n"
            "Instructions:\n"
            "- Answer the user's request directly.\n"
            "- For coding questions, provide practical implementation guidance.\n"
            "- Do not claim that you changed files unless an execution workflow actually did so.\n"
            "- Prefer concise, technically accurate answers.\n"
        )

        decision = self.model_router.recommend(
            prompt=prompt,
            context_tokens=min(
                12000,
                max(4000, len(context) // 4),
            ),
        )

        return self.llm_gateway.generate(
            prompt=prompt,
            routing=decision,
            context=context,
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

        if (
            any(x in prompt_lower for x in ["hi", "hello", "hey"])
            and len(prompt_lower) <= 16
        ):
            response = (
                "I can help with repository questions, coding tasks, "
                "architecture, debugging, tests, and controlled execution."
            )

        elif any(
            x in prompt_lower
            for x in ["help", "what can you do", "capability", "features"]
        ):
            response = (
                "I can:\n"
                "- Answer coding and architecture questions\n"
                "- Analyze the repository\n"
                "- Explain project structure and tests\n"
                "- Suggest implementation approaches\n"
                "- Recommend the appropriate local model\n"
                "- Execute controlled workflows using `/run first-run` or `/run run-plan`"
            )

        elif any(
            x in prompt_lower
            for x in ["status", "history", "what did i ask", "context"]
        ):
            last_user_prompts = [
                m["content"]
                for m in session.messages
                if m["role"] == "user"
            ][-4:]

            response = "Recent context:\n" + "\n".join(
                f"- {item}" for item in last_user_prompts
            )

        else:
            try:
                response = self._llm_reply(
                    session=session,
                    prompt=prompt,
                    repo_path=repo_path,
                )
            except Exception as exc:
                response = (
                    "I could not get a response from the local LLM.\n\n"
                    f"Error: {exc}"
                )

        self._append_message(session, "assistant", response)

        return {
            "session_id": session.session_id,
            "reply": response,
            "message_count": len(session.messages),
        }
