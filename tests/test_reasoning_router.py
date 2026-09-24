from coding_agent.reasoning import (
    HardwareProfile,
    HeuristicTaskClassifier,
    LLMGateway,
    MockLLMProvider,
    ModelRouter,
    NullLLMProvider,
    RoutingPolicy,
    TaskComplexity,
)


def test_task_classifier_easy_medium_hard() -> None:
    classifier = HeuristicTaskClassifier()
    assert classifier.classify("Explain this DTO") == TaskComplexity.EASY
    assert classifier.classify("Implement payment retry and fix failing tests") == TaskComplexity.MEDIUM
    assert classifier.classify("Redesign architecture for a 500K multi-repo enterprise platform") == TaskComplexity.HARD


def test_model_router_local_policy() -> None:
    router = ModelRouter(
        hardware=HardwareProfile(vram_gb=8.0, system_ram_gb=12.0),
        policy=RoutingPolicy(allow_cloud_fallback=False),
    )
    easy = router.recommend("Explain this method", context_tokens=4000)
    hard = router.recommend("Redesign architecture", context_tokens=24000)

    assert easy.selected_model_key == "qwen2.5-coder-3b-q4"
    assert hard.selected_model_key == "qwen2.5-coder-7b-q4"
    assert hard.local_only is True


def test_llm_gateway_default_null_provider() -> None:
    router = ModelRouter()
    decision = router.recommend("Implement API retry", context_tokens=8000)
    gateway = LLMGateway(default_provider=NullLLMProvider())
    output = gateway.generate(prompt="Implement API retry", routing=decision)
    assert "not configured" in output.lower()
    assert decision.selected_model_key in output


def test_llm_gateway_structured_output_and_stream_contract() -> None:
    router = ModelRouter()
    decision = router.recommend("Return JSON summary", context_tokens=3000)
    gateway = LLMGateway(default_provider=MockLLMProvider(mode="success", name="mock-success"))

    structured = gateway.generate_structured_output(
        prompt="Return a JSON payload",
        routing=decision,
        schema_name="summary",
    )
    streamed = list(gateway.stream_response(prompt="stream", routing=decision))

    assert structured["result"] == "ok"
    assert streamed
