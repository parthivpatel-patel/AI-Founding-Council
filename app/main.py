"""CLI for the AI Founding Council.

`python -m app.main` prints status and does not call a provider.
`python -m app.main ask "..."` runs independent analyses, cross-examination, evidence resolution, a red-team pass, and a pending decision memo.
`python -m app.main decide <ceo_decision.json> approve|reject [reasoning]` records that decision locally.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app import PHASE, __version__
from app.config import env_flag, env_value, load_env_file
from app.council.debate import examine
from app.council.independent import run_independent_round
from app.council.synthesis import conclude
from app.memory.decisions import record_ceo_decision
from app.providers.base import ProviderError
from app.providers.registry import router_from_env

ROOT = Path(os.environ["COUNCIL_ROOT"]) if os.environ.get("COUNCIL_ROOT", "").strip() else Path(__file__).resolve().parents[1]
COMPANY_STATE_PATH = ROOT / "company" / "COMPANY_STATE.md"

_PROVIDER_FLAGS = (
    ("openai", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_API_AUTHORIZED"),
    ("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_API_AUTHORIZED"),
    ("gemini", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_API_AUTHORIZED"),
    ("xai", "XAI_API_KEY", "XAI_MODEL", "XAI_API_AUTHORIZED"),
    ("nvidia", "NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_API_AUTHORIZED"),
    ("cursor", "CURSOR_API_KEY", "CURSOR_MODEL", "CURSOR_API_AUTHORIZED"),
)


def main(argv: list[str] | None = None) -> int:
    load_env_file(ROOT / ".env")
    args = list(sys.argv[1:] if argv is None else argv)
    if not COMPANY_STATE_PATH.is_file():
        print("Missing company/COMPANY_STATE.md", file=sys.stderr)
        return 1
    if args and args[0] == "ask":
        return _ask(args[1:])
    if args and args[0] == "decide":
        return _decide(args[1:])
    return _status()


def _status() -> int:
    print(f"AI Founding Council V1 (phase {PHASE}, version {__version__})")
    print("Rounds: independent analysis, cross-examination, evidence resolution, red-team pass, pending memo.")
    print("CEO recording: python -m app.main decide <ceo_decision.json> approve|reject [reasoning]")
    blocked = False
    for name, key_name, model_name, flag_name in _PROVIDER_FLAGS:
        ready = bool(env_value(key_name) and env_value(model_name) and env_flag(flag_name))
        if not ready:
            blocked = True
        print(f"{name}: {'authorized' if ready else 'blocked'}")
    if blocked:
        print("Live API calls: blocked until each provider key, model, and authorization flag are set")
    else:
        print("Live API calls: authorized by CEO flags")
    print("Default routes: strategy=openai research=gemini red_team=anthropic contrarian=xai cto=cursor")
    print("Cursor is the CTO. NVIDIA is an unassigned provider.")
    return 0


def _ask(words: list[str]) -> int:
    question = " ".join(words).strip()
    if not question:
        print('Usage: python -m app.main ask "question"', file=sys.stderr)
        return 2
    try:
        router = router_from_env(ROOT)
        round1 = run_independent_round(question, router=router, root=ROOT)
        examination = examine(question, round1, router=router, root=ROOT)
        decision = conclude(question, round1, examination.disputes, router=router, root=ROOT)
    except (ProviderError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    available = 0
    print("ROUND 1")
    for result in round1:
        label = "READY" if result.available else "AGENT_UNAVAILABLE"
        print(f"[{result.role}] {label}")
        print(result.detail)
        if result.path is not None:
            print(f"Saved: {result.path}")
        if result.available:
            available += 1
        print()
    print("CROSS-EXAMINATION")
    for result in examination.reviews:
        if not any(item.role == result.role and item.available for item in round1):
            print(f"[{result.role}] AGENT_UNAVAILABLE")
            continue
        label = "READY" if result.available else "CROSS_EXAM_UNAVAILABLE"
        print(f"[{result.role}] {label}")
        print(result.detail)
        if result.path is not None:
            print(f"Saved: {result.path}")
        print()
    print("DISAGREEMENTS")
    if examination.disputes:
        for dispute in examination.disputes:
            print(f"{dispute.dispute_id}: {dispute.claim}")
            print(f"Status: {dispute.status}")
            print(f"Raised by: {', '.join(dispute.raised_by)}")
            print(dispute.required_action)
            print()
    else:
        print("No disagreement was detected.")
        print()
    print("Model agreement is not evidence.")
    print("EVIDENCE RESOLUTION")
    if decision.resolutions:
        for item in decision.resolutions:
            print(f"{item.dispute_id}: {item.status}")
            print(item.assessment)
            print(item.required_action)
            print()
    else:
        print("No dispute was stated, so no extra research call was made.")
        print()
    print("RED TEAM PASS")
    print(decision.thesis.reason)
    print(decision.red_team.strongest_counterargument)
    print()
    print("CEO DECISION MEMO")
    print(f"CEO DECISION: {decision.memo.ceo_decision}")
    print(decision.memo.recommended_next_action)
    print("Estimated cost USD: unverified")
    print(f"Saved: {decision.path}")
    return 0 if available else 2


def _decide(words: list[str]) -> int:
    if len(words) < 2 or words[1].lower() not in {"approve", "reject"}:
        print(
            'Usage: python -m app.main decide <ceo_decision.json> approve|reject [reasoning]',
            file=sys.stderr,
        )
        return 2
    decision = "APPROVED" if words[1].lower() == "approve" else "REJECTED"
    reasoning = " ".join(words[2:]).strip()
    try:
        recorded = record_ceo_decision(ROOT, Path(words[0]), decision, reasoning)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"CEO DECISION: {recorded.ceo_decision}")
    print(f"Decision ID: {recorded.decision_id}")
    print(f"Saved: {recorded.record_path}")
    print("Company state and the decision log now include this decision.")
    print("Unknown fields were not changed. No spend was authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
