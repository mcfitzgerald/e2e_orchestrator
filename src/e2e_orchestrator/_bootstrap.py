"""Make the e2e_ontology repo importable.

The ontology repo has no pyproject.toml today, so we can't `uv pip install -e`
it. Instead we resolve it via:

  1. `E2E_ONTOLOGY_PATH` env var (absolute path), if set; else
  2. sibling directory `../e2e_ontology` relative to this repo's root.

The resolved path is prepended to `sys.path` so `exploder` and `ontology_service`
import cleanly. When the ontology repo grows a pyproject, swap this for a real
dependency in pyproject.toml and delete this module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _candidate_paths() -> list[Path]:
    env = os.environ.get("E2E_ONTOLOGY_PATH")
    out: list[Path] = []
    if env:
        out.append(Path(env).expanduser().resolve())
    # this file lives at src/e2e_orchestrator/_bootstrap.py, repo root is parents[2]
    out.append((Path(__file__).resolve().parents[2] / ".." / "e2e_ontology").resolve())
    return out


def ensure_ontology_on_path() -> Path:
    for p in _candidate_paths():
        if (p / "exploder.py").is_file() and (p / "ontology_service").is_dir():
            sp = str(p)
            if sp not in sys.path:
                sys.path.insert(0, sp)
            return p
    raise RuntimeError(
        "Could not locate the e2e_ontology repo. Set E2E_ONTOLOGY_PATH or place "
        f"it at a sibling directory of this repo. Tried: {[str(p) for p in _candidate_paths()]}"
    )


ONTOLOGY_REPO_PATH: Path = ensure_ontology_on_path()
ONTOLOGY_YAML_PATH: Path = ONTOLOGY_REPO_PATH / "supply_chain_demo.yaml"
WORLD_STATE_YAML_PATH: Path = ONTOLOGY_REPO_PATH / "world_state.yaml"
