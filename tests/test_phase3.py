"""Phase 3 provider adapters and independent round. No live network calls."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

from app.council.independent import run_independent_round
from app.providers.anthropic import MESSAGES_URL, AnthropicProvider
from app.providers.base import AuthorizationRequired, GenerationRequest, GenerationResult, UsageRecord
from app.providers.cursor import CursorProvider
from app.providers.gemini import GeminiProvider
from app.providers.nvidia import CHAT_URL, NvidiaProvider
from app.providers.router import ModelRouter
from app.providers.xai import RESPONSES_URL, XAIProvider
from test_phase2 import analysis_payload

REQUEST = GenerationRequest(
    task="research",
    instructions="role rules",
    user_input="company state and question",
    reason="test",
    schema_name="agent_analysis",
    json_schema={"type": "object", "additionalProperties": False, "properties": {"thesis": {"type": "string"}}},
)


class ScriptedTransport:
    def __init__(self, responses: list[tuple[int, dict[str, Any], dict[str, str]]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post_json(self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float):
        self.calls.append({"url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        if not self.responses:
            raise AssertionError("unexpected provider call")
        return self.responses.pop(0)


def _provider(cls, transport, **kwargs):
    return cls(
        api_key="test-key-not-real",
        model=kwargs.pop("model", "configured-model"),
        authorized=True,
        timeout_seconds=5,
        transport=transport,
        sleep=lambda _seconds: None,
        **kwargs,
    )


class AdapterShapeTests(unittest.TestCase):
    def test_anthropic_messages_request(self) -> None:
        transport = ScriptedTransport(
            [(200, {"id": "msg_test", "model": "configured-model", "content": [{"type": "text", "text": "{}"}], "usage": {"input_tokens": 3, "output_tokens": 4}}, {})]
        )
        result = _provider(AnthropicProvider, transport).generate(REQUEST)
        call = transport.calls[0]
        self.assertEqual(call["url"], MESSAGES_URL)
        self.assertEqual(call["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(call["headers"]["x-api-key"], "test-key-not-real")
        self.assertEqual(call["body"]["max_tokens"], 2048)
        self.assertEqual(call["body"]["messages"][0]["role"], "user")
        self.assertNotIn("thinking", call["body"])
        self.assertEqual(result.usage.input_tokens, 3)
        self.assertIsNone(result.usage.estimated_cost_usd)

    def test_gemini_generate_content_request(self) -> None:
        transport = ScriptedTransport(
            [
                (
                    200,
                    {
                        "responseId": "resp_g",
                        "modelVersion": "configured-model",
                        "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 6},
                    },
                    {},
                )
            ]
        )
        result = _provider(GeminiProvider, transport).generate(REQUEST)
        call = transport.calls[0]
        self.assertEqual(
            call["url"],
            "https://generativelanguage.googleapis.com/v1beta/models/configured-model:generateContent",
        )
        self.assertEqual(call["headers"]["x-goog-api-key"], "test-key-not-real")
        schema = call["body"]["generationConfig"]["responseFormat"]["text"]["schema"]
        self.assertEqual(call["body"]["generationConfig"]["responseFormat"]["text"]["mimeType"], "application/json")
        self.assertNotIn("additionalProperties", schema)
        self.assertEqual(result.usage.output_tokens, 6)

    def test_xai_responses_request_does_not_store(self) -> None:
        transport = ScriptedTransport(
            [
                (
                    200,
                    {
                        "id": "resp_x",
                        "model": "configured-model",
                        "output": [
                            {"type": "reasoning"},
                            {"type": "message", "content": [{"type": "output_text", "text": "{}"}]},
                        ],
                        "usage": {"input_tokens": 7, "output_tokens": 8},
                    },
                    {},
                )
            ]
        )
        result = _provider(XAIProvider, transport).generate(REQUEST)
        body = transport.calls[0]["body"]
        self.assertEqual(transport.calls[0]["url"], RESPONSES_URL)
        self.assertFalse(body["store"])
        self.assertEqual(body["input"][0]["role"], "system")
        self.assertEqual(result.text, "{}")

    def test_nvidia_chat_request(self) -> None:
        transport = ScriptedTransport(
            [
                (
                    200,
                    {
                        "id": "chat_n",
                        "model": "nvidia/example",
                        "choices": [{"message": {"content": "{}"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
                    },
                    {},
                )
            ]
        )
        result = _provider(NvidiaProvider, transport, model="nvidia/example").generate(REQUEST)
        body = transport.calls[0]["body"]
        self.assertEqual(transport.calls[0]["url"], CHAT_URL)
        self.assertFalse(body["stream"])
        self.assertEqual(body["response_format"]["type"], "json_object")
        self.assertEqual(result.usage.input_tokens, 1)
        self.assertNotIn("test-key-not-real", result.text)

    def test_cursor_authorization_does_not_start_an_agent(self) -> None:
        calls: list[str] = []

        class Runner:
            def complete(self, **kwargs):
                calls.append("called")
                return "{}"

        provider = CursorProvider(
            api_key="test-key-not-real",
            model="composer-test",
            authorized=False,
            cwd=Path("."),
            runner=Runner(),
        )
        with self.assertRaises(AuthorizationRequired):
            provider.generate(REQUEST)
        self.assertEqual(calls, [])

    def test_blocked_provider_makes_no_http_call(self) -> None:
        transport = ScriptedTransport([])
        provider = AnthropicProvider(
            api_key="test-key-not-real",
            model="configured-model",
            authorized=False,
            transport=transport,
        )
        with self.assertRaises(AuthorizationRequired):
            provider.generate(REQUEST)
        self.assertEqual(transport.calls, [])


class Gate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started: list[str] = []
        self._release = threading.Event()

    def enter(self, task: str) -> None:
        with self._lock:
            self.started.append(task)
            if len(self.started) == 4:
                self._release.set()
        if not self._release.wait(2):
            raise TimeoutError("independent calls did not overlap")


class IndependentRoundTests(unittest.TestCase):
    def test_four_agents_run_without_seeing_each_other(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / "company").mkdir()
        (root / "company" / "COMPANY_STATE.md").write_text("Capital: $1,000\n", encoding="utf-8")
        gate = Gate()
        providers = {}
        for name, token in (
            ("openai", "STRATEGIST_TOKEN"),
            ("gemini", "RESEARCH_TOKEN"),
            ("anthropic", "RED_TEAM_TOKEN"),
            ("xai", "CONTRARIAN_TOKEN"),
        ):
            providers[name] = _RecordingProvider(token, gate)
        router = ModelRouter(providers)
        results = run_independent_round("What should we investigate next?", router=router, root=root)
        self.assertEqual([item.role for item in results], ["strategist", "researcher", "red_team", "contrarian"])
        self.assertTrue(all(item.available for item in results))
        self.assertEqual(sorted(gate.started), ["contrarian", "red_team", "research", "strategy"])
        inputs = {provider.name: provider.requests[0].user_input for provider in providers.values()}
        for name, text in inputs.items():
            for token in ("STRATEGIST_TOKEN", "RESEARCH_TOKEN", "RED_TEAM_TOKEN", "CONTRARIAN_TOKEN"):
                self.assertNotIn(token, text)
        saved = list((root / "council_logs").glob("*/*.json"))
        self.assertEqual(len(saved), 4)
        blob = "\n".join(path.read_text(encoding="utf-8") for path in saved)
        self.assertNotIn("test-key", blob)
        self.assertIn("STRATEGIST_TOKEN", blob)


class _RecordingProvider:
    def __init__(self, token: str, gate: Gate) -> None:
        self.name = token
        self.token = token
        self.gate = gate
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.gate.enter(request.task)
        self.requests.append(request)
        payload = analysis_payload()
        payload["thesis"] = self.token
        usage = UsageRecord(
            provider=self.name,
            model="fake",
            task=request.task,
            timestamp="2026-10-01T00:00:00+00:00",
            input_tokens=1,
            output_tokens=1,
            estimated_cost_usd=None,
            latency_ms=1,
            success=True,
            reason=request.reason,
        )
        return GenerationResult(text=json.dumps(payload), model="fake", provider=self.name, response_id=None, usage=usage)


if __name__ == "__main__":
    unittest.main()
