"""Minimal .env file loader (no external dependencies).

Reads KEY=VALUE pairs from a .env file and inserts them into os.environ
(without overriding variables already present in the environment).
"""
from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def load_env(path: str | Path | None = None) -> None:
    path = Path(path) if path else _ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
