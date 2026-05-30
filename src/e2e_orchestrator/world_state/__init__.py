"""World-state layer — runtime fixture the orchestrator loads at boot.

Holds validated entity instances + supplementary state (schedule, clock) and
exposes generic typed queries the axiom evaluator composes. Swappable for an
enterprise system-of-record reader behind the same query surface (§9)."""
from .loader import Entity, LineLoad, WorldState, WorldStateValidationError

__all__ = ["WorldState", "Entity", "LineLoad", "WorldStateValidationError"]
