"""The fixed seven-tool kit + the agent factory that binds it.

`make_toolkit(orchestrator, ctx)` returns a list of seven Python callables. The
list is identical in shape across every role; what each tool does for a given
role is whatever the orchestrator + ontology say (no per-role customization)."""
from .agent_toolkit import ToolKit, make_toolkit

__all__ = ["ToolKit", "make_toolkit"]
