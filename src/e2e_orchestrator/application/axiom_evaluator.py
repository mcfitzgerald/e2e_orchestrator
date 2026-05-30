"""Deterministic axiom evaluation — the safety floor under the agent layer.

Per `agent_system_design.md` §8: axioms are evaluated by the orchestrator, never
by the LLM. The agent sees only the result — pass, or fail with a structured
reason and an `on_failure_route_to` if blocking. The LLM does not get to decide
whether the line has capacity.

Dispatch (the Phase 4 design point) is by what the axiom *declares*, uniformly
for every axiom:

  1. `tool_ref` present  → resolve the name in the tool registry and call
     `fn(quantum, world_state)`. World-state axioms (schedules, lead times,
     calendars) live here. `tool_ref` wins over `expr`.
  2. else `expr` present → evaluate as a **slot-level** expression: the LinkML
     `equals_expression` subset, `{quantum.<slot>}` references resolved against
     the quantum payload, comparisons/boolean/arithmetic only. **No function
     calls, no entity traversal** — those are the named Phase 4 stop condition
     ("if the expr interpreter grows function-call support, expr: was the wrong
     abstraction; pivot to tool_ref"). An expr that needs them is reported as
     not machine-evaluable in the subset (a tool_ref-migration candidate),
     non-enforcing.
  3. else (only `nl:`)   → advisory result; passes by default, evidence notes
     it was read by the LLM, not deterministically evaluated.

The same `evaluate_axiom` path backs both flow-axiom checks (`evaluate`) and FSM
guard checks (the FSM tracker), so the deterministic floor is identical whether
a constraint is hit on a handoff or on a lifecycle transition.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from ontology_service import OntologyService

from .axiom_tools import AxiomTool, default_registry


@dataclass(frozen=True)
class AxiomOutcome:
    name: str
    severity: str | None
    passed: bool
    evidence: str                          # human-readable reason, kept terse
    recovery_flow: str | None = None       # on_failure_route_to, when blocking + failed
    recovery_quantum: dict[str, Any] | None = None   # tool-built quantum for the recovery flow


@dataclass(frozen=True)
class AxiomEvalResult:
    ok: bool
    results: tuple[AxiomOutcome, ...]
    recovery_flow: str | None = None
    recovery_quantum: dict[str, Any] | None = None


_PLACEHOLDER = re.compile(r"\{([^}]+)\}")

# AST nodes the slot-expression subset permits. Deliberately excludes Call
# (function support is the stop condition), Attribute, Subscript, etc.
_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv,
    ast.Compare, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
    ast.Name, ast.Load, ast.Constant,
)


class UnsupportedExpr(Exception):
    """The expr uses a construct outside the slot-level subset (function call,
    entity traversal, unknown node). Reported as non-enforcing, not crashed."""


class AxiomEvaluator:
    """Evaluates axioms deterministically. Constructed once by the orchestrator
    with the loaded world state; the orchestrator's call site is unchanged from
    the Phase 2 stub — that is the design point."""

    def __init__(
        self,
        service: OntologyService,
        world_state: Any | None = None,
        *,
        registry: dict[str, AxiomTool] | None = None,
    ):
        self._svc = service
        self._world = world_state
        self._registry = registry if registry is not None else default_registry()

    # ---- flow-scoped evaluation (handoff path) -----------------------------

    def evaluate(self, flow_name: str, quantum: dict[str, Any]) -> AxiomEvalResult:
        axioms = self._svc.axioms_on_flow(flow_name)
        if not axioms:
            return AxiomEvalResult(ok=True, results=())

        outcomes: list[AxiomOutcome] = []
        ok = True
        recovery_flow: str | None = None
        recovery_quantum: dict[str, Any] | None = None
        for ax in axioms:
            outcome = self.evaluate_axiom(ax, quantum)
            outcomes.append(outcome)
            if not outcome.passed and _enum_value(ax.severity) == "blocking":
                ok = False
                if recovery_flow is None and outcome.recovery_flow is not None:
                    recovery_flow = outcome.recovery_flow
                    recovery_quantum = outcome.recovery_quantum
        return AxiomEvalResult(
            ok=ok,
            results=tuple(outcomes),
            recovery_flow=recovery_flow,
            recovery_quantum=recovery_quantum,
        )

    # ---- single-axiom evaluation (shared by FSM guards) --------------------

    def evaluate_axiom(self, ax: Any, quantum: dict[str, Any]) -> AxiomOutcome:
        severity = _enum_value(ax.severity)
        tool_ref = getattr(ax, "tool_ref", None)

        if tool_ref:
            passed, evidence, recovery_quantum = self._eval_tool_ref(tool_ref, quantum)
        elif getattr(ax, "expr", None):
            passed, evidence = self._eval_expr(ax.expr, quantum)
            recovery_quantum = None
        else:
            passed, evidence = True, "LLM-read; deterministic eval not applicable (nl-only axiom)"
            recovery_quantum = None

        recovery_flow = None
        if not passed and severity == "blocking":
            recovery_flow = getattr(ax, "on_failure_route_to", None)
        else:
            recovery_quantum = None  # only carry a recovery quantum for blocking failures

        return AxiomOutcome(
            name=ax.name,
            severity=severity,
            passed=passed,
            evidence=evidence,
            recovery_flow=recovery_flow,
            recovery_quantum=recovery_quantum,
        )

    # ---- dispatch implementations ------------------------------------------

    def _eval_tool_ref(self, tool_ref: str, quantum: dict[str, Any]):
        fn = self._registry.get(tool_ref)
        if fn is None:
            return True, f"tool_ref {tool_ref!r} not registered; deterministic eval skipped", None
        if self._world is None:
            return True, f"tool_ref {tool_ref!r} requires world state; none loaded — eval skipped", None
        result = fn(quantum, self._world)
        return result.passed, result.evidence, result.recovery_quantum

    def _eval_expr(self, expr: str, quantum: dict[str, Any]):
        """Evaluate a slot-level expression. Returns (passed, evidence)."""
        try:
            py_expr, bindings, missing = _resolve_placeholders(expr, quantum)
        except UnsupportedExpr as exc:
            return True, f"expr not machine-evaluable in slot subset ({exc}); candidate for tool_ref"
        if missing:
            # LinkML convention: missing values evaluate to None. We do not
            # block on a value the quantum simply doesn't carry.
            return True, f"expr references unset slot(s) {sorted(missing)}; not enforced"
        try:
            value = _safe_eval(py_expr, bindings)
        except UnsupportedExpr as exc:
            return True, f"expr not machine-evaluable in slot subset ({exc}); candidate for tool_ref"
        passed = bool(value)
        return passed, f"expr {expr!r} evaluated to {value!r} with {bindings}"


# ---------------------------------------------------------------------------
# Slot-expression subset machinery
# ---------------------------------------------------------------------------


def _resolve_placeholders(expr: str, quantum: dict[str, Any]):
    """Replace every `{quantum.<slot>}` with a safe variable name bound to the
    slot's value. Rejects deeper paths (entity traversal) — those need world
    state, i.e. a tool_ref. Returns (python_expr, bindings, missing_slots)."""
    bindings: dict[str, Any] = {}
    missing: set[str] = set()
    counter = {"n": 0}

    def repl(match: re.Match) -> str:
        path = match.group(1).strip()
        segments = path.split(".")
        if segments[0] != "quantum":
            raise UnsupportedExpr(f"unsupported reference root {path!r}")
        if len(segments) != 2:
            # quantum.entity.subslot — entity traversal, needs world state.
            raise UnsupportedExpr(f"entity traversal {path!r}")
        slot = segments[1]
        var = f"_v{counter['n']}"
        counter["n"] += 1
        value = quantum.get(slot)
        if value is None:
            missing.add(slot)
        bindings[var] = value
        return var

    py_expr = _PLACEHOLDER.sub(repl, expr)
    return py_expr, bindings, missing


def _safe_eval(py_expr: str, bindings: dict[str, Any]) -> Any:
    try:
        tree = ast.parse(py_expr, mode="eval")
    except SyntaxError as exc:
        raise UnsupportedExpr(f"syntax error: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsupportedExpr(f"unsupported construct {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in bindings:
            raise UnsupportedExpr(f"unbound name {node.id!r}")
    return _eval_node(tree.body, bindings)


_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
    ast.FloorDiv: lambda a, b: a // b,
}
_CMPOPS = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}


def _eval_node(node: ast.AST, b: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return b[node.id]
    if isinstance(node, ast.UnaryOp):
        v = _eval_node(node.operand, b)
        if isinstance(node.op, ast.Not):
            return not v
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return +v
    if isinstance(node, ast.BoolOp):
        vals = [_eval_node(v, b) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(vals)
        return any(vals)
    if isinstance(node, ast.BinOp):
        return _BINOPS[type(node.op)](_eval_node(node.left, b), _eval_node(node.right, b))
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, b)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, b)
            if not _CMPOPS[type(op)](left, right):
                return False
            left = right
        return True
    raise UnsupportedExpr(f"unsupported node {type(node).__name__}")


def _enum_value(v: Any) -> str | None:
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)
