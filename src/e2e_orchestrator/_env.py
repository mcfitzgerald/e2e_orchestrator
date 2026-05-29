"""Minimal `.env` loader — avoids the `python-dotenv` dependency.

Reads `.env` (or `$E2E_ENV_FILE`) from the current working directory and
populates `os.environ` with any KEY=VALUE pairs it finds. Lines starting with
`#` are skipped. Existing env vars are not overwritten — explicit shell vars
always win, matching dotenv's default behavior.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_if_present(path: str | Path | None = None) -> Path | None:
    candidate = Path(path) if path is not None else Path(os.environ.get("E2E_ENV_FILE", ".env"))
    if not candidate.is_file():
        return None
    for raw in candidate.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return candidate
