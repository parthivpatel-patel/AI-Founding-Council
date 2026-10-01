"""Persist one agent result and a usage line. Historical files are not overwritten."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.providers.base import UsageRecord


def save_agent_result(root: Path, role: str, payload: dict[str, Any], usage: UsageRecord) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = root / "council_logs" / f"{stamp}_{role}"
    directory.mkdir(parents=True, exist_ok=False)
    document = {
        "role": role,
        "saved_at": usage.timestamp,
        "result": payload,
        "usage": usage.to_dict(),
    }
    path = directory / f"{role}.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    _append_usage(root, usage)
    return path


def save_session_document(root: Path, filename: str, payload: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = root / "council_logs" / f"{stamp}_session"
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / filename
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _append_usage(root: Path, usage: UsageRecord) -> None:
    usage_path = root / "usage.jsonl"
    with usage_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(usage.to_dict()) + "\n")
