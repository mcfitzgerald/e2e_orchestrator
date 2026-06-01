"""World-state loader — the orchestrator's view of the world at runtime.

Per `agent_system_design.md` §9, the orchestrator owns runtime state and the
ontology owns structure. World state for the POC is a YAML fixture
(`e2e_ontology/world_state.yaml`) loaded once at boot:

  - **Instances** of ontology entity classes (SKU, ProductionLine, Supplier,
    RetailerCommitment, TradePromotion). Each is validated against its declared
    class via the same SchemaView-driven `QuantumValidator` the orchestrator
    uses for quanta — "the fixture is real data shaped by the real schema."
  - **Supplementary state** the ontology does not model as a class: a baseline
    `production_schedule` (drives `line_capacity_not_exceeded`) and a `clock`
    (an injectable `today()` so time-dependent axioms aren't tied to wall time).

Queries are **generic over typed entities** — `find(class, **slots)` plus thin
typed wrappers. There is deliberately no per-instance / per-domain accessor
(`get_promo_for_megalomart`, etc.); that is the Phase 4 stop condition. The axiom
tools (`application/axiom_tools.py`) compose these primitives; the world model
stays domain-agnostic here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml
from linkml_runtime.utils.schemaview import SchemaView

from ..application.quantum_validator import QuantumValidator, ValidationError


# ---------------------------------------------------------------------------
# Fixture binding. Maps each top-level instance collection in world_state.yaml
# to the ontology class its items instantiate. This is the fixture's
# collection→class binding (config, not logic) — the only place plural keys
# meet class names. `clock` and `production_schedule` are supplementary state
# with no ontology class and are handled separately.
# ---------------------------------------------------------------------------

INSTANCE_COLLECTIONS: dict[str, str] = {
    "skus": "SKU",
    "production_lines": "ProductionLine",
    "suppliers": "Supplier",
    "retailer_commitments": "RetailerCommitment",
    "trade_promotions": "TradePromotion",
}


@dataclass(frozen=True)
class Entity:
    """A validated world-state instance with attribute access over its slots.

    Generic on purpose: `entity.rated_weekly_capacity` reads the slot of the
    same name from the validated payload, for any entity class. No per-type
    subclass exists — the type is carried as `class_name` for the trace."""

    class_name: str
    data: Mapping[str, Any]

    def __getattr__(self, name: str) -> Any:
        # __getattr__ only fires when normal attribute lookup misses, so the
        # real fields (`class_name`, `data`) never reach here. Guard `data`
        # to stay recursion-safe if probed before init (copy/pickle).
        if name == "data":
            raise AttributeError(name)
        try:
            return self.data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.data)


@dataclass(frozen=True)
class LineLoad:
    """Computed aggregate (not an entity): scheduled load on a line for a
    window, against the line's rated weekly capacity."""

    plant_code: str
    line_code: str
    window_start_day: int
    window_end_day: int
    scheduled_units: float
    rated_weekly_capacity: int | None
    scheduled_skus: tuple[str, ...]

    @property
    def available(self) -> float | None:
        if self.rated_weekly_capacity is None:
            return None
        return self.rated_weekly_capacity - self.scheduled_units


class WorldStateValidationError(RuntimeError):
    """Raised when a fixture instance fails validation against its class."""

    def __init__(self, collection: str, index: int, errors: tuple[ValidationError, ...]):
        self.collection = collection
        self.index = index
        self.errors = errors
        errs = ", ".join(f"{e.slot}:{e.code}" for e in errors)
        super().__init__(f"{collection}[{index}] failed schema validation: {errs}")


