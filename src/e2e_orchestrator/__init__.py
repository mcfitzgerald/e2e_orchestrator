"""e2e_orchestrator — generic-agent runtime over the supply chain ontology.

Importing the package implicitly ensures the sibling `e2e_ontology` repo is on
`sys.path`, so `from ontology_service import OntologyService` and
`from exploder import load_ontology` resolve. See `_bootstrap.py`.
"""
from . import _bootstrap  # noqa: F401  side-effecting import; do not remove.
