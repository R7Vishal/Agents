from __future__ import annotations

from .types import HardwareProfile, ModelProfile, RoutingDecision, RoutingPolicy, TaskComplexity


class HeuristicTaskClassifier:
    EASY_KEYWORDS = {
        "explain",
        "dto",
        "skeleton",
        "summarize",
        "what does",
        "rename",
        "comment",
    }
    HARD_KEYWORDS = {
        "redesign",
        "re-architecture",
        "architecture",
        "500k",
        "multi-repo",
        "enterprise-wide",
        "compliance",
    }

    def classify(self, prompt: str, context_tokens: int = 0) -> TaskComplexity:
        text = prompt.strip().lower()

        if context_tokens > 20000:
            return TaskComplexity.HARD
        if any(token in text for token in self.HARD_KEYWORDS):
            return TaskComplexity.HARD
        if len(text) < 220 and any(token in text for token in self.EASY_KEYWORDS):
            return TaskComplexity.EASY
        return TaskComplexity.MEDIUM


class ModelRouter:
    def __init__(
        self,
        hardware: HardwareProfile | None = None,
        policy: RoutingPolicy | None = None,
        classifier: HeuristicTaskClassifier | None = None,
    ) -> None:
        self.hardware = hardware or HardwareProfile()
        self.policy = policy or RoutingPolicy()
        self.classifier = classifier or HeuristicTaskClassifier()

        self.fast_local = ModelProfile(
            key="qwen2.5-coder-3b-q4",
            label="Qwen2.5-Coder-3B-Instruct Q4",
            estimated_vram_gb=2.0,
            role="Fast/MVP coding tasks",
            local=True,
        )
        self.main_local = ModelProfile(
            key="qwen2.5-coder-7b-q4",
            label="Qwen2.5-Coder-7B-Instruct Q4",
            estimated_vram_gb=4.4,
            role="Primary coding/reasoning/fixing model",
            local=True,
        )
        self.cloud_fallback = ModelProfile(
            key="cloud-llm",
            label="Cloud Fallback LLM",
            estimated_vram_gb=0.0,
            role="High complexity overflow",
            local=False,
        )

    def recommend(self, prompt: str, context_tokens: int = 0) -> RoutingDecision:
        bounded_tokens = min(max(context_tokens or self.policy.preferred_context_tokens, 1024), self.policy.max_context_tokens)
        complexity = self.classifier.classify(prompt=prompt, context_tokens=bounded_tokens)

        if complexity == TaskComplexity.EASY:
            model = self.fast_local
            reason = "Simple task routed to fast local coding model."
            return RoutingDecision(
                complexity=complexity,
                selected_model_key=model.key,
                selected_model_label=model.label,
                context_tokens=bounded_tokens,
                local_only=True,
                reason=reason,
            )

        if complexity == TaskComplexity.MEDIUM:
            model = self.main_local if self.main_local.estimated_vram_gb <= self.hardware.vram_gb else self.fast_local
            reason = "Medium task routed to primary local coding model within hardware limits."
            return RoutingDecision(
                complexity=complexity,
                selected_model_key=model.key,
                selected_model_label=model.label,
                context_tokens=bounded_tokens,
                local_only=True,
                reason=reason,
            )

        if self.policy.allow_cloud_fallback:
            reason = "Hard task routed to cloud fallback per routing policy."
            return RoutingDecision(
                complexity=complexity,
                selected_model_key=self.cloud_fallback.key,
                selected_model_label=self.cloud_fallback.label,
                context_tokens=bounded_tokens,
                local_only=False,
                reason=reason,
                fallback_model_key=self.main_local.key,
            )

        reason = "Hard task kept local because cloud fallback is disabled; use primary 7B local model with narrowed context."
        return RoutingDecision(
            complexity=complexity,
            selected_model_key=self.main_local.key,
            selected_model_label=self.main_local.label,
            context_tokens=min(bounded_tokens, 16000),
            local_only=True,
            reason=reason,
            fallback_model_key=self.cloud_fallback.key,
        )
