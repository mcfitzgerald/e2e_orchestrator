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


@pytest.fixture(scope="session")
def world_state(ontology_service):
    """The demo world fixture, validated against the loaded schema."""
    from e2e_orchestrator.world_state import WorldState

    return WorldState.load(_bootstrap.WORLD_STATE_YAML_PATH, ontology_service.ontology.schema_view)
