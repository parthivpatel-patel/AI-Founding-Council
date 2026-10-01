"""Local configuration. Secrets stay in the environment or .env."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """Load KEY=value pairs into the environment without overriding existing values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def provider_settings(key_name: str, model_name: str, flag_name: str) -> tuple[str, str, bool, float]:
    timeout_raw = env_value("PROVIDER_TIMEOUT_SECONDS") or "25"
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 25.0
    return env_value(key_name), env_value(model_name), env_flag(flag_name), min(max(timeout, 1.0), 60.0)
