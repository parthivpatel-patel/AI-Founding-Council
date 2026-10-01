"""Cursor adapter.

Cursor is not a chat-completions endpoint. The official Python SDK runs an agent
with Agent.prompt. A local agent can use tools, so this adapter is off until
CURSOR_API_AUTHORIZED=1 and the prompt forbids file changes. The SDK is imported
only when a live call is authorized.

Docs: https://cursor.com/docs/sdk/python
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

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
from app.providers.http import monotonic_ms, require_model, schema_instruction


class CursorRunner:
    def complete(self, *, api_key: str, model: str, prompt: str, cwd: str) -> str:
        try:
            from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
        except ImportError as exc:
            raise ProviderConfigError("cursor-sdk is not installed. Install it before authorizing Cursor.") from exc
        result = Agent.prompt(
            prompt,
            AgentOptions(api_key=api_key, model=model, local=LocalAgentOptions(cwd=cwd)),
        )
        status = getattr(result, "status", "")
        text = getattr(result, "result", "")
        if status == "error":
            raise ProviderError("Cursor agent run failed")
        if not isinstance(text, str):
            return ""
        return text


class CursorProvider:
    name = "cursor"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        authorized: bool,
        cwd: Path,
        runner: CursorRunner | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._authorized = authorized
        self._cwd = cwd
        self._runner = runner or CursorRunner()
        self._clock = clock

    @classmethod
    def from_env(cls, cwd: Path) -> CursorProvider:
        key, model, authorized, _timeout = provider_settings("CURSOR_API_KEY", "CURSOR_MODEL", "CURSOR_API_AUTHORIZED")
        return cls(api_key=key, model=model, authorized=authorized, cwd=cwd)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self._ensure_ready()
        model = require_model(self._model)
        started = self._clock()
        prompt = (
            "Do not read, edit, create, or delete files. Do not run commands. "
            "Answer with JSON only.\n\n"
            + request.instructions
            + "\n\n"
            + schema_instruction(request.json_schema)
            + "\n\n"
            + request.user_input
        )
        try:
            text = self._runner.complete(api_key=self._api_key, model=model, prompt=prompt, cwd=str(self._cwd))
        except ProviderError as exc:
            exc.usage = self._usage(request, started, False, "request_failed", model)
            raise
        except Exception as exc:
            usage = self._usage(request, started, False, "request_failed", model)
            raise ProviderError("Cursor request failed", usage) from exc
        if not text.strip():
            usage = self._usage(request, started, False, "empty_response", model)
            raise MalformedResponseError("Cursor response contained no text", usage)
        usage = self._usage(request, started, True, "", model)
        return GenerationResult(text=text, model=model, provider=self.name, response_id=None, usage=usage)

    def _ensure_ready(self) -> None:
        if not self._api_key:
            raise ProviderConfigError("CURSOR_API_KEY is not set")
        if not self._model:
            raise ProviderConfigError("CURSOR_MODEL is not set. Choose a model after checking current price and quota.")
        if not self._authorized:
            raise AuthorizationRequired("Set CURSOR_API_AUTHORIZED=1 after the CEO authorizes Cursor. No agent was started.")

    def _usage(self, request: GenerationRequest, started: float, success: bool, error: str, model: str) -> UsageRecord:
        return UsageRecord(
            provider=self.name,
            model=model,
            task=request.task,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
            latency_ms=monotonic_ms(started) if started else 0.0,
            success=success,
            reason=request.reason,
            error=error or None,
        )
