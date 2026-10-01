"""CLI for the AI Founding Council.

`python -m app.main` prints status and does not call a provider.
`python -m app.main ask "..."` runs four independent analyses. No debate.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app import PHASE, __version__
from app.config import env_flag, env_value, load_env_file
from app.council.independent import run_independent_round
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
    return _status()


def _status() -> int:
    print(f"AI Founding Council V1 (phase {PHASE}, version {__version__})")
    print("Independent round: strategist, researcher, red team, contrarian. No debate.")
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
    print("Default routes: strategy=openai research=gemini red_team=anthropic contrarian=xai")
    print("NVIDIA and Cursor are available as role overrides.")
    return 0


def _ask(words: list[str]) -> int:
    question = " ".join(words).strip()
    if not question:
        print('Usage: python -m app.main ask "question"', file=sys.stderr)
        return 2
    try:
        results = run_independent_round(question, router=router_from_env(ROOT), root=ROOT)
    except (ProviderError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    available = 0
    for result in results:
        label = "READY" if result.available else "AGENT_UNAVAILABLE"
        print(f"[{result.role}] {label}")
        print(result.detail)
        if result.path is not None:
            print(f"Saved: {result.path}")
        if result.available:
            available += 1
        print()
    print("Estimated cost USD: unverified")
    print("Debate: not run")
    return 0 if available else 2


if __name__ == "__main__":
    raise SystemExit(main())
