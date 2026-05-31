"""Shared pytest fixtures.

The Ontology Service is expensive to construct (parses the full YAML); cache
once per session and let tests share the read-only service."""
from __future__ import annotations

import pytest

from ontology_service import WORLD_STATE_YAML, OntologyService


@pytest.fixture(scope="session")
def ontology_yaml_path():
    from ontology_service import SUPPLY_CHAIN_DEMO_YAML

    return SUPPLY_CHAIN_DEMO_YAML


@pytest.fixture(scope="session")
def ontology_service(ontology_yaml_path) -> OntologyService:
    return OntologyService.load(str(ontology_yaml_path))


@pytest.fixture(scope="session")
def world_state(ontology_service):
    """The demo world fixture, validated against the loaded schema."""
    from e2e_orchestrator.world_state import WorldState

    return WorldState.load(WORLD_STATE_YAML, ontology_service.ontology.schema_view)
