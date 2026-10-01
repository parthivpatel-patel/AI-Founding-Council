"""Provider-agnostic generation types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationRequest:
    task: str
    instructions: str
    user_input: str
    reason: str
    schema_name: str
    json_schema: dict[str, Any]


@dataclass(frozen=True)
class UsageRecord:
    provider: str
    model: str
    task: str
    timestamp: str
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    latency_ms: float
    success: bool
    reason: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "task": self.task,
            "timestamp": self.timestamp,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "reason": self.reason,
            "error": self.error,
        }


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    provider: str
    response_id: str | None
    usage: UsageRecord


class ModelProvider(Protocol):
    name: str

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Return model text. Implementations must not log secrets."""


class ProviderError(Exception):
    def __init__(self, message: str, usage: UsageRecord | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class ProviderConfigError(ProviderError):
    pass


class AuthorizationRequired(ProviderError):
    pass


class ProviderAuthError(ProviderError):
    pass


class RateLimitError(ProviderError):
    pass


class QuotaExhaustedError(ProviderError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class MalformedResponseError(ProviderError):
    pass
