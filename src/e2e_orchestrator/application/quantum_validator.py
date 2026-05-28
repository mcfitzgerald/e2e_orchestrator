"""Deterministic quantum validation against the LinkML schema.

A quantum is a typed payload (e.g. `DemandAnomaly`, `SupplyRequest`). The agent
emits it as a dict via a tool call; before the orchestrator routes it, the dict
must validate against the class declared in the ontology — `f.body.quantum` on
the flow body resolves to a class name; this validator turns that name + the
dict into a pass/fail with structured errors.

We use `SchemaView` to introspect required slots + basic types. We deliberately
do not generate Pydantic classes at runtime — the validation surface we need
(required-slots-present, primitive-type-compatible, enum-membership-clean,
reference-string-shape) is small enough to handle directly.

LinkML primitive ranges we recognize:
  string, integer, decimal, float, double, boolean, date, datetime, uri, curie.
Class ranges (e.g. `range: SKU`) and enum ranges are checked structurally:
class ranges accept any non-empty string id; enum ranges check membership.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView


_PRIMITIVE_TYPES = {
    "string": (str,),
    "integer": (int,),
    "decimal": (int, float),       # accept either; LinkML decimal is a number
    "float": (int, float),
    "double": (int, float),
    "boolean": (bool,),
    "date": (str,),                # accept ISO string for the POC
    "datetime": (str,),
    "uri": (str,),
    "curie": (str,),
}


@dataclass(frozen=True)
class ValidationError:
    slot: str
    code: str                      # "missing_required" | "type_mismatch" | "enum_unknown" | "unknown_slot"
    detail: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    quantum_class: str
    errors: tuple[ValidationError, ...] = ()
    normalized: dict[str, Any] = field(default_factory=dict)


class QuantumValidator:
    """Validates a quantum dict against its class as declared in the ontology."""

    def __init__(self, schemaview: SchemaView):
        self._sv = schemaview

    def validate(self, class_name: str, payload: dict[str, Any]) -> ValidationResult:
        cls = self._sv.get_class(class_name)
        if cls is None:
            return ValidationResult(
                ok=False,
                quantum_class=class_name,
                errors=(ValidationError(slot="<class>", code="unknown_class", detail=f"{class_name} not in schema"),),
            )

        slots = {s.name: s for s in self._induced_slots(cls)}
        errors: list[ValidationError] = []

        # Unknown-slot check.
        for k in payload.keys():
            if k not in slots:
                errors.append(ValidationError(slot=k, code="unknown_slot", detail=f"{class_name} has no slot {k}"))

        # Required-slot + type checks.
        for name, slot in slots.items():
            if name not in payload or payload[name] is None:
                if bool(getattr(slot, "required", False)):
                    errors.append(ValidationError(slot=name, code="missing_required", detail=f"required slot {name} absent"))
                continue
            err = self._check_slot_value(name, slot, payload[name])
            if err is not None:
                errors.append(err)

        return ValidationResult(
            ok=not errors,
            quantum_class=class_name,
            errors=tuple(errors),
            normalized=dict(payload),
        )

    def _induced_slots(self, cls: ClassDefinition) -> list[SlotDefinition]:
        """Walk inheritance + mixins via SchemaView so subclass slots resolve.

        `class_induced_slots` already returns fully-induced `SlotDefinition`
        objects (with `required`, `range`, etc. flattened from ancestors), so
        we return them directly."""
        return list(self._sv.class_induced_slots(cls.name))

    def _check_slot_value(self, name: str, slot: SlotDefinition, value: Any) -> ValidationError | None:
        range_ = slot.range
        if range_ is None:
            return None
        # LinkML primitive type.
        if range_ in _PRIMITIVE_TYPES:
            allowed = _PRIMITIVE_TYPES[range_]
            if not isinstance(value, allowed):
                return ValidationError(
                    slot=name,
                    code="type_mismatch",
                    detail=f"slot {name} range={range_} but value type={type(value).__name__}",
                )
            return None
        # Enum.
        enum = self._sv.get_enum(range_)
        if enum is not None:
            permitted = set((enum.permissible_values or {}).keys())
            if not isinstance(value, str) or value not in permitted:
                return ValidationError(
                    slot=name,
                    code="enum_unknown",
                    detail=f"slot {name} value {value!r} not in {sorted(permitted)}",
                )
            return None
        # Class range — accept any non-empty string id (POC: we don't resolve refs).
        cls_range = self._sv.get_class(range_)
        if cls_range is not None:
            if not isinstance(value, (str, dict)) or (isinstance(value, str) and not value):
                return ValidationError(
                    slot=name,
                    code="type_mismatch",
                    detail=f"slot {name} expects class ref ({range_}) as id/dict; got {type(value).__name__}",
                )
            return None
        # Unknown range — be permissive.
        return None
