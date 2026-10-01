"""Record an explicit CEO approval or rejection.

The pending memo stays the proposal. This module appends the human decision
to the decision log and the Major Decisions section. It does not call a model,
authorize spending, or fill unknown company fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_DECISIONS = ("APPROVED", "REJECTED")
_MEMO_FIELDS = (
    "question",
    "current_state",
    "what_we_know",
    "what_we_dont_know",
    "strongest_evidence",
    "strongest_counterargument",
    "key_assumptions",
    "critical_risks",
    "council_disagreements",
    "cheapest_experiment",
    "expected_cost",
    "expected_learning",
    "kill_criteria",
    "recommended_next_action",
    "ceo_decision",
)


@dataclass(frozen=True)
class RecordedDecision:
    decision_id: str
    ceo_decision: str
    reasoning: str
    record_path: Path
    question: str


def record_ceo_decision(root: Path, memo_path: Path, decision: str, reasoning: str) -> RecordedDecision:
    """Append one CEO decision for a pending memo. A second record is refused."""
    if decision not in _DECISIONS:
        raise ValueError("CEO decision must be APPROVED or REJECTED")
    memo_file = _memo_file(root, memo_path)
    payload = json.loads(memo_file.read_text(encoding="utf-8"))
    memo = _pending_memo(payload)
    record_path = memo_file.parent / "ceo_record.json"
    log_path = root / "company" / "DECISION_LOG.md"
    state_path = root / "company" / "COMPANY_STATE.md"
    if not log_path.is_file():
        raise FileNotFoundError("company/DECISION_LOG.md is missing")
    if not state_path.is_file():
        raise FileNotFoundError("company/COMPANY_STATE.md is missing")
    log_text = log_path.read_text(encoding="utf-8")
    state_text = state_path.read_text(encoding="utf-8")
    relative = memo_file.relative_to(root.resolve()).as_posix()
    if record_path.exists() or relative in log_text:
        raise ValueError("This memo already has a recorded CEO decision.")
    recorded_at = datetime.now(timezone.utc)
    decision_id = _next_id(log_text)
    reason = reasoning.strip() or "Not provided."
    entry = _entry(decision_id, recorded_at.date().isoformat(), decision, reason, memo, relative)
    bullet = f"- {decision_id} ({recorded_at.date().isoformat()}): {decision}. {_one_line(memo['question'])}\n"
    log_path.write_text(_append_log(log_text, entry), encoding="utf-8")
    state_path.write_text(_update_major_decisions(state_text, bullet), encoding="utf-8")
    document = {
        "decision_id": decision_id,
        "ceo_decision": decision,
        "reasoning": reason,
        "recorded_at": recorded_at.isoformat(),
        "memo_file": relative,
        "question": memo["question"],
        "note": (
            "The human CEO recorded this decision. Unknown company fields were not changed. "
            "No spend was authorized."
        ),
    }
    record_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return RecordedDecision(decision_id, decision, reason, record_path, memo["question"])


def _memo_file(root: Path, memo_path: Path) -> Path:
    path = memo_path.expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if path.is_dir():
        path = path / "ceo_decision.json"
    logs = (root / "council_logs").resolve()
    if logs != path.parent.parent:
        raise ValueError("Decision memos must live under council_logs")
    if path.name != "ceo_decision.json":
        raise ValueError("Expected ceo_decision.json")
    if not path.is_file():
        raise FileNotFoundError("ceo_decision.json was not found")
    return path


def _pending_memo(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("memo"), dict):
        raise ValueError("ceo_decision.json has no memo")
    memo = payload["memo"]
    cleaned: dict[str, str] = {}
    for name in _MEMO_FIELDS:
        value = memo.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Memo field {name} is missing")
        cleaned[name] = value.strip()
    if cleaned["ceo_decision"] != "PENDING":
        raise ValueError("Only a pending memo can be recorded")
    return cleaned


def _next_id(log_text: str) -> str:
    numbers = [int(item) for item in re.findall(r"DECISION-(\d+)", log_text)]
    return f"DECISION-{max(numbers, default=0) + 1:03d}"


def _entry(decision_id: str, date: str, decision: str, reasoning: str, memo: dict[str, str], relative: str) -> str:
    outcome = (
        "The CEO accepted the memo."
        if decision == "APPROVED"
        else "The CEO did not accept the memo."
    )
    lines = [
        f"## {decision_id}",
        "",
        f"- Decision ID: {decision_id}",
        f"- Date: {date}",
        f"- Question: {_one_line(memo['question'])}",
        f"- Evidence: {_one_line(memo['strongest_evidence'])} Cited evidence does not make the claim true.",
        (
            "- Alternatives considered: Not listed separately in the memo. "
            f"Recommended next action: {_one_line(memo['recommended_next_action'])} "
            f"Strongest counterargument: {_one_line(memo['strongest_counterargument'])}"
        ),
        f"- Council disagreements: {_one_line(memo['council_disagreements'])}",
        f"- Decision: {decision}. {outcome} This does not authorize spending and does not convert assumptions into facts.",
        f"- CEO reasoning, if provided: {_one_line(reasoning)}",
        f"- Expected outcome: Expected, not observed. {_one_line(memo['expected_learning'])}",
        f"- Reversal condition: {_one_line(memo['kill_criteria'])}",
        f"- Memo: {relative}",
        "",
    ]
    return "\n".join(lines)


def _append_log(text: str, entry: str) -> str:
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip() == "No decisions have been recorded.":
            return "".join(lines[:index]) + entry.rstrip() + "\n" + "".join(lines[index + 1 :])
    suffix = "" if text.endswith("\n") else "\n"
    return text + suffix + "\n" + entry


def _update_major_decisions(text: str, bullet: str) -> str:
    lines = text.splitlines(keepends=True)
    start = next((index for index, line in enumerate(lines) if line.strip() == "## Major Decisions"), None)
    if start is None:
        raise ValueError("COMPANY_STATE.md has no Major Decisions section")
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    body = "".join(lines[start + 1:end])
    if "DECISION-" in body:
        addition = bullet if body.endswith("\n") else "\n" + bullet
        updated = body + addition
        if end < len(lines) and not updated.endswith("\n\n"):
            updated += "\n"
        return "".join(lines[: start + 1]) + updated + "".join(lines[end:])
    if "None recorded." not in body:
        raise ValueError("Major Decisions is neither empty nor an existing decision list")
    updated = bullet if bullet.endswith("\n") else bullet + "\n"
    if end < len(lines):
        updated += "\n"
    return "".join(lines[: start + 1]) + updated + "".join(lines[end:])


def _one_line(value: str) -> str:
    return " ".join(value.split())
