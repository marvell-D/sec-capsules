from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from sec_capsules.core.models import estimate_tokens
from sec_capsules.core.paths import RECIPES_ROOT
from sec_capsules.core.runner import CapsuleRunner


SUCCESSFUL_STATUSES = {"dry_run", "replayed", "succeeded"}


def load_recipe(recipe_id_or_path: str) -> dict[str, Any]:
    path = Path(recipe_id_or_path)
    if not path.exists():
        path = RECIPES_ROOT / f"{recipe_id_or_path}.yml"
    if not path.exists():
        raise FileNotFoundError(f"recipe not found: {recipe_id_or_path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_recipe(
    recipe_id_or_path: str,
    *,
    target: str,
    scope_file: str | Path,
    profile: str = "safe",
    arguments_by_step: dict[str, dict[str, Any]] | None = None,
    execute: bool = False,
    fixtures: dict[str, str] | None = None,
    approval_file: str | Path | None = None,
    runs_dir: str | Path = "runs",
    token_budget: int = 800,
    timeout: int = 120,
) -> dict[str, Any]:
    recipe = load_recipe(recipe_id_or_path)
    ordered_steps = order_steps(recipe.get("steps", []))
    runner = CapsuleRunner(runs_dir=runs_dir)
    fixtures = fixtures or {}
    arguments_by_step = arguments_by_step or {}
    step_ids = {str(step["id"]) for step in ordered_steps}
    unknown_argument_steps = sorted(set(arguments_by_step) - step_ids)
    if unknown_argument_steps:
        raise ValueError(
            "arguments_by_step references unknown recipe steps: "
            + ", ".join(unknown_argument_steps)
        )
    entries: list[dict[str, Any]] = []
    completed: dict[str, dict[str, Any]] = {}

    for step in ordered_steps:
        step_id = str(step["id"])
        dependencies = [str(value) for value in step.get("depends_on", [])]
        failed_dependencies = [
            dependency
            for dependency in dependencies
            if completed[dependency]["status"] not in SUCCESSFUL_STATUSES
        ]
        if failed_dependencies:
            entry = {
                "step_id": step_id,
                "capsule_id": step["capsule"],
                "depends_on": dependencies,
                "status": "skipped",
                "reason": f"dependency did not succeed: {', '.join(failed_dependencies)}",
            }
        else:
            result = runner.run(
                str(step["capsule"]),
                target=target,
                scope_file=scope_file,
                profile=str(step.get("profile", profile)),
                arguments=arguments_by_step.get(step_id),
                execute=execute,
                fixture=fixtures.get(str(step["capsule"])),
                approval_file=approval_file,
                token_budget=token_budget,
                timeout=timeout,
            )
            entry = {
                "step_id": step_id,
                "capsule_id": result.capsule_id,
                "run_id": result.run_id,
                "depends_on": dependencies,
                "status": result.status,
                "arguments": result.arguments,
                "argument_sources": result.argument_sources,
                "observation": result.observation,
                "artifact_refs": [
                    f"artifact://{result.run_id}/artifacts/{Path(artifact.path).name}"
                    for artifact in result.artifacts
                ],
            }
        completed[step_id] = entry
        entries.append(entry)

    summary = {
        "run_count": sum(1 for entry in entries if entry["status"] != "skipped"),
        "skipped_count": sum(1 for entry in entries if entry["status"] == "skipped"),
        "finding_count": sum(
            len(entry.get("observation", {}).get("top_findings", [])) for entry in entries
        ),
        "endpoint_count": sum(
            len(entry.get("observation", {}).get("new_endpoints", [])) for entry in entries
        ),
    }
    combined = {
        "type": "recipe_run.v1",
        "recipe_id": recipe.get("id", recipe_id_or_path),
        "target": target,
        "steps": entries,
        "summary": summary,
        "observation": build_recipe_observation(recipe.get("id", recipe_id_or_path), entries, token_budget),
    }

    out_dir = Path(runs_dir) / f"recipe_{combined['recipe_id']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "recipe_run.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "observation.json").write_text(
        json.dumps(combined["observation"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return combined


def order_steps(raw_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps: dict[str, dict[str, Any]] = {}
    original_order: list[str] = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict) or not raw_step.get("capsule"):
            raise ValueError(f"recipe step {index} must define a capsule")
        step_id = str(raw_step.get("id") or raw_step["capsule"])
        if step_id in steps:
            raise ValueError(f"recipe contains duplicate step id: {step_id}")
        dependencies = raw_step.get("depends_on", [])
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        step = {**raw_step, "id": step_id, "depends_on": list(dependencies)}
        steps[step_id] = step
        original_order.append(step_id)

    for step in steps.values():
        for dependency in step["depends_on"]:
            if dependency not in steps:
                raise ValueError(f"recipe step {step['id']} depends on unknown step {dependency}")

    ordered: list[dict[str, Any]] = []
    remaining = set(original_order)
    while remaining:
        ready = [
            step_id
            for step_id in original_order
            if step_id in remaining and all(dependency not in remaining for dependency in steps[step_id]["depends_on"])
        ]
        if not ready:
            raise ValueError("recipe dependency graph contains a cycle")
        for step_id in ready:
            ordered.append(steps[step_id])
            remaining.remove(step_id)
    return ordered


def build_recipe_observation(recipe_id: str, entries: list[dict[str, Any]], token_budget: int) -> dict[str, Any]:
    steps = [
        {
            "step_id": entry["step_id"],
            "capsule_id": entry["capsule_id"],
            "status": entry["status"],
            "run_id": entry.get("run_id"),
            "summary": entry.get("observation", {}).get("summary"),
        }
        for entry in entries
    ]
    packet = {
        "type": "recipe_observation_packet.v1",
        "recipe_id": recipe_id,
        "steps": steps,
        "hidden_from_model": {
            "raw_artifacts": True,
            "structured_run_payloads": True,
            "artifact_drilldown_required": True,
        },
    }
    while estimate_tokens(packet) > token_budget and packet["steps"]:
        packet["steps"].pop()
    packet["budget"] = {
        "requested_tokens": token_budget,
        "estimated_tokens": estimate_tokens(packet),
        "within_budget": estimate_tokens(packet) <= token_budget,
    }
    return packet
