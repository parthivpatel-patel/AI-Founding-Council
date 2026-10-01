"""NVIDIA NIM adapter for POST /v1/chat/completions.

Verified against the NVIDIA API catalog:
https://integrate.api.nvidia.com/v1/chat/completions
https://docs.api.nvidia.com/nim/reference/llm-apis
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.config import provider_settings
from app.providers.base import (
    AuthorizationRequired,
    GenerationRequest,
    GenerationResult,
    MalformedResponseError,
    ProviderConfigError,
    ProviderError,
    UsageRecord,
)
from app.providers.http import (
    UrllibTransport,
    monotonic_ms,
    post_for_model,
    require_model,
    schema_instruction,
)

CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_MAX_TOKENS = 2048


class NvidiaProvider:
    name = "nvidia"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        authorized: bool,
        timeout_seconds: float = 25.0,
        transport: UrllibTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._authorized = authorized
        self._timeout = timeout_seconds
        self._transport = transport or UrllibTransport()
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> NvidiaProvider:
        key, model, authorized, timeout = provider_settings("NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_API_AUTHORIZED")
        return cls(api_key=key, model=model, authorized=authorized, timeout_seconds=timeout)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self._ensure_ready()
        model = require_model(self._model, allow_slash=True)
        started = time.perf_counter()
        body = {
            "model": model,
            "stream": False,
            "max_tokens": _MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": request.instructions + "\n\n" + schema_instruction(request.json_schema)},
                {"role": "user", "content": request.user_input},
            ],
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}
        try:
            payload, _headers = post_for_model(
                transport=self._transport,
                url=CHAT_URL,
                headers=headers,
                body=body,
                timeout=self._timeout,
                sleep=self._sleep,
                secret=self._api_key,
            )
        except ProviderError as exc:
            exc.usage = self._usage(request, started, False, "request_failed", model)
            raise
        text = _choice_text(payload)
        response_model = payload.get("model") if isinstance(payload.get("model"), str) else model
        input_tokens, output_tokens = _usage_tokens(payload)
        if not text.strip():
            usage = self._usage(request, started, False, "empty_response", response_model, input_tokens, output_tokens)
            raise MalformedResponseError("NVIDIA response contained no message text", usage)
        usage = self._usage(request, started, True, "", response_model, input_tokens, output_tokens)
        response_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        return GenerationResult(text=text, model=response_model, provider=self.name, response_id=response_id, usage=usage)

    def _ensure_ready(self) -> None:
        if not self._api_key:
            raise ProviderConfigError("NVIDIA_API_KEY is not set")
        if not self._model:
            raise ProviderConfigError("NVIDIA_MODEL is not set. Choose a model after checking current price and quota.")
        if not self._authorized:
            raise AuthorizationRequired("Set NVIDIA_API_AUTHORIZED=1 after the CEO authorizes NVIDIA. No request was sent.")

    def _usage(
        self,
        request: GenerationRequest,
        started: float,
        success: bool,
        error: str,
        model: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> UsageRecord:
        return UsageRecord(
            provider=self.name,
            model=model,
            task=request.task,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=None,
            latency_ms=monotonic_ms(started),
            success=success,
            reason=request.reason,
            error=error or None,
        )


def _choice_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [block.get("text", "") for block in content if isinstance(block, dict) and isinstance(block.get("text"), str)]
        return "".join(parts)
    return ""


def _usage_tokens(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    return _int_or_none(usage.get("prompt_tokens")), _int_or_none(usage.get("completion_tokens"))


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
