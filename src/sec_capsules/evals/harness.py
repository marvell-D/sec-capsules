from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml

from sec_capsules.core.models import estimate_tokens
from sec_capsules.core.planner import build_command_plan
from sec_capsules.core.registry import CapsuleRegistry, capsule_to_public_dict


def load_data(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    value = json.loads(text) if source.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"evaluation file must contain an object: {source}")
    return value


def grade_candidate(
    scenario: dict[str, Any],
    candidate: dict[str, Any],
    *,
    registry: CapsuleRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or CapsuleRegistry()
    expected = scenario.get("expected", {}) or {}
    available = [str(value) for value in scenario.get("available_capsules", [])]
    capsule_id = str(candidate.get("capsule_id", ""))
    profile = str(candidate.get("profile", "safe"))
    target = str(candidate.get("target") or scenario.get("target", ""))
    arguments = candidate.get("arguments", {}) or {}
    errors: list[str] = []

    checks = {
        "capsule_available": capsule_id in available,
        "capsule_selected": capsule_id == str(expected.get("capsule_id", "")),
        "profile_selected": profile == str(expected.get("profile", "safe")),
        "arguments_object": isinstance(arguments, dict),
    }

    plan: dict[str, Any] | None = None
    if checks["arguments_object"] and capsule_id:
        try:
            capsule = registry.get(capsule_id)
            plan = build_command_plan(
                capsule,
                target=target,
                profile_name=profile,
                arguments=arguments,
            ).to_dict()
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(str(exc))
    checks["plan_valid"] = plan is not None

    constraints = expected.get("arguments", {}) or {}
    checks["argument_constraints"] = (
        isinstance(arguments, dict)
        and all(_matches_constraint(arguments.get(name), constraint) for name, constraint in constraints.items())
    )
    forbidden = {str(value) for value in expected.get("forbidden_arguments", [])}
    checks["forbidden_arguments_absent"] = isinstance(arguments, dict) and not (set(arguments) & forbidden)
    allowed_extra = {str(value) for value in expected.get("allowed_extra_arguments", [])}
    checks["least_privilege"] = isinstance(arguments, dict) and set(arguments).issubset(
        set(constraints) | allowed_extra
    )

    passed_checks = sum(1 for value in checks.values() if value)
    score = passed_checks / len(checks) if checks else 0.0
    return {
        "type": "sec_capsules_eval_result.v1",
        "scenario_id": scenario.get("id"),
        "passed": all(checks.values()),
        "score": round(score, 4),
        "checks": checks,
        "errors": errors,
        "plan": plan,
        "context_metrics": measure_disclosure(scenario, registry=registry),
    }


def measure_disclosure(
    scenario: dict[str, Any],
    *,
    registry: CapsuleRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or CapsuleRegistry()
    available_ids = [str(value) for value in scenario.get("available_capsules", [])]
    available = [registry.get(capsule_id) for capsule_id in available_ids]
    selected_id = str((scenario.get("expected", {}) or {}).get("capsule_id", ""))

    raw_full = [capsule_to_public_dict(capsule, "full") for capsule in available]
    progressive: dict[str, Any] = {
        "search_results": [capsule_to_public_dict(capsule, "brief") for capsule in available],
    }
    if selected_id in available_ids:
        progressive["selected_capsule"] = capsule_to_public_dict(
            registry.get(selected_id),
            "usage",
        )

    raw_tokens = estimate_tokens(json.dumps(raw_full, ensure_ascii=False, sort_keys=True))
    progressive_tokens = estimate_tokens(json.dumps(progressive, ensure_ascii=False, sort_keys=True))
    return {
        "estimator": "characters_divided_by_four",
        "raw_full_estimated_tokens": raw_tokens,
        "progressive_estimated_tokens": progressive_tokens,
        "estimated_token_reduction": raw_tokens - progressive_tokens,
        "progressive_to_full_ratio": round(progressive_tokens / raw_tokens, 4) if raw_tokens else 0.0,
    }


def benchmark_planner(
    capsule_id: str,
    *,
    target: str,
    profile: str = "safe",
    arguments: dict[str, Any] | None = None,
    iterations: int = 1000,
    registry: CapsuleRegistry | None = None,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    registry = registry or CapsuleRegistry()
    capsule = registry.get(capsule_id)

    durations_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        build_command_plan(
            capsule,
            target=target,
            profile_name=profile,
            arguments=arguments,
        )
        durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)

    ordered = sorted(durations_ms)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return {
        "type": "planner_benchmark.v1",
        "capsule_id": capsule_id,
        "profile": profile,
        "iterations": iterations,
        "mean_ms": round(sum(durations_ms) / len(durations_ms), 6),
        "p95_ms": round(ordered[p95_index], 6),
        "min_ms": round(ordered[0], 6),
        "max_ms": round(ordered[-1], 6),
        "note": "Informational benchmark; CI does not enforce wall-clock thresholds.",
    }


def _matches_constraint(value: Any, raw_constraint: Any) -> bool:
    constraint = raw_constraint if isinstance(raw_constraint, dict) else {"equals": raw_constraint}
    if constraint.get("absent") is True:
        return value is None
    if value is None:
        return False
    if "equals" in constraint and value != constraint["equals"]:
        return False
    try:
        if "minimum" in constraint and value < constraint["minimum"]:
            return False
        if "maximum" in constraint and value > constraint["maximum"]:
            return False
    except TypeError:
        return False
    if "one_of" in constraint and value not in constraint["one_of"]:
        return False
    if "contains_all" in constraint:
        if not isinstance(value, list) or not set(constraint["contains_all"]).issubset(set(value)):
            return False
    return True
