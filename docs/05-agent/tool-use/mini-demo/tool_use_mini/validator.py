"""Minimal JSON Schema validation for tool arguments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationError:
    """A single validation failure with a dotted path to the offending field."""

    path: str
    message: str


def _json_type_name(value: Any) -> str:
    """Return the JSON Schema type name for a Python value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _matches_type(value: Any, schema_type: Any) -> bool:
    """Check whether a value matches a JSON Schema type (or list of types)."""
    if isinstance(schema_type, list):
        return any(_matches_type(value, t) for t in schema_type)

    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "null":
        return value is None
    return False


def validate_arguments(
    arguments: Any,
    schema: Dict[str, Any],
    path: str = "",
) -> List[ValidationError]:
    """Validate ``arguments`` against a JSON Schema subset.

    Supports:
    - type checking for primitives and object/array/null
    - required properties
    - nested object properties
    - list of accepted types

    Returns a list of :class:`ValidationError`; an empty list means success.
    """
    errors: List[ValidationError] = []

    if not isinstance(arguments, dict):
        errors.append(ValidationError(path=path or "<root>", message="arguments must be an object"))
        return errors

    schema_type = schema.get("type")
    if schema_type is not None:
        if not _matches_type(arguments, schema_type):
            errors.append(
                ValidationError(
                    path=path or "<root>",
                    message=f"expected type {schema_type!r}, got {_json_type_name(arguments)!r}",
                )
            )
            return errors

    required = schema.get("required", [])
    for key in required:
        if key not in arguments:
            errors.append(ValidationError(path=f"{path}.{key}".lstrip("."), message="missing required field"))

    properties = schema.get("properties", {})
    for key, value in arguments.items():
        child_path = f"{path}.{key}".lstrip(".")
        if key not in properties:
            if not schema.get("additionalProperties", True):
                errors.append(ValidationError(path=child_path, message="additional property not allowed"))
            continue

        prop_schema = properties[key]
        prop_type = prop_schema.get("type")
        if prop_type is not None and not _matches_type(value, prop_type):
            errors.append(
                ValidationError(
                    path=child_path,
                    message=f"expected type {prop_type!r}, got {_json_type_name(value)!r}",
                )
            )
            continue

        if isinstance(value, dict) and prop_type == "object":
            errors.extend(validate_arguments(value, prop_schema, child_path))

    return errors
