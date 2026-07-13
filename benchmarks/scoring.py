from __future__ import annotations

from typing import Any


def score_trace(trace: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    answer = trace.get("final_answer", {})
    results = [_score_milestone(item, answer) for item in scenario.get("milestones", [])]
    passed = sum(result["passed"] for result in results)
    total = len(results)
    evidence_refs = _strings(answer.get("evidence_refs", []))
    return {
        "passed": total > 0 and passed == total,
        "milestones_passed": passed,
        "milestones_total": total,
        "milestone_score": round(passed / total, 4) if total else 0.0,
        "evidence_coverage": round(min(len(evidence_refs), total) / total, 4) if total else 0.0,
        "milestones": results,
    }


def _score_milestone(milestone: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    kind = str(milestone.get("type", ""))
    expected = milestone.get("expected")
    observed: Any = None
    passed = False

    if kind == "asset_value_contains":
        observed = {
            str(item.get("value")) if isinstance(item, dict) else str(item)
            for item in answer.get("assets", [])
        }
        passed = str(expected) in observed
    elif kind == "service_ports_contains":
        observed = {
            int(item["port"])
            for item in answer.get("services", [])
            if isinstance(item, dict) and str(item.get("port", "")).isdigit()
        }
        expected_ports = {int(value) for value in expected or []}
        passed = expected_ports <= observed
    elif kind == "endpoint_urls_contains":
        observed = {
            str(item.get("url")) if isinstance(item, dict) else str(item)
            for item in answer.get("endpoints", [])
        }
        passed = set(str(value) for value in expected or []) <= observed
    elif kind == "evidence_refs_min":
        observed = len(_strings(answer.get("evidence_refs", [])))
        passed = observed >= int(expected or 0)

    return {
        "id": milestone.get("id"),
        "type": kind,
        "passed": passed,
        "expected": expected,
        "observed": sorted(observed) if isinstance(observed, set) else observed,
    }


def _strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if isinstance(value, str) and value]
