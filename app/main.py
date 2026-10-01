"""Local CLI entry point.

Phase 1 only checks that the scaffold and company state are present.
It does not call a model provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app import PHASE, __version__

ROOT = Path(__file__).resolve().parents[1]
COMPANY_STATE_PATH = ROOT / "company" / "COMPANY_STATE.md"


def main() -> int:
    if not COMPANY_STATE_PATH.is_file():
        print("Missing company/COMPANY_STATE.md", file=sys.stderr)
        return 1

    print(f"AI Founding Council V1 (phase {PHASE}, version {__version__})")
    print("Scaffold ready.")
    print(f"Company state: {COMPANY_STATE_PATH.relative_to(ROOT)}")
    print("Providers connected: none")
    print("Council session: not available in phase 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
