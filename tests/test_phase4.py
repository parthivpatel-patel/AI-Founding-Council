"""Phase 4 cross-examination and dispute detection. No live network calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.council.debate import examine
from app.council.independent import IndependentResult
from app.providers.base import GenerationRequest, GenerationResult, UsageRecord
from app.providers.router import ModelRouter
from app.schemas.debate import CrossExamination, Disagreement, detect_disputes
from app.schemas.messages import parse_agent_analysis
from test_phase2 import analysis_payload


def _analysis(thesis: str):
    payload = analysis_payload()
    payload["thesis"] = thesis
    return parse_agent_analysis(payload)


def _round(role: str, task: str, thesis: str, *, available: bool = True) -> IndependentResult:
    analysis = _analysis(thesis) if available else None
    detail = f"Thesis: {thesis}" if available else "CURSOR_API_KEY is not set"
    return IndependentResult(role, task, available, detail, None, analysis)


class _CrossProvider:
    def __init__(self, disagreements: list[dict[str, str]] | None = None) -> None:
        self.requests: list[GenerationRequest] = []
        self._disagreements = disagreements if disagreements is not None else [
            {
                "claim": "Customers will pay.",
                "sides": "one side asserts payment",
                "why": "No payment was observed.",
            }
        ]

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        body = {
            "agreements": ["The buyer is unknown."],
            "disagreements": self._disagreements,
            "unsupported_claims": ["A price was assumed."],
            "missing_evidence": ["A customer interview."],
            "contradictory_assumptions": ["Demand exists."],
            "overlooked_risks": ["The founder cannot reach the buyer."],
            "new_questions": ["Who pays?"],
        }
        usage = UsageRecord(
            provider="fake",
            model="fake",
            task=request.task,
            timestamp="2026-10-01T00:00:00+00:00",
            input_tokens=2,
            output_tokens=2,
            estimated_cost_usd=None,
            latency_ms=1,
            success=True,
            reason=request.reason,
            error=None,
        )
        return GenerationResult(text=json.dumps(body), model="fake", provider="fake", response_id=None, usage=usage)


class DisputeTests(unittest.TestCase):
    def test_same_claim_is_one_unverified_dispute(self) -> None:
        item = Disagreement("Customers will pay.", "sides", "No payment.")
        other = Disagreement("customers   will pay.", "other sides", "Still no payment.")
        disputes = detect_disputes(
            [
                ("strategist", CrossExamination((), (item,), (), (), (), (), ())),
                ("red_team", CrossExamination((), (other,), (), (), (), (), ())),
            ]
        )
        self.assertEqual(len(disputes), 1)
        self.assertEqual(disputes[0].dispute_id, "DISPUTE-001")
        self.assertEqual(disputes[0].status, "UNVERIFIED")
        self.assertEqual(disputes[0].raised_by, ("strategist", "red_team"))
        self.assertEqual(disputes[0].required_action, "Research required.")

    def test_no_stated_disagreement_creates_no_dispute(self) -> None:
        review = CrossExamination(("They agree the buyer is unknown.",), (), (), (), (), (), ())
        self.assertEqual(detect_disputes([("researcher", review)]), [])


class CrossExamTests(unittest.TestCase):
    def test_cross_exam_sees_round1_only_and_skips_unavailable_agents(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / "company").mkdir()
        (root / "company" / "COMPANY_STATE.md").write_text("Capital: $1,000\n", encoding="utf-8")
        strategist = _CrossProvider()
        researcher = _CrossProvider()
        cto = _CrossProvider()
        router = ModelRouter({"openai": strategist, "gemini": researcher, "cursor": cto})
        round1 = [
            _round("strategist", "strategy", "STRATEGIST_TOKEN"),
            _round("researcher", "research", "RESEARCH_TOKEN"),
            _round("cto", "cto", "CTO_TOKEN", available=False),
        ]
        outcome = examine("What should we investigate next?", round1, router=router, root=root)
        self.assertEqual(len(strategist.requests), 1)
        self.assertEqual(len(researcher.requests), 1)
        self.assertEqual(cto.requests, [])
        strategist_input = strategist.requests[0].user_input
        self.assertIn("Thesis: RESEARCH_TOKEN", strategist_input)
        self.assertIn("AGENT_UNAVAILABLE", strategist_input)
        self.assertIn("Agreement among models is not evidence.", strategist_input)
        self.assertNotIn("Customers will pay.", strategist_input)
        self.assertEqual(len(outcome.disputes), 1)
        self.assertEqual(outcome.disputes[0].status, "UNVERIFIED")
        self.assertEqual(outcome.disputes[0].raised_by, ("strategist", "researcher"))
        saved = json.loads(outcome.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["note"], "Model agreement is not evidence.")
        self.assertIn("cto", saved["unavailable_round1"])

    def test_cto_defaults_to_cursor(self) -> None:
        sentinel = object()
        self.assertIs(ModelRouter({"cursor": sentinel}).select("cto"), sentinel)


if __name__ == "__main__":
    unittest.main()
