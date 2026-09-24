from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .types import (
    ProviderAuditEvent,
    ProviderError,
    ProviderErrorCode,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
    RoutingDecision,
)


class LLMProvider(Protocol):
    def invoke(self, request: ProviderRequest) -> ProviderResponse: ...

    def generate(self, prompt: str, routing: RoutingDecision, context: str = "") -> str: ...

    def generate_structured_output(
        self,
        prompt: str,
        routing: RoutingDecision,
        schema_name: str,
        context: str = "",
    ) -> dict[str, Any]: ...

    def stream_response(self, prompt: str, routing: RoutingDecision, context: str = "") -> Iterable[str]: ...


@dataclass
class NullLLMProvider:
    name: str = "null-provider"

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        content = self.generate(prompt=request.prompt, routing=request.routing, context=request.context)
        return ProviderResponse(
            ok=True,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            content=content,
            usage=ProviderUsage(total_tokens=len(content.split())),
            raw=content,
        )

    def generate(self, prompt: str, routing: RoutingDecision, context: str = "") -> str:
        return (
            "LLM provider is not configured. "
            f"Recommended route: {routing.selected_model_label} ({routing.selected_model_key})."
        )

    def generate_structured_output(
        self,
        prompt: str,
        routing: RoutingDecision,
        schema_name: str,
        context: str = "",
    ) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": False,
            "schema": schema_name,
            "recommended_model": routing.selected_model_key,
            "note": "No runtime LLM integration enabled.",
        }

    def stream_response(self, prompt: str, routing: RoutingDecision, context: str = "") -> Iterable[str]:
        yield self.generate(prompt=prompt, routing=routing, context=context)


class LLMGateway:
    def __init__(self, default_provider: LLMProvider | None = None) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default_provider = default_provider or NullLLMProvider()
        self._audit_events: list[ProviderAuditEvent] = []

    def register_provider(self, model_key: str, provider: LLMProvider) -> None:
        self._providers[model_key] = provider

    def resolve_provider(self, model_key: str) -> LLMProvider:
        return self._providers.get(model_key, self._default_provider)

    def generate(self, prompt: str, routing: RoutingDecision, context: str = "") -> str:
        request = ProviderRequest(prompt=prompt, routing=routing, context=context)
        response = self.invoke(request)
        if response.ok:
            return response.content
        if response.error is not None:
            return f"Provider error [{response.error.code.value}]: {response.error.message}"
        return "Provider error: unknown"

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        provider = self.resolve_provider(request.routing.selected_model_key)
        response = provider.invoke(request)
        if response.ok:
            self._record_audit(
                event="provider_invoke",
                request=request,
                provider_name=response.provider_name,
                success=True,
            )
            return response

        if request.routing.fallback_model_key:
            fallback_provider = self.resolve_provider(request.routing.fallback_model_key)
            fallback_request = ProviderRequest(
                prompt=request.prompt,
                routing=RoutingDecision(
                    complexity=request.routing.complexity,
                    selected_model_key=request.routing.fallback_model_key,
                    selected_model_label=request.routing.selected_model_label,
                    context_tokens=request.routing.context_tokens,
                    local_only=request.routing.local_only,
                    reason=request.routing.reason,
                    fallback_model_key="",
                ),
                context=request.context,
                schema_name=request.schema_name,
                request_id=request.request_id,
            )
            fallback_response = fallback_provider.invoke(fallback_request)
            self._record_audit(
                event="provider_fallback",
                request=request,
                provider_name=response.provider_name,
                success=fallback_response.ok,
                error_code=response.error.code.value if response.error else "",
                fallback_used=True,
                fallback_model_key=request.routing.fallback_model_key,
            )
            if fallback_response.ok:
                return fallback_response

        self._record_audit(
            event="provider_invoke",
            request=request,
            provider_name=response.provider_name,
            success=False,
            error_code=response.error.code.value if response.error else "",
        )
        return response

    def generate_structured_output(
        self,
        prompt: str,
        routing: RoutingDecision,
        schema_name: str,
        context: str = "",
    ) -> dict[str, Any]:
        request = ProviderRequest(prompt=prompt, routing=routing, context=context, schema_name=schema_name)
        response = self.invoke(request)
        if response.ok:
            if response.structured_content:
                return response.structured_content
            if response.content:
                try:
                    parsed = json.loads(response.content)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass
        return {
            "ok": False,
            "error": response.error.code.value if response.error else ProviderErrorCode.UNKNOWN.value,
            "message": response.error.message if response.error else "Failed to produce structured output",
            "schema": schema_name,
        }

    def stream_response(self, prompt: str, routing: RoutingDecision, context: str = "") -> Iterable[str]:
        response = self.invoke(ProviderRequest(prompt=prompt, routing=routing, context=context))
        if response.ok:
            yield response.content
            return
        if response.error:
            yield f"Provider error [{response.error.code.value}]: {response.error.message}"
            return
        yield "Provider error: unknown"

    def audit_events(self) -> list[ProviderAuditEvent]:
        return list(self._audit_events)

    def clear_audit_events(self) -> None:
        self._audit_events.clear()

    def registered_model_keys(self) -> list[str]:
        return sorted(list(self._providers.keys()))

    def provider_name_for(self, model_key: str) -> str:
        provider = self.resolve_provider(model_key)
        return getattr(provider, "name", provider.__class__.__name__)

    def _record_audit(
        self,
        *,
        event: str,
        request: ProviderRequest,
        provider_name: str,
        success: bool,
        error_code: str = "",
        fallback_used: bool = False,
        fallback_model_key: str = "",
    ) -> None:
        self._audit_events.append(
            ProviderAuditEvent(
                event=event,
                request_id=request.request_id,
                primary_model_key=request.routing.selected_model_key,
                provider_name=provider_name,
                success=success,
                error_code=error_code,
                fallback_used=fallback_used,
                fallback_model_key=fallback_model_key,
            )
        )


