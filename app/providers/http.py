"""Shared HTTP helper for provider adapters."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from app.providers.base import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExhaustedError,
    RateLimitError,
)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}
_MAX_ATTEMPTS = 2
_MAX_RETRY_WAIT_SECONDS = 1.0
_SIMPLE_MODEL = re.compile(r"^[A-Za-z0-9._-]+$")
_PATH_MODEL = re.compile(r"^[A-Za-z0-9._/-]+$")


class UrllibTransport:
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
                return response.status, _decode_json(response.read()), dict(response.headers)
        except TimeoutError as exc:
            raise ProviderTimeout("Provider request timed out") from exc
        except urllib.error.HTTPError as exc:
            return exc.code, _decode_json(exc.read()), dict(exc.headers)
        except urllib.error.URLError as exc:
            raise ProviderUnavailable("Provider could not be reached") from exc


def require_model(model: str, *, allow_slash: bool = False) -> str:
    cleaned = model.strip()
    pattern = _PATH_MODEL if allow_slash else _SIMPLE_MODEL
    if not cleaned or ".." in cleaned or pattern.fullmatch(cleaned) is None:
        raise ProviderConfigError("Model id is missing or not a plain model name")
    return cleaned


def post_for_model(
    *,
    transport: UrllibTransport,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    timeout: float,
    sleep: Callable[[float], None],
    secret: str,
) -> tuple[dict[str, Any], Mapping[str, str]]:
    response_headers: Mapping[str, str] = {}
    payload: dict[str, Any] = {}
    status = 0
    for attempt in range(_MAX_ATTEMPTS):
        try:
            status, payload, response_headers = transport.post_json(url, headers, body, timeout)
        except ProviderTimeout:
            raise
        except ProviderUnavailable:
            if attempt + 1 < _MAX_ATTEMPTS:
                sleep(0.2)
                continue
            raise
        if status == 200:
            return payload, response_headers
        code, message = _error_parts(payload)
        public = _redact(message or f"HTTP {status}", secret)
        if code in {"insufficient_quota", "billing_error"}:
            raise QuotaExhaustedError(public)
        if status in _RETRYABLE_STATUS and attempt + 1 < _MAX_ATTEMPTS:
            sleep(_retry_delay(response_headers))
            continue
        raise _status_error(status, public)
    raise ProviderUnavailable("Provider request failed")


def output_text(payload: Mapping[str, Any]) -> str:
    """Read Responses API text without assuming output[0] is the message."""
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


def schema_instruction(schema: Mapping[str, Any]) -> str:
    return "Return only one JSON object matching this schema, with no markdown:\n" + json.dumps(
        schema, separators=(",", ":")
    )


def _decode_json(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_parts(payload: Mapping[str, Any]) -> tuple[str, str]:
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code") or error.get("status") or error.get("type") or ""
        message = error.get("message") or ""
        return (code if isinstance(code, str) else str(code), message if isinstance(message, str) else "")
    if isinstance(error, str):
        return "", error
    return "", ""


def _status_error(status: int, message: str) -> ProviderError:
    if status in {401, 403}:
        return ProviderAuthError(message)
    if status == 429:
        return RateLimitError(message)
    if status in {408, 504}:
        return ProviderTimeout(message)
    if status >= 500:
        return ProviderUnavailable(message)
    return ProviderError(message)


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


def monotonic_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
