from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskComplexity(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


@dataclass(frozen=True)
class HardwareProfile:
    vram_gb: float = 8.0
    system_ram_gb: float = 12.0
    cpu: str = "Intel Core i7"


@dataclass(frozen=True)
class ModelProfile:
    key: str
    label: str
    estimated_vram_gb: float
    role: str
    local: bool


@dataclass(frozen=True)
class RoutingPolicy:
    preferred_context_tokens: int = 12000
    max_context_tokens: int = 16000
    allow_cloud_fallback: bool = False


@dataclass(frozen=True)
class RoutingDecision:
    complexity: TaskComplexity
    selected_model_key: str
    selected_model_label: str
    context_tokens: int
    local_only: bool
    reason: str
    fallback_model_key: str = ""


class ProviderErrorCode(str, Enum):
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    routing: RoutingDecision
    context: str = ""
    schema_name: str = ""
    request_id: str = ""


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ProviderError:
    code: ProviderErrorCode
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    ok: bool
    model_key: str
    provider_name: str
    content: str = ""
    structured_content: dict[str, Any] = field(default_factory=dict)
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    error: ProviderError | None = None
    raw: str = ""


@dataclass(frozen=True)
class ProviderAuditEvent:
    event: str
    request_id: str
    primary_model_key: str
    provider_name: str
    success: bool
    error_code: str = ""
    fallback_used: bool = False
    fallback_model_key: str = ""
