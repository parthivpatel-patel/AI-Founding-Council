"""Gemini adapter for generateContent.

Verified against the Gemini structured-output REST example:
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

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
from app.providers.http import UrllibTransport, monotonic_ms, post_for_model, require_model

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"


class GeminiProvider:
    name = "gemini"

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
    def from_env(cls) -> GeminiProvider:
        key, model, authorized, timeout = provider_settings("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_API_AUTHORIZED")
        return cls(api_key=key, model=model, authorized=authorized, timeout_seconds=timeout)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self._ensure_ready()
        model = require_model(self._model)
        started = time.perf_counter()
        body = {
            "systemInstruction": {"parts": [{"text": request.instructions}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_input}]}],
            "generationConfig": {
                "responseFormat": {
                    "text": {
                        "mimeType": "application/json",
                        "schema": _without_additional_properties(request.json_schema),
                    }
                }
            },
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}
        url = f"{_API_ROOT}{quote(model, safe='')}:generateContent"
        try:
            payload, _headers = post_for_model(
                transport=self._transport,
                url=url,
                headers=headers,
                body=body,
                timeout=self._timeout,
                sleep=self._sleep,
                secret=self._api_key,
            )
        except ProviderError as exc:
            exc.usage = self._usage(request, started, False, "request_failed", model)
            raise
        text = _candidate_text(payload)
        response_model = payload.get("modelVersion") if isinstance(payload.get("modelVersion"), str) else model
        input_tokens, output_tokens = _usage_tokens(payload)
        if not text.strip():
            usage = self._usage(request, started, False, "empty_response", response_model, input_tokens, output_tokens)
            raise MalformedResponseError("Gemini response contained no text", usage)
        usage = self._usage(request, started, True, "", response_model, input_tokens, output_tokens)
        response_id = payload.get("responseId") if isinstance(payload.get("responseId"), str) else None
        return GenerationResult(text=text, model=response_model, provider=self.name, response_id=response_id, usage=usage)

    def _ensure_ready(self) -> None:
        if not self._api_key:
            raise ProviderConfigError("GEMINI_API_KEY is not set")
        if not self._model:
            raise ProviderConfigError("GEMINI_MODEL is not set. Choose a model after checking current price and quota.")
        if not self._authorized:
            raise AuthorizationRequired("Set GEMINI_API_AUTHORIZED=1 after the CEO authorizes Gemini. No request was sent.")

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


def _without_additional_properties(value: Mapping[str, Any] | list[Any] | object) -> Any:
    if isinstance(value, Mapping):
        return {key: _without_additional_properties(item) for key, item in value.items() if key != "additionalProperties"}
    if isinstance(value, list):
        return [_without_additional_properties(item) for item in value]
    return value


def _candidate_text(payload: Mapping[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ""
    parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        blocks = content.get("parts")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if isinstance(block, dict) and block.get("thought") is not True and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "".join(parts)


def _usage_tokens(payload: Mapping[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usageMetadata")
    if not isinstance(usage, dict):
        return None, None
    return _int_or_none(usage.get("promptTokenCount")), _int_or_none(usage.get("candidatesTokenCount"))


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
