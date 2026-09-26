from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from .types import (
    ProviderError,
    ProviderErrorCode,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
    RoutingDecision,
)


@dataclass
class LMStudioProvider:
    """
    Provider adapter for LM Studio's OpenAI-compatible API.

    The coding agent uses logical model keys such as:
        qwen2.5-coder-7b-q4

    LM Studio receives the physical model identifier:
        qwen2.5-coder-7b-instruct
    """

    name: str = "lmstudio"
    base_url: str = ""
    model: str = ""
    timeout_seconds: float = 120.0
    max_retries: int = 1

    def __post_init__(self) -> None:
        self.base_url = (
            self.base_url
            or os.getenv("AI_LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        ).rstrip("/")

        self.model = (
            self.model
            or os.getenv(
                "AI_LMSTUDIO_MODEL",
                "qwen2.5-coder-7b-instruct",
            )
        )

        timeout_value = os.getenv("AI_TIMEOUT_SECONDS", "")
        if timeout_value:
            try:
                self.timeout_seconds = float(timeout_value)
            except ValueError:
                pass

        retries_value = os.getenv("AI_MAX_RETRIES", "")
        if retries_value:
            try:
                self.max_retries = max(0, int(retries_value))
            except ValueError:
                pass

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        messages = self._build_messages(request)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }

        if request.schema_name:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/chat/completions"

        attempts = self.max_retries + 1

        for attempt in range(attempts):
            try:
                status, raw_body = self._post(url=url, body=body)
                return self._parse_response(
                    request=request,
                    status=status,
                    raw_body=raw_body,
                )

            except urllib.error.HTTPError as exc:
                raw_body = self._read_error_body(exc)

                if exc.code == 429:
                    return self._error_response(
                        request,
                        ProviderErrorCode.RATE_LIMITED,
                        "LM Studio returned HTTP 429 (rate limited).",
                        retryable=True,
                        details={"http_status": exc.code},
                        raw=raw_body,
                    )

                if exc.code in {500, 502, 503, 504} and attempt < attempts - 1:
                    continue

                if exc.code >= 500:
                    return self._error_response(
                        request,
                        ProviderErrorCode.PROVIDER_UNAVAILABLE,
                        f"LM Studio returned HTTP {exc.code}.",
                        retryable=True,
                        details={"http_status": exc.code},
                        raw=raw_body,
                    )

                if self._looks_like_context_error(raw_body):
                    return self._error_response(
                        request,
                        ProviderErrorCode.CONTEXT_OVERFLOW,
                        "LM Studio rejected the request because the context is too large.",
                        retryable=False,
                        details={"http_status": exc.code},
                        raw=raw_body,
                    )

                return self._error_response(
                    request,
                    ProviderErrorCode.UNKNOWN,
                    f"LM Studio returned HTTP {exc.code}.",
                    retryable=False,
                    details={"http_status": exc.code},
                    raw=raw_body,
                )

            except (TimeoutError, socket.timeout):
                if attempt < attempts - 1:
                    continue

                return self._error_response(
                    request,
                    ProviderErrorCode.TIMEOUT,
                    "LM Studio request timed out.",
                    retryable=True,
                )

            except urllib.error.URLError as exc:
                if attempt < attempts - 1:
                    continue

                return self._error_response(
                    request,
                    ProviderErrorCode.PROVIDER_UNAVAILABLE,
                    f"Unable to connect to LM Studio: {exc.reason}",
                    retryable=True,
                )

            except OSError as exc:
                if attempt < attempts - 1:
                    continue

                return self._error_response(
                    request,
                    ProviderErrorCode.PROVIDER_UNAVAILABLE,
                    f"Unable to connect to LM Studio: {exc}",
                    retryable=True,
                )

        return self._error_response(
            request,
            ProviderErrorCode.UNKNOWN,
            "LM Studio request failed after all retry attempts.",
            retryable=False,
        )

    def generate(
        self,
        prompt: str,
        routing: RoutingDecision,
        context: str = "",
    ) -> str:
        response = self.invoke(
            ProviderRequest(
                prompt=prompt,
                routing=routing,
                context=context,
            )
        )
        return response.content if response.ok else ""

    def generate_structured_output(
        self,
        prompt: str,
        routing: RoutingDecision,
        schema_name: str,
        context: str = "",
    ) -> dict[str, Any]:
        response = self.invoke(
            ProviderRequest(
                prompt=prompt,
                routing=routing,
                context=context,
                schema_name=schema_name,
            )
        )

        if not response.ok:
            return {}

        if response.structured_content:
            return response.structured_content

        try:
            parsed = json.loads(response.content)
        except (TypeError, json.JSONDecodeError):
            return {}

        return parsed if isinstance(parsed, dict) else {}

    def stream_response(
        self,
        prompt: str,
        routing: RoutingDecision,
        context: str = "",
    ) -> Iterable[str]:
        response = self.invoke(
            ProviderRequest(
                prompt=prompt,
                routing=routing,
                context=context,
            )
        )

        if response.ok:
            yield response.content
        elif response.error:
            yield f"Provider error [{response.error.code.value}]: {response.error.message}"

    def _build_messages(self, request: ProviderRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a local AI coding assistant. "
                    "Provide accurate, practical software engineering answers. "
                    "When asked for code, prefer complete and executable code."
                ),
            }
        ]

        if request.context.strip():
            messages.append(
                {
                    "role": "system",
                    "content": f"Repository/context information:\n{request.context}",
                }
            )

        messages.append(
            {
                "role": "user",
                "content": request.prompt,
            }
        )

        return messages

    def _post(self, url: str, body: bytes) -> tuple[int, str]:
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=self.timeout_seconds,
        ) as response:
            return response.status, response.read().decode("utf-8")

    def _parse_response(
        self,
        request: ProviderRequest,
        status: int,
        raw_body: str,
    ) -> ProviderResponse:
        if status < 200 or status >= 300:
            return self._error_response(
                request,
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                f"LM Studio returned HTTP {status}.",
                retryable=True,
                details={"http_status": status},
                raw=raw_body,
            )

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return self._error_response(
                request,
                ProviderErrorCode.MALFORMED_OUTPUT,
                "LM Studio returned invalid JSON.",
                retryable=False,
                raw=raw_body,
            )

        choices = payload.get("choices")

        if not isinstance(choices, list) or not choices:
            return self._error_response(
                request,
                ProviderErrorCode.MALFORMED_OUTPUT,
                "LM Studio response does not contain choices.",
                retryable=False,
                raw=raw_body,
            )

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if not isinstance(content, str) or not content.strip():
            return self._error_response(
                request,
                ProviderErrorCode.MALFORMED_OUTPUT,
                "LM Studio returned an empty response.",
                retryable=False,
                raw=raw_body,
            )

        usage_payload = payload.get("usage") or {}

        usage = ProviderUsage(
            prompt_tokens=int(usage_payload.get("prompt_tokens", 0) or 0),
            completion_tokens=int(
                usage_payload.get("completion_tokens", 0) or 0
            ),
            total_tokens=int(usage_payload.get("total_tokens", 0) or 0),
        )

        structured_content: dict[str, Any] = {}

        if request.schema_name:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    structured_content = parsed
            except json.JSONDecodeError:
                return self._error_response(
                    request,
                    ProviderErrorCode.MALFORMED_OUTPUT,
                    "LM Studio returned non-JSON content for structured output.",
                    retryable=False,
                    raw=raw_body,
                )

        return ProviderResponse(
            ok=True,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            content=content,
            structured_content=structured_content,
            usage=usage,
            raw=raw_body,
        )

    def _error_response(
        self,
        request: ProviderRequest,
        code: ProviderErrorCode,
        message: str,
        *,
        retryable: bool,
        details: dict[str, Any] | None = None,
        raw: str = "",
    ) -> ProviderResponse:
        return ProviderResponse(
            ok=False,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            error=ProviderError(
                code=code,
                message=message,
                retryable=retryable,
                details=details or {},
            ),
            raw=raw,
        )

    @staticmethod
    def _read_error_body(exc: urllib.error.HTTPError) -> str:
        try:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _looks_like_context_error(raw_body: str) -> bool:
        text = raw_body.lower()
        keywords = (
            "context",
            "token",
            "maximum sequence length",
            "too long",
            "prompt is too long",
        )
        return any(keyword in text for keyword in keywords)