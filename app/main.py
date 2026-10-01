"""CLI for the AI Founding Council.

`python -m app.main` prints status and does not call a provider.
`python -m app.main ask "..."` runs the strategist when the CEO has authorized OpenAI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app import PHASE, __version__
from app.agents.strategist import ask_strategist
from app.config import env_flag, env_value, load_env_file
from app.providers.base import ProviderError
from app.providers.openai import OpenAIProvider
from app.providers.router import ModelRouter
from app.schemas.messages import render_analysis

ROOT = Path(__file__).resolve().parents[1]
COMPANY_STATE_PATH = ROOT / "company" / "COMPANY_STATE.md"


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
    key_set = bool(env_value("OPENAI_API_KEY"))
    model_set = bool(env_value("OPENAI_MODEL"))
    authorized = env_flag("OPENAI_API_AUTHORIZED")
    if key_set and model_set and authorized:
        live = "authorized by CEO flag"
    else:
        live = "blocked until OPENAI_API_KEY, OPENAI_MODEL, and OPENAI_API_AUTHORIZED=1 are set"
    print(f"AI Founding Council V1 (phase {PHASE}, version {__version__})")
    print("Strategist agent and OpenAI adapter are implemented.")
    print("Provider adapter: OpenAI Responses API POST /v1/responses")
    print(f"Live API calls: {live}")
    print("Other providers: not connected")
    print("Council session: not available until a later phase")
    return 0


def _ask(words: list[str]) -> int:
    question = " ".join(words).strip()
    if not question:
        print('Usage: python -m app.main ask "question"', file=sys.stderr)
        return 2
    try:
        provider = OpenAIProvider.from_env()
        result = ask_strategist(question, provider=ModelRouter({"openai": provider}).select("strategy"), root=ROOT)
    except (ProviderError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(render_analysis(result.analysis))
    print(f"Latency ms: {result.usage.latency_ms}")
    print("Estimated cost USD: unverified")
    print(f"Saved: {result.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
