import json
import urllib.error

from coding_agent.reasoning import (
    LMStudioProvider,
    ModelRouter,
    ProviderErrorCode,
    ProviderRequest,
)


def _request() -> ProviderRequest:
    routing = ModelRouter().recommend(
        "Implement retry strategy",
        context_tokens=4000,
    )

    return ProviderRequest(
        prompt="Write a Python retry function.",
        routing=routing,
        request_id="lmstudio-test",
    )


def test_lmstudio_success(monkeypatch) -> None:
    provider = LMStudioProvider(
        base_url="http://localhost:1234/v1",
        model="qwen2.5-coder-7b-instruct",
        max_retries=0,
    )

    response_body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "def retry():\n    pass",
                }
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
        },
    }

    def fake_post(url, body):
        payload = json.loads(body.decode("utf-8"))

        assert url == "http://localhost:1234/v1/chat/completions"
        assert payload["model"] == "qwen2.5-coder-7b-instruct"
        assert payload["stream"] is False

        return 200, json.dumps(response_body)

    monkeypatch.setattr(provider, "_post", fake_post)

    response = provider.invoke(_request())

    assert response.ok is True
    assert response.provider_name == "lmstudio"
    assert "def retry" in response.content
    assert response.usage.total_tokens == 28


def test_lmstudio_rate_limit(monkeypatch) -> None:
    provider = LMStudioProvider(max_retries=0)

    def fake_post(url, body):
        raise urllib.error.HTTPError(
            url,
            429,
            "Too Many Requests",
            {},
            None,
        )

    monkeypatch.setattr(provider, "_post", fake_post)

    response = provider.invoke(_request())

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.RATE_LIMITED
    assert response.error.retryable is True


def test_lmstudio_malformed_response(monkeypatch) -> None:
    provider = LMStudioProvider(max_retries=0)

    def fake_post(url, body):
        return 200, "{invalid json"

    monkeypatch.setattr(provider, "_post", fake_post)

    response = provider.invoke(_request())

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.MALFORMED_OUTPUT


def test_lmstudio_empty_response(monkeypatch) -> None:
    provider = LMStudioProvider(max_retries=0)

    def fake_post(url, body):
        return 200, json.dumps({"choices": []})

    monkeypatch.setattr(provider, "_post", fake_post)

    response = provider.invoke(_request())

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == ProviderErrorCode.MALFORMED_OUTPUT


def test_lmstudio_structured_output(monkeypatch) -> None:
    provider = LMStudioProvider(max_retries=0)

    response_body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"result": "success"}',
                }
            }
        ]
    }

    def fake_post(url, body):
        payload = json.loads(body.decode("utf-8"))
        assert payload["response_format"] == {"type": "json_object"}
        return 200, json.dumps(response_body)

    monkeypatch.setattr(provider, "_post", fake_post)

    request = _request()
    request = type(request)(
        prompt=request.prompt,
        routing=request.routing,
        context=request.context,
        schema_name="test-schema",
        request_id=request.request_id,
    )

    response = provider.invoke(request)

    assert response.ok is True
    assert response.structured_content == {"result": "success"}