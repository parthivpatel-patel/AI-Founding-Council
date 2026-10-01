"""Phase 6 CEO recording. No model call and no invented company facts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.memory.decisions import record_ceo_decision

ROOT = Path(__file__).resolve().parents[1]


def _memo(decision: str = "PENDING") -> dict[str, object]:
    return {
        "memo": {
            "question": "What should we investigate next?",
            "current_state": "Stage 0. This memo does not update company state.",
            "what_we_know": "No claim was labeled FACT.",
            "what_we_dont_know": "Current problem",
            "strongest_evidence": "Level 16 — Founder assumption: nothing was observed.",
            "strongest_counterargument": "No customer was observed.",
            "key_assumptions": "Demand exists.",
            "critical_risks": "No distribution.",
            "council_disagreements": "No disagreement was detected. That is not validation.",
            "cheapest_experiment": "Talk to one buyer.",
            "expected_cost": "Unverified. No spend is authorized.",
            "expected_learning": "The question is still open.",
            "kill_criteria": "Stop if no buyer describes the pain.",
            "recommended_next_action": "Define the evidence that would change the thesis.",
            "ceo_decision": decision,
        },
        "note": "CEO decision is pending. Company state was not updated.",
    }


def _root() -> Path:
    root = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "company", root / "company")
    return root


def _write_memo(root: Path, decision: str = "PENDING") -> Path:
    directory = root / "council_logs" / "20261001T000000000000Z_decision"
    directory.mkdir(parents=True)
    path = directory / "ceo_decision.json"
    path.write_text(json.dumps(_memo(decision), indent=2), encoding="utf-8")
    return path


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    heading = ""
    body: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("## "):
            if heading:
                sections[heading] = "".join(body)
            heading = line.strip()
            body = []
        elif heading:
            body.append(line)
    if heading:
        sections[heading] = "".join(body)
    return sections


class DecisionRecordTests(unittest.TestCase):
    def test_approve_updates_only_the_decision_records(self) -> None:
        root = _root()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        before = (root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8")
        memo = _write_memo(root)
        recorded = record_ceo_decision(root, memo, "APPROVED", "I accept the next question, not a fact.")
        after = (root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8")
        log = (root / "company" / "DECISION_LOG.md").read_text(encoding="utf-8")
        self.assertEqual(recorded.decision_id, "DECISION-001")
        self.assertEqual(recorded.ceo_decision, "APPROVED")
        self.assertIn("DECISION-001", log)
        self.assertIn("I accept the next question, not a fact.", log)
        self.assertIn("does not authorize spending", log)
        self.assertIn("Cited evidence does not make the claim true.", log)
        self.assertNotIn("No decisions have been recorded.", log)
        saved = json.loads(recorded.record_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["ceo_decision"], "APPROVED")
        self.assertEqual(json.loads(memo.read_text(encoding="utf-8"))["memo"]["ceo_decision"], "PENDING")
        before_sections = _sections(before)
        after_sections = _sections(after)
        self.assertEqual(set(before_sections), set(after_sections))
        for heading, body in before_sections.items():
            if heading == "## Major Decisions":
                self.assertIn("DECISION-001", after_sections[heading])
                self.assertNotIn("None recorded.", after_sections[heading])
            else:
                self.assertEqual(after_sections[heading], body)
        self.assertIn("$0 until the CEO authorizes spending.", after)
        self.assertIn("## Current Problem\nUNKNOWN", after)

    def test_reject_and_a_second_record_is_refused(self) -> None:
        root = _root()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        memo = _write_memo(root)
        record_ceo_decision(root, memo, "REJECTED", "")
        log = (root / "company" / "DECISION_LOG.md").read_text(encoding="utf-8")
        state = (root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8")
        self.assertIn("REJECTED", log)
        self.assertIn("CEO reasoning, if provided: Not provided.", log)
        with self.assertRaises(ValueError):
            record_ceo_decision(root, memo, "APPROVED", "Changed my mind")
        self.assertEqual((root / "company" / "DECISION_LOG.md").read_text(encoding="utf-8"), log)
        self.assertEqual((root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8"), state)

    def test_a_settled_memo_and_an_outside_path_are_refused(self) -> None:
        root = _root()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        settled = _write_memo(root, "APPROVED")
        with self.assertRaises(ValueError):
            record_ceo_decision(root, settled, "APPROVED", "")
        outside = root / "ceo_decision.json"
        outside.write_text(json.dumps(_memo()), encoding="utf-8")
        with self.assertRaises(ValueError):
            record_ceo_decision(root, outside, "APPROVED", "")
        self.assertIn("None recorded.", (root / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8"))

    def test_cli_records_without_a_provider_call(self) -> None:
        root = _root()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        memo = _write_memo(root)
        env = os.environ.copy()
        env["COUNCIL_ROOT"] = str(root)
        completed = subprocess.run(
            [sys.executable, "-m", "app.main", "decide", str(memo), "approve", "Record this only."],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("CEO DECISION: APPROVED", completed.stdout)
        self.assertIn("Decision ID: DECISION-001", completed.stdout)
        self.assertIn("No spend was authorized.", completed.stdout)
        self.assertNotIn("Bearer ", completed.stdout)
        self.assertNotIn("Bearer ", completed.stderr)


if __name__ == "__main__":
    unittest.main()
