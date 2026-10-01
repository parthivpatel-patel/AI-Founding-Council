"""Checks that Phase 1 scaffolding exists and does not call providers."""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "app/__init__.py",
    "app/main.py",
    "app/agents/base.py",
    "app/agents/orchestrator.py",
    "app/agents/strategist.py",
    "app/agents/researcher.py",
    "app/agents/red_team.py",
    "app/agents/contrarian.py",
    "app/providers/base.py",
    "app/providers/openai.py",
    "app/providers/anthropic.py",
    "app/providers/gemini.py",
    "app/providers/xai.py",
    "app/council/session.py",
    "app/council/debate.py",
    "app/council/synthesis.py",
    "app/memory/company_state.py",
    "app/memory/decisions.py",
    "app/memory/storage.py",
    "app/schemas/messages.py",
    "app/schemas/decisions.py",
    "company/COMPANY_STATE.md",
    "company/MISSION.md",
    "company/DECISION_LOG.md",
    "company/EXPERIMENT_LOG.md",
    "council_logs/.gitkeep",
    ".gitignore",
    ".env.example",
    "README.md",
    "ARCHITECTURE.md",
    "DECISIONS.md",
    "AGENTS.md",
    "requirements.txt",
)

COMPANY_STATE_HEADINGS = (
    "## CEO",
    "## Current Stage",
    "## Mission",
    "## Starting Capital",
    "## Maximum Pre-Revenue Risk",
    "## AI Infrastructure Budget",
    "## Current Problem",
    "## Current Product",
    "## Current Customer",
    "## Current Business Model",
    "## Validated Facts",
    "## Assumptions",
    "## Unknowns",
    "## Disproven Assumptions",
    "## Current Bottleneck",
    "## Current Objective",
)


class ScaffoldTests(unittest.TestCase):
    def test_required_paths_exist(self) -> None:
        missing = [path for path in REQUIRED_PATHS if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])

    def test_gitignore_covers_secrets_and_venv(self) -> None:
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", ignored)
        self.assertIn(".venv/", ignored)

    def test_env_example_has_empty_keys(self) -> None:
        keys: list[str] = []
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            keys.append(key.strip())
            self.assertEqual(value.strip(), "")
        self.assertIn("OPENAI_API_KEY", keys)
        self.assertIn("OPENAI_MODEL", keys)
        self.assertIn("OPENAI_API_AUTHORIZED", keys)

    def test_company_state_has_required_sections(self) -> None:
        text = (ROOT / "company" / "COMPANY_STATE.md").read_text(encoding="utf-8")
        for heading in COMPANY_STATE_HEADINGS:
            self.assertIn(heading, text)
        self.assertIn("UNKNOWN", text)
        self.assertIn("$0", text)

    def test_phase1_modules_do_not_call_network_libraries(self) -> None:
        banned = {"openai", "anthropic", "google", "httpx", "requests", "aiohttp"}
        offenders: list[str] = []
        for path in (ROOT / "app").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = {node.module.split(".")[0]}
                else:
                    continue
                hit = banned.intersection(names)
                if hit:
                    offenders.append(f"{path.relative_to(ROOT)}: {sorted(hit)}")
        self.assertEqual(offenders, [])

    def test_cli_reports_phase1_without_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "app.main"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("phase 2", completed.stdout)
        self.assertIn("Live API calls: blocked", completed.stdout)
        self.assertNotIn("Bearer ", completed.stdout)


if __name__ == "__main__":
    unittest.main()
