from __future__ import annotations

from typing import Any

from sec_capsules.core.models import estimate_tokens


def build_observation_packet(
    *,
    run_id: str,
    tool: str,
    structured: dict[str, Any],
    token_budget: int = 800,
    execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assets = list(structured.get("assets", []))
    findings = list(structured.get("findings", []))
    services = list(structured.get("services", []))
    endpoints = list(structured.get("endpoints", []))

    top_findings = [
        {
            "title": finding.get("title"),
            "severity": finding.get("severity"),
            "confidence": finding.get("confidence", "unknown"),
            "affected": finding.get("affected"),
            "evidence_ref": (finding.get("evidence_refs") or [None])[0],
        }
        for finding in findings[:5]
    ]

    packet = {
        "type": "observation_packet.v1",
        "run_id": run_id,
        "tool": tool,
        "execution": execution or {},
        "summary": summarize_counts(
            assets=assets,
            findings=findings,
            services=services,
            endpoints=endpoints,
        ),
        "top_findings": top_findings,
        "new_assets": assets[:8],
        "new_services": services[:8],
        "new_endpoints": [endpoint.get("url") for endpoint in endpoints[:12] if endpoint.get("url")],
        "recommended_next_actions": recommended_next_actions(findings, endpoints),
        "hidden_from_model": {
            "raw_output": True,
            "secrets_redacted": False,
            "artifact_drilldown_required": True,
        },
    }

    while estimate_tokens(packet) > token_budget and packet["new_endpoints"]:
        packet["new_endpoints"].pop()
    while estimate_tokens(packet) > token_budget and packet["new_services"]:
        packet["new_services"].pop()
    while estimate_tokens(packet) > token_budget and packet["new_assets"]:
        packet["new_assets"].pop()
    while estimate_tokens(packet) > token_budget and packet["top_findings"]:
        packet["top_findings"].pop()

    for optional_key in ("new_endpoints", "new_services", "new_assets", "top_findings"):
        if estimate_tokens(packet) <= token_budget:
            break
        if not packet[optional_key]:
            packet.pop(optional_key)

    packet["budget"] = {
        "requested_tokens": token_budget,
        "estimated_tokens": estimate_tokens(packet),
        "within_budget": estimate_tokens(packet) <= token_budget,
    }
    return packet


def summarize_counts(
    *,
    assets: list[dict],
    findings: list[dict],
    services: list[dict],
    endpoints: list[dict],
) -> str:
    parts = []
    if assets:
        parts.append(f"{len(assets)} asset(s)")
    if services:
        parts.append(f"{len(services)} service(s)")
    if endpoints:
        parts.append(f"{len(endpoints)} endpoint(s)")
    if findings:
        parts.append(f"{len(findings)} finding candidate(s)")
    if not parts:
        return "No structured security objects were produced. Raw output is preserved as artifacts."
    return f"Produced {', '.join(parts)}. Raw output is preserved as artifacts and hidden by default."


def recommended_next_actions(findings: list[dict], endpoints: list[dict]) -> list[str]:
    actions = []
    if findings:
        actions.extend(["inspect_evidence", "export_report"])
    if endpoints:
        actions.append("continue_endpoint_triage")
    if not actions:
        actions.append("review_raw_artifact_if_needed")
    return actions
