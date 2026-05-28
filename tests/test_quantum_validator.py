"""Quantum validator: required-slot + primitive-type + class-ref checks."""
from __future__ import annotations

import pytest

from e2e_orchestrator.application.quantum_validator import QuantumValidator


@pytest.fixture()
def validator(ontology_service):
    return QuantumValidator(ontology_service.ontology.schema_view)


def test_valid_demand_anomaly_passes(validator):
    result = validator.validate(
        "DemandAnomaly",
        {
            "anomaly_id": "anom-1",
            "sku": "sku-toothpaste-6oz",
            "detected_day": 42,
            "departure_units": 1500.0,
            "severity_score": 0.9,
        },
    )
    assert result.ok, result.errors


def test_missing_required_field_flags_error(validator):
    result = validator.validate("DemandAnomaly", {"anomaly_id": "x", "sku": "y", "detected_day": 1})
    assert not result.ok
    codes = {e.code for e in result.errors}
    assert "missing_required" in codes


def test_type_mismatch_flags_error(validator):
    result = validator.validate(
        "DemandAnomaly",
        {"anomaly_id": "x", "sku": "y", "detected_day": "not-an-int", "departure_units": 1.0},
    )
    assert not result.ok
    assert any(e.code == "type_mismatch" and e.slot == "detected_day" for e in result.errors)


def test_unknown_slot_flags_error(validator):
    result = validator.validate(
        "DemandAnomaly",
        {"anomaly_id": "x", "sku": "y", "detected_day": 1, "departure_units": 1.0, "bogus": True},
    )
    assert not result.ok
    assert any(e.code == "unknown_slot" and e.slot == "bogus" for e in result.errors)


def test_supply_request_validates(validator):
    result = validator.validate(
        "SupplyRequest",
        {
            "request_id": "sr-1",
            "sku": "sku-A",
            "volume": 4500,
            "required_by": 90,
            "source_signal_ref": "anom-1",
        },
    )
    assert result.ok, result.errors
