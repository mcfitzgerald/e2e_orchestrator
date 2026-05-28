"""Shared pytest fixtures.

The Ontology Service is expensive to construct (parses the full YAML); cache
once per session and let tests share the read-only service."""
from __future__ import annotations

import pytest

from e2e_orchestrator import _bootstrap  # noqa: F401 — surfaces ontology repo
from ontology_service import OntologyService


@pytest.fixture(scope="session")
def ontology_yaml_path():
    return _bootstrap.ONTOLOGY_YAML_PATH


@pytest.fixture(scope="session")
def ontology_service(ontology_yaml_path) -> OntologyService:
    return OntologyService.load(str(ontology_yaml_path))