@dataclass
class MockLLMProvider:
    name: str = "mock-provider"
    mode: str = "success"

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        fixtures = {
            "success": self._success,
            "malformed_json": self._malformed_json,
            "rate_limit": self._rate_limit,
            "timeout": self._timeout,
            "context_overflow": self._context_overflow,
        }
        handler = fixtures.get(self.mode, self._unknown)
        return handler(request)

    def generate(self, prompt: str, routing: RoutingDecision, context: str = "") -> str:
        response = self.invoke(ProviderRequest(prompt=prompt, routing=routing, context=context))
        return response.content if response.ok else ""

    def generate_structured_output(
        self,
        prompt: str,
        routing: RoutingDecision,
        schema_name: str,
        context: str = "",
    ) -> dict[str, Any]:
        response = self.invoke(
            ProviderRequest(prompt=prompt, routing=routing, context=context, schema_name=schema_name)
        )
        return response.structured_content

    def stream_response(self, prompt: str, routing: RoutingDecision, context: str = "") -> Iterable[str]:
        response = self.invoke(ProviderRequest(prompt=prompt, routing=routing, context=context))
        if response.ok:
            yield response.content
        else:
            yield response.error.message if response.error else "unknown"

    def _success(self, request: ProviderRequest) -> ProviderResponse:
        content = "{\"result\": \"ok\"}"
        return ProviderResponse(
            ok=True,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            content=content,
            structured_content={"result": "ok"},
            usage=ProviderUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
            raw=content,
        )

    def _malformed_json(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            ok=False,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            error=ProviderError(
                code=ProviderErrorCode.MALFORMED_OUTPUT,
                message="Malformed JSON output",
                retryable=False,
            ),
            raw="{invalid_json",
        )

    def _rate_limit(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            ok=False,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            error=ProviderError(
                code=ProviderErrorCode.RATE_LIMITED,
                message="Rate limit exceeded",
                retryable=True,
            ),
        )

    def _timeout(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            ok=False,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            error=ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="Provider timeout",
                retryable=True,
            ),
        )

    def _context_overflow(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            ok=False,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            error=ProviderError(
                code=ProviderErrorCode.CONTEXT_OVERFLOW,
                message="Context token limit exceeded",
                retryable=False,
                details={"max_context_tokens": request.routing.context_tokens},
            ),
        )

    def _unknown(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            ok=False,
            model_key=request.routing.selected_model_key,
            provider_name=self.name,
            error=ProviderError(
                code=ProviderErrorCode.UNKNOWN,
                message=f"Unknown fixture mode: {self.mode}",
                retryable=False,
            ),
        )
