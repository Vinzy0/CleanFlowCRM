"""Configuration for the automation, demo and rate-limit layers.

The process environment wins; the git-ignored project ``.env`` fills any gaps so
a direct local run works without exporting variables by hand. Values are read on
demand, which keeps tests able to change configuration per case. Secrets are
never logged, returned to clients, or included in error messages.
"""

import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"

_values: dict[str, str] | None = None


def _project_values() -> dict[str, str]:
    global _values
    if _values is None:
        raw = dotenv_values(PROJECT_ENV) if PROJECT_ENV.is_file() else {}
        _values = {key: (value or "").strip() for key, value in raw.items()}
    return _values


def reload() -> None:
    """Drop cached ``.env`` contents (used by tests and long-running shells)."""
    global _values
    _values = None


def env(name: str, default: str | None = None) -> str | None:
    """Process environment first, then the project ``.env``, then ``default``."""
    if name in os.environ:
        return os.environ[name].strip() or default
    return _project_values().get(name) or default


def flag(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def number(name: str, default: int) -> int:
    value = env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
