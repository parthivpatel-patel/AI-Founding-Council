"""Phase 5 evidence resolution, red-team pass, and pending memo. No live calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.council.evidence import select_thesis
from app.council.independent import IndependentResult
from app.council.synthesis import conclude
from app.providers.base import AuthorizationRequired, GenerationRequest, GenerationResult, UsageRecord
from app.providers.router import ModelRouter
from app.schemas.debate import Dispute
from app.schemas.messages import parse_agent_analysis
from test_phase2 import analysis_payload


def _analysis(thesis: str, level: int, recommendation: str = "Talk to one buyer."):
    payload = analysis_payload()
    payload["thesis"] = thesis
    payload["evidence"] = [{"text": f"Evidence for {thesis}", "level": level}]
    payload["facts"] = [{"text": "Starting capital is recorded as $1,000.", "label": "FACT"}]
    payload["recommendation"] = recommendation
    return parse_agent_analysis(payload)


def _result(role: str, task: str, thesis: str, level: int, *, available: bool = True) -> IndependentResult:
    analysis = _analysis(thesis, level) if available else None
    return IndependentResult(role, task, available, thesis, None, analysis)


def _dispute() -> Dispute:
    return Dispute(
        dispute_id="DISPUTE-001",
        claim="Customers will pay.",
        raised_by=("strategist", "red_team"),
        sides="unresolved",
        why="No payment was observed.",
        status="UNVERIFIED",
        evidence="Insufficient.",
        required_action="Research required.",
    )


class _Recorder:
    def __init__(self, text: str | Exception) -> None:
        self.text = text
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        if isinstance(self.text, Exception):
            raise self.text
        usage = UsageRecord(
            provider="fake",
            model="fake",
            task=request.task,
            timestamp="2026-10-01T00:00:00+00:00",
            input_tokens=1,
            output_tokens=1,
            estimated_cost_usd=None,
            latency_ms=1,
            success=True,
            reason=request.reason,
            error=None,
        )
        return GenerationResult(text=self.text, model="fake", provider="fake", response_id=None, usage=usage)


def _root() -> Path:
    root = Path(tempfile.mkdtemp())
    company = root / "company"
    company.mkdir()
    (company / "COMPANY_STATE.md").write_text("Capital: $1,000\n", encoding="utf-8")
    (company / "DECISION_LOG.md").write_text("No decisions have been recorded.\n", encoding="utf-8")
    return root


_RESEARCH = json.dumps(
    {
        "items": [
            {
                "dispute_id": "DISPUTE-001",
                "still_unknown": "No buyer has paid.",
                "research_action": "Interview one buyer.",
            }
        ]
    }
)
_RED_TEAM = json.dumps(
    {
        "failure_mechanisms": ["The buyer may not exist."],
        "strongest_counterargument": "No payment was observed.",
        "kill_criteria": "No buyer will talk.",
        "residual_uncertainty": "Demand is unknown.",
    }
)


class DecisionTests(unittest.TestCase):
    def test_no_dispute_skips_research_and_leaves_the_memo_pending(self) -> None:
        root = _root()
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        before = (root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8")
        log_before = (root / "company" / "DECISION_LOG.md").read_text(encoding="utf-8")
        research = _Recorder(_RESEARCH)
        red_team = _Recorder(_RED_TEAM)
        router = ModelRouter({"gemini": research, "anthropic": red_team})
        round1 = [
            _result("strategist", "strategy", "STRATEGIST_THESIS", 16),
            _result("researcher", "research", "RESEARCH_THESIS", 1),
        ]
        packet = conclude("What next?", round1, [], router=router, root=root)
        self.assertEqual(research.requests, [])
        self.assertEqual(len(red_team.requests), 1)
        self.assertIn("THESIS UNDER TEST:\nSTRATEGIST_THESIS", red_team.requests[0].user_input)
        self.assertIn("Level 1 — Customer payment", packet.thesis.reason)
        self.assertIn("Agreement was not used.", packet.thesis.reason)
        self.assertEqual(packet.memo.ceo_decision, "PENDING")
        self.assertEqual(packet.memo.expected_cost, "Unverified. No spend is authorized.")
        saved = json.loads(packet.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["memo"]["ceo_decision"], "PENDING")
        self.assertNotIn("APPROVED", packet.path.read_text(encoding="utf-8"))
        self.assertEqual((root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8"), before)
        self.assertEqual((root / "company" / "DECISION_LOG.md").read_text(encoding="utf-8"), log_before)

    def test_disputes_get_one_research_call_and_stay_unverified(self) -> None:
        root = _root()
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        research = _Recorder(_RESEARCH)
        red_team = _Recorder(_RED_TEAM)
        router = ModelRouter({"gemini": research, "anthropic": red_team})
        packet = conclude(
            "What next?",
            [_result("strategist", "strategy", "STRATEGIST_THESIS", 16)],
            [_dispute()],
            router=router,
            root=root,
        )
        self.assertEqual(len(research.requests), 1)
        self.assertEqual(research.requests[0].schema_name, "evidence_resolution")
        self.assertIn("DISPUTE-001", research.requests[0].user_input)
        self.assertIn("Do not mark any dispute resolved.", research.requests[0].user_input)
        self.assertEqual(packet.resolutions[0].status, "UNVERIFIED")
        self.assertEqual(packet.resolutions[0].required_action, "Interview one buyer.")
        self.assertEqual(packet.memo.ceo_decision, "PENDING")
        self.assertEqual(len(red_team.requests), 1)

    def test_unavailable_red_team_still_writes_a_pending_memo(self) -> None:
        root = _root()
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        router = ModelRouter(
            {
                "gemini": _Recorder(_RESEARCH),
                "anthropic": _Recorder(AuthorizationRequired("ANTHROPIC_API_AUTHORIZED is not set")),
            }
        )
        packet = conclude(
            "What next?",
            [_result("researcher", "research", "RESEARCH_THESIS", 13, available=True)],
            [],
            router=router,
            root=root,
        )
        self.assertEqual(packet.thesis.role, "researcher")
        self.assertFalse(packet.red_team.available)
        self.assertIn("RED_TEAM_PASS_UNAVAILABLE", packet.memo.strongest_counterargument)
        self.assertEqual(packet.memo.ceo_decision, "PENDING")


if __name__ == "__main__":
    unittest.main()
