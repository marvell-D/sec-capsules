from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sec_capsules.core.models import Capsule


SUPPORTED_TYPES = {"array", "boolean", "integer", "number", "string"}


@dataclass(frozen=True)
class ResolvedArguments:
    values: dict[str, Any]
    sources: dict[str, str]


def resolve_arguments(
    capsule: Capsule,
    profile_name: str,
    provided: dict[str, Any] | None = None,
) -> ResolvedArguments:
    profile = capsule.profile(profile_name)
    schema = capsule.raw.get("input_schema", {})
    if not isinstance(schema, dict):
        raise ValueError(f"capsule {capsule.id} input_schema must be an object")
    properties = schema.get("properties", {})
    defaults = profile.get("defaults", {})
    allowed_values = profile.get("allowed_arguments", list(defaults) if isinstance(defaults, dict) else [])
    provided = {} if provided is None else provided

    if not isinstance(properties, dict):
        raise ValueError(f"capsule {capsule.id} input_schema.properties must be an object")
    if not isinstance(defaults, dict):
        raise ValueError(f"capsule {capsule.id} profile {profile_name} defaults must be an object")
    if not isinstance(allowed_values, list) or not all(isinstance(name, str) for name in allowed_values):
        raise ValueError(
            f"capsule {capsule.id} profile {profile_name} allowed_arguments must be a string list"
        )
    if not isinstance(provided, dict):
        raise ValueError("arguments must be an object")
    allowed = set(allowed_values)

    unknown_defaults = sorted(set(defaults) - set(properties))
    if unknown_defaults:
        raise ValueError(
            f"capsule {capsule.id} profile {profile_name} has defaults without schemas: "
            f"{', '.join(unknown_defaults)}"
        )

    unknown_allowed = sorted(allowed - set(properties))
    if unknown_allowed:
        raise ValueError(
            f"capsule {capsule.id} profile {profile_name} allows unknown arguments: "
            f"{', '.join(unknown_allowed)}"
        )

    unknown = sorted(set(provided) - set(properties))
    if unknown:
        raise ValueError(f"unknown arguments for {capsule.id}: {', '.join(unknown)}")

    disallowed = sorted(set(provided) - allowed)
    if disallowed:
        raise ValueError(
            f"arguments are not enabled by profile {profile_name}: {', '.join(disallowed)}"
        )

    for name in provided:
        if properties[name].get("x-agent-settable", True) is not True:
            raise ValueError(f"argument {name!r} is runtime-controlled and cannot be set by an agent")

    values = deepcopy(defaults)
    values.update(deepcopy(provided))
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(name, str) for name in required):
        raise ValueError(f"capsule {capsule.id} input_schema.required must be a string list")
    missing = [str(name) for name in required if name not in values]
    if missing:
        raise ValueError(f"missing required arguments for {capsule.id}: {', '.join(sorted(missing))}")

    for name, value in values.items():
        validate_value(name, value, properties[name])

    sources = {
        name: "agent" if name in provided else "profile_default"
        for name in values
    }
    return ResolvedArguments(values=values, sources=sources)


def validate_input_schema(capsule: Capsule) -> None:
    schema = capsule.raw.get("input_schema")
    if not isinstance(schema, dict):
        raise ValueError(f"capsule {capsule.id} input_schema must be an object")
    if schema.get("type") != "object":
        raise ValueError(f"capsule {capsule.id} input_schema type must be object")
    if "additionalProperties" not in schema or schema["additionalProperties"] is not False:
        raise ValueError(f"capsule {capsule.id} input_schema must reject additional properties")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"capsule {capsule.id} input_schema.properties must be an object")
    for name, spec in properties.items():
        if not isinstance(spec, dict):
            raise ValueError(f"argument schema {name!r} must be an object")
        value_type = spec.get("type")
        if value_type not in SUPPORTED_TYPES:
            raise ValueError(f"argument {name!r} uses unsupported type {value_type!r}")
        if not str(spec.get("description", "")).strip():
            raise ValueError(f"argument {name!r} must include a description")
        if "x-agent-settable" in spec and not isinstance(spec["x-agent-settable"], bool):
            raise ValueError(f"argument {name!r} x-agent-settable must be boolean")
        if value_type == "array":
            item_spec = spec.get("items")
            if not isinstance(item_spec, dict) or item_spec.get("type") not in SUPPORTED_TYPES:
                raise ValueError(f"array argument {name!r} must define a supported items type")

    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(name, str) for name in required):
        raise ValueError(f"capsule {capsule.id} input_schema.required must be a string list")
    unknown_required = sorted(set(required) - set(properties))
    if unknown_required:
        raise ValueError(
            f"capsule {capsule.id} requires unknown arguments: {', '.join(unknown_required)}"
        )

    for profile_name in capsule.raw.get("profiles", {}):
        resolve_arguments(capsule, str(profile_name))


def validate_value(name: str, value: Any, spec: dict[str, Any]) -> None:
    value_type = spec.get("type")
    if value_type not in SUPPORTED_TYPES:
        raise ValueError(f"argument {name!r} uses unsupported type {value_type!r}")

    valid_type = {
        "array": lambda item: isinstance(item, list),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "string": lambda item: isinstance(item, str),
    }[value_type]
    if not valid_type(value):
        raise ValueError(f"argument {name!r} must be of type {value_type}")

    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(f"argument {name!r} must be one of {spec['enum']!r}")

    if value_type in {"integer", "number"}:
        if "minimum" in spec and value < spec["minimum"]:
            raise ValueError(f"argument {name!r} must be >= {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise ValueError(f"argument {name!r} must be <= {spec['maximum']}")

    if value_type == "string":
        if "minLength" in spec and len(value) < spec["minLength"]:
            raise ValueError(f"argument {name!r} is shorter than minLength {spec['minLength']}")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            raise ValueError(f"argument {name!r} is longer than maxLength {spec['maxLength']}")

    if value_type == "array":
        if "minItems" in spec and len(value) < spec["minItems"]:
            raise ValueError(f"argument {name!r} has fewer than {spec['minItems']} items")
        if "maxItems" in spec and len(value) > spec["maxItems"]:
            raise ValueError(f"argument {name!r} has more than {spec['maxItems']} items")
        if spec.get("uniqueItems") and len({repr(item) for item in value}) != len(value):
            raise ValueError(f"argument {name!r} must contain unique items")
        item_spec = spec.get("items", {}) or {}
        for index, item in enumerate(value):
            validate_value(f"{name}[{index}]", item, item_spec)


def template_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(template_value(item) for item in value)
    return str(value)
