"""e2e_orchestrator — generic-agent runtime over the supply chain ontology.

The `e2e_ontology` package is a declared dependency (see `pyproject.toml`,
installed via `[tool.uv.sources]` as an editable local checkout), so
`from ontology_service import OntologyService` and `from exploder import
load_ontology` resolve normally — no sys.path shim. Data-file locations come
from `ontology_service.paths` (e.g. `SUPPLY_CHAIN_DEMO_YAML`, `WORLD_STATE_YAML`).
"""