class WorldState:
    """Typed, queryable view over the loaded world fixture. Read-only after
    construction — the orchestrator instantiates one at boot and exposes it to
    the axiom evaluator."""

    def __init__(
        self,
        *,
        instances: dict[str, list[Entity]],
        production_schedule: list[dict[str, Any]],
        clock: dict[str, Any],
    ):
        self._instances = instances
        self._schedule = production_schedule
        self._clock = clock

    # ---- construction ------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path, schemaview: SchemaView, *, strict: bool = True) -> "WorldState":
        """Load and validate the fixture. With `strict=True` (default) a schema
        violation raises; the fixture is meant to be clean. The same
        SchemaView-driven validator the orchestrator uses for quanta enforces
        that every instance is shaped by the real schema."""
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        validator = QuantumValidator(schemaview)

        instances: dict[str, list[Entity]] = {cn: [] for cn in INSTANCE_COLLECTIONS.values()}
        for collection, class_name in INSTANCE_COLLECTIONS.items():
            items = raw.get(collection) or []
            for i, item in enumerate(items):
                result = validator.validate(class_name, item)
                if not result.ok and strict:
                    raise WorldStateValidationError(collection, i, result.errors)
                instances[class_name].append(Entity(class_name, dict(item)))

        clock = raw.get("clock") or {}
        schedule = list(raw.get("production_schedule") or [])
        return cls(instances=instances, production_schedule=schedule, clock=clock)

    # ---- generic queries over typed entities -------------------------------

    def instances_of(self, class_name: str) -> list[Entity]:
        return list(self._instances.get(class_name, ()))

    def find(self, class_name: str, **slot_filters: Any) -> Entity | None:
        """First instance of `class_name` whose slots equal every given filter.
        The single generic lookup primitive; typed accessors wrap it."""
        for ent in self._instances.get(class_name, ()):
            if all(ent.get(k) == v for k, v in slot_filters.items()):
                return ent
        return None

    def find_all(self, class_name: str, **slot_filters: Any) -> list[Entity]:
        return [
            ent
            for ent in self._instances.get(class_name, ())
            if all(ent.get(k) == v for k, v in slot_filters.items())
        ]

    # ---- thin typed accessors (parameterized, not per-instance) ------------

    def get_sku(self, sku_code: str) -> Entity | None:
        return self.find("SKU", sku_code=sku_code)

    def get_supplier(self, supplier_code: str) -> Entity | None:
        return self.find("Supplier", supplier_code=supplier_code)

    def get_production_line(self, plant: str | None, line: str) -> Entity | None:
        """Resolve a line by code, optionally constrained to a plant. Returns
        None when the line is absent or the plant doesn't match — the grounding
        signal the axiom tools turn into `unknown_entity`."""
        ent = self.find("ProductionLine", line_code=line)
        if ent is None:
            return None
        if plant is not None and ent.get("plant_code") != plant:
            return None
        return ent

    # ---- supplementary state -----------------------------------------------

    def today(self) -> int:
        """Injectable clock — `today()` for time-dependent axioms (lead time).
        Reads `clock.today_day_of_year` from the fixture (§9)."""
        return int(self._clock.get("today_day_of_year", 0))

    def query_line_load(
        self,
        plant: str | None,
        line: str,
        window_start_day: int,
        window_end_day: int,
    ) -> LineLoad:
        """Sum baseline scheduled units on `line` whose week falls inside the
        window, against the line's rated weekly capacity. Generic over the
        supplementary `production_schedule`; the unit of comparison is weekly
        (capacity is weekly), so a single-week window is the intended grain."""
        line_ent = self.get_production_line(plant, line)
        capacity = int(line_ent.rated_weekly_capacity) if line_ent is not None else None

        total = 0.0
        skus: list[str] = []
        for row in self._schedule:
            if row.get("line") != line:
                continue
            week = row.get("week_start_day")
            if week is None or not (window_start_day <= week <= window_end_day):
                continue
            total += float(row.get("units", 0))
            sku = row.get("sku")
            if sku is not None and sku not in skus:
                skus.append(sku)

        return LineLoad(
            plant_code=plant if plant is not None else (line_ent.get("plant_code") if line_ent else ""),
            line_code=line,
            window_start_day=window_start_day,
            window_end_day=window_end_day,
            scheduled_units=total,
            rated_weekly_capacity=capacity,
            scheduled_skus=tuple(skus),
        )

    def commitments_for_skus(self, skus: Iterable[str]) -> list[Entity]:
        """Retailer commitments whose SKU is in `skus`. Generic filter (used by
        the capacity tool to populate at-risk commitments); not SKU-specific."""
        wanted = set(skus)
        return [c for c in self.instances_of("RetailerCommitment") if c.get("sku") in wanted]
