"""OpenAI adapter for POST /v1/responses.

Verified against the OpenAI text generation and structured output guides:
https://developers.openai.com/api/docs/guides/text
https://developers.openai.com/api/docs/guides/structured-outputs

Token fields match the official ResponseUsage model:
input_tokens, output_tokens, output_tokens_details.reasoning_tokens.
Price is not estimated here. No price table has been verified.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from app.config import env_flag, env_value
from app.providers.base import (
    AuthorizationRequired,
    GenerationRequest,
    GenerationResult,
    MalformedResponseError,
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExhaustedError,
    RateLimitError,
    UsageRecord,
)

RESPONSES_URL = "https://api.openai.com/v1/responses"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 2
_MAX_RETRY_WAIT_SECONDS = 1.0


class HttpTransport:
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout: float,
    ) -> tuple[int, dict[str, Any], Mapping[str, str]]:
        raise NotImplementedError


class UrllibTransport(HttpTransport):
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout: float,
    ) -> tuple[int, dict[str, Any], Mapping[str, str]]:
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return response.status, _decode_json(raw), dict(response.headers)
        except TimeoutError as exc:
            raise ProviderTimeout("OpenAI request timed out") from exc
        except urllib.error.HTTPError as exc:
            return exc.code, _decode_json(exc.read()), dict(exc.headers)
        except urllib.error.URLError as exc:
            raise ProviderUnavailable("OpenAI could not be reached") from exc


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        authorized: bool,
        timeout_seconds: float = 25.0,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._authorized = authorized
        self._timeout = timeout_seconds
        self._transport = transport or UrllibTransport()
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> OpenAIProvider:
        timeout_raw = env_value("OPENAI_TIMEOUT_SECONDS") or "25"
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ProviderConfigError("OPENAI_TIMEOUT_SECONDS must be a number") from exc
        timeout = min(max(timeout, 1.0), 60.0)
        return cls(
            api_key=env_value("OPENAI_API_KEY"),
            model=env_value("OPENAI_MODEL"),
            authorized=env_flag("OPENAI_API_AUTHORIZED"),
            timeout_seconds=timeout,
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self._ensure_ready()
        started = time.perf_counter()
        body = {
            "model": self._model,
            "instructions": request.instructions,
            "input": request.user_input,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.json_schema,
                }
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        status = 0
        payload: dict[str, Any] = {}
        response_headers: Mapping[str, str] = {}
        for attempt in range(_MAX_ATTEMPTS):
            try:
                status, payload, response_headers = self._transport.post_json(
                    RESPONSES_URL,
                    headers,
                    body,
                    self._timeout,
                )
            except ProviderTimeout as exc:
                exc.usage = self._usage(request, started, False, "timeout")
                raise
            except ProviderUnavailable as exc:
                if attempt + 1 < _MAX_ATTEMPTS:
                    self._sleep(0.2)
                    continue
                exc.usage = self._usage(request, started, False, "unavailable")
                raise
            if status == 200:
                break
            error_code, error_message = _error_parts(payload)
            public_message = _redact(error_message or f"OpenAI HTTP {status}", self._api_key)
            if error_code == "insufficient_quota":
                usage = self._usage(request, started, False, "quota_exhausted")
                raise QuotaExhaustedError(public_message, usage)
            retryable = status in _RETRYABLE_STATUS and attempt + 1 < _MAX_ATTEMPTS
            if retryable and error_code != "insufficient_quota":
                self._sleep(_retry_delay(response_headers))
                continue
            usage = self._usage(request, started, False, _failure_reason(status))
            raise _status_error(status, public_message, usage)
        else:
            usage = self._usage(request, started, False, "request_failed")
            raise ProviderUnavailable("OpenAI request failed", usage)

        text = _output_text(payload)
        response_model = payload.get("model") if isinstance(payload.get("model"), str) else self._model
        response_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        input_tokens, output_tokens = _token_counts(payload)
        if not text.strip():
            usage = self._usage(
                request,
                started,
                False,
                "empty_response",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=response_model,
            )
            raise MalformedResponseError("OpenAI response contained no output text", usage)
        usage = self._usage(
            request,
            started,
            True,
            "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=response_model,
        )
        return GenerationResult(
            text=text,
            model=response_model,
            provider=self.name,
            response_id=response_id,
            usage=usage,
        )

    def _ensure_ready(self) -> None:
        if not self._api_key:
            raise ProviderConfigError("OPENAI_API_KEY is not set")
        if not self._model:
            raise ProviderConfigError("OPENAI_MODEL is not set. Choose a model after checking current price and quota.")
        if not self._authorized:
            raise AuthorizationRequired(
                "Set OPENAI_API_AUTHORIZED=1 after the CEO authorizes this provider. No request was sent."
            )

    def _usage(
        self,
        request: GenerationRequest,
        started: float,
        success: bool,
        error: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
    ) -> UsageRecord:
        return UsageRecord(
            provider=self.name,
            model=model or self._model or "unset",
            task=request.task,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=None,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            success=success,
            reason=request.reason,
            error=error or None,
        )


def _decode_json(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _output_text(payload: Mapping[str, Any]) -> str:
    """Collect assistant text from the output array.

    Official guidance: do not assume the text is at output[0].
    """
    parts: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
    return "".join(parts)


def _token_counts(payload: Mapping[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    return _int_or_none(usage.get("input_tokens")), _int_or_none(usage.get("output_tokens"))


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _error_parts(payload: Mapping[str, Any]) -> tuple[str, str]:
    error = payload.get("error")
    if not isinstance(error, dict):
        return "", ""
    code = error.get("code")
    message = error.get("message")
    return (code if isinstance(code, str) else "", message if isinstance(message, str) else "")


def _status_error(status: int, message: str, usage: UsageRecord) -> ProviderError:
    if status in {401, 403}:
        return ProviderAuthError(message, usage)
    if status == 429:
        return RateLimitError(message, usage)
    if status in {408, 504}:
        return ProviderTimeout(message, usage)
    if status >= 500:
        return ProviderUnavailable(message, usage)
    return ProviderError(message, usage)


def _failure_reason(status: int) -> str:
    if status in {401, 403}:
        return "auth_failed"
    if status == 429:
        return "rate_limited"
    if status in {408, 504}:
        return "timeout"
    if status >= 500:
        return "unavailable"
    return "request_failed"


def _retry_delay(headers: Mapping[str, str]) -> float:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    try:
        delay = float(raw) if raw is not None else 0.2
    except (TypeError, ValueError):
        delay = 0.2
    return min(max(delay, 0.0), _MAX_RETRY_WAIT_SECONDS)


def _redact(message: str, secret: str) -> str:
    if secret:
        message = message.replace(secret, "[redacted]")
    return message[:300]
