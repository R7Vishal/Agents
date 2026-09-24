from coding_agent.reasoning import (
    HardwareProfile,
    LLMGateway,
    MockLLMProvider,
    ModelRouter,
    ProviderRequest,
    RoutingPolicy,
)


def test_gateway_fallback_and_audit_events() -> None:
    router = ModelRouter(
        hardware=HardwareProfile(vram_gb=8.0, system_ram_gb=12.0),
        policy=RoutingPolicy(allow_cloud_fallback=False),
    )
    decision = router.recommend(
        "Redesign architecture for a 500K multi-repo enterprise platform",
        context_tokens=24000,
    )

    gateway = LLMGateway(default_provider=MockLLMProvider(mode="success", name="default-provider"))
    gateway.register_provider(decision.selected_model_key, MockLLMProvider(mode="rate_limit", name="primary-provider"))
    gateway.register_provider(decision.fallback_model_key, MockLLMProvider(mode="success", name="fallback-provider"))

    response = gateway.invoke(
        ProviderRequest(
            prompt="Perform architecture plan",
            routing=decision,
            request_id="req-fallback",
        )
    )

    assert response.ok is True
    assert response.provider_name == "fallback-provider"

    audits = gateway.audit_events()
    assert len(audits) == 1
    event = audits[0]
    assert event.event == "provider_fallback"
    assert event.request_id == "req-fallback"
    assert event.success is True
    assert event.fallback_used is True
    assert event.error_code == "RATE_LIMITED"


def test_gateway_no_fallback_audit_on_failure() -> None:
    decision = ModelRouter().recommend("Explain this dto", context_tokens=4000)

    gateway = LLMGateway(default_provider=MockLLMProvider(mode="timeout", name="timeout-provider"))
    response = gateway.invoke(
        ProviderRequest(
            prompt="quick",
            routing=decision,
            request_id="req-no-fallback",
        )
    )

    assert response.ok is False
    audits = gateway.audit_events()
    assert len(audits) == 1
    assert audits[0].event == "provider_invoke"
    assert audits[0].success is False
    assert audits[0].error_code == "TIMEOUT"
