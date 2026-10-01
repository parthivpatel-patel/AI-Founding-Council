"""Round 1: independent analyses. Agents do not see each other."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.agents.contrarian import ask_contrarian
from app.agents.red_team import ask_red_team
from app.agents.researcher import ask_researcher
from app.agents.strategist import ask_strategist
from app.memory.storage import save_agent_result
from app.providers.base import ModelProvider, ProviderError, UsageRecord
from app.providers.router import ModelRouter
from app.schemas.messages import render_analysis

_CALLS = (
    ("strategist", "strategy", ask_strategist),
    ("researcher", "research", ask_researcher),
    ("red_team", "red_team", ask_red_team),
    ("contrarian", "contrarian", ask_contrarian),
)


@dataclass(frozen=True)
class IndependentResult:
    role: str
    available: bool
    detail: str
    path: Path | None


def run_independent_round(question: str, *, router: ModelRouter, root: Path) -> list[IndependentResult]:
    if not question.strip():
        raise ValueError("question is empty")

    def run_one(role: str, task: str, caller) -> IndependentResult:
        try:
            provider: ModelProvider = router.select(task)
            result = caller(question, provider=provider, root=root)
        except ProviderError as exc:
            path = None
            if exc.usage is None:
                path = save_agent_result(
                    root,
                    role,
                    {"question": question.strip(), "error": "AGENT_UNAVAILABLE", "detail": str(exc)},
                    _unavailable_usage(role, str(exc)),
                )
            return IndependentResult(role=role, available=False, detail=str(exc), path=path)
        return IndependentResult(
            role=role,
            available=True,
            detail=render_analysis(result.analysis),
            path=result.path,
        )

    with ThreadPoolExecutor(max_workers=len(_CALLS)) as pool:
        futures = [pool.submit(run_one, role, task, caller) for role, task, caller in _CALLS]
        return [future.result() for future in futures]


def _unavailable_usage(role: str, error: str) -> UsageRecord:
    return UsageRecord(
        provider="unassigned",
        model="unset",
        task=role,
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_tokens=None,
        output_tokens=None,
        estimated_cost_usd=None,
        latency_ms=0.0,
        success=False,
        reason="Provider was not authorized or not configured",
        error=error[:300],
    )
