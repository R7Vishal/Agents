from coding_agent.reasoning import (
    LLMGateway,
    MockLLMProvider,
    ModelRouter,
    ProviderErrorCode,
    ProviderRequest,
)


def _routing():
    return ModelRouter().recommend("Implement retry strategy", context_tokens=4000)


def test_provider_contract_success_schema() -> None:
    gateway = LLMGateway(default_provider=MockLLMProvider(mode="success", name="mock-default"))
    request = ProviderRequest(prompt="hello", routing=_routing(), request_id="req-success")

    response = gateway.invoke(request)

    assert response.ok is True
    assert response.provider_name == "mock-default"
    assert response.model_key
    assert response.usage.total_tokens >= 0


def test_provider_contract_malformed_json_fixture() -> None:
    gateway = LLMGateway(default_provider=MockLLMProvider(mode="malformed_json", name="mock-default"))
    request = ProviderRequest(prompt="return json", routing=_routing(), request_id="req-malformed")

    response = gateway.invoke(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.MALFORMED_OUTPUT


def test_provider_contract_rate_limit_fixture() -> None:
    gateway = LLMGateway(default_provider=MockLLMProvider(mode="rate_limit", name="mock-default"))
    request = ProviderRequest(prompt="rate", routing=_routing(), request_id="req-rate")

    response = gateway.invoke(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.RATE_LIMITED
    assert response.error.retryable is True


def test_provider_contract_timeout_fixture() -> None:
    gateway = LLMGateway(default_provider=MockLLMProvider(mode="timeout", name="mock-default"))
    request = ProviderRequest(prompt="timeout", routing=_routing(), request_id="req-timeout")

    response = gateway.invoke(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.TIMEOUT


def test_provider_contract_context_overflow_fixture() -> None:
    decision = ModelRouter().recommend("very large context", context_tokens=16000)
    gateway = LLMGateway(default_provider=MockLLMProvider(mode="context_overflow", name="mock-default"))
    request = ProviderRequest(prompt="overflow", routing=decision, request_id="req-overflow")

    response = gateway.invoke(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.CONTEXT_OVERFLOW
