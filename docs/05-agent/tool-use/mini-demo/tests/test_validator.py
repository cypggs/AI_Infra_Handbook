"""Tests for JSON Schema validation."""

import pytest

from tool_use_mini.validator import ValidationError, validate_arguments


def test_valid_arguments():
    """Valid arguments produce no errors."""
    schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
        },
        "required": ["city"],
    }
    errors = validate_arguments({"city": "北京"}, schema)
    assert errors == []


def test_missing_required():
    """Missing required fields are reported."""
    schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
        },
        "required": ["city"],
    }
    errors = validate_arguments({}, schema)
    assert len(errors) == 1
    assert errors[0].path == "city"
    assert "missing" in errors[0].message


def test_wrong_type():
    """Type mismatches are reported."""
    schema = {
        "type": "object",
        "properties": {
            "amount_usd": {"type": "number"},
        },
        "required": ["amount_usd"],
    }
    errors = validate_arguments({"amount_usd": "1000"}, schema)
    assert len(errors) == 1
    assert errors[0].path == "amount_usd"
    assert "number" in errors[0].message
    assert "string" in errors[0].message


def test_non_object_root():
    """A non-dict root argument is rejected."""
    schema = {"type": "object"}
    errors = validate_arguments("not an object", schema)
    assert len(errors) == 1
    assert "object" in errors[0].message


def test_additional_properties_disallowed():
    """Additional properties are rejected when disabled."""
    schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
        "additionalProperties": False,
    }
    errors = validate_arguments({"city": "北京", "extra": 1}, schema)
    assert len(errors) == 1
    assert errors[0].path == "extra"
    assert "additional" in errors[0].message


def test_multiple_errors():
    """Multiple independent errors are all reported."""
    schema = {
        "type": "object",
        "properties": {
            "amount_usd": {"type": "number"},
            "rate": {"type": "number"},
        },
        "required": ["amount_usd", "rate"],
    }
    errors = validate_arguments({"amount_usd": "1000"}, schema)
    paths = {e.path for e in errors}
    assert "amount_usd" in paths
    assert "rate" in paths
