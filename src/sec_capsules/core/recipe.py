from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from sec_capsules.core.paths import RECIPES_ROOT
from sec_capsules.core.runner import CapsuleRunner


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
    execute: bool = False,
    fixtures: dict[str, str] | None = None,
    runs_dir: str | Path = "runs",
    token_budget: int = 800,
) -> dict[str, Any]:
    recipe = load_recipe(recipe_id_or_path)
    runner = CapsuleRunner(runs_dir=runs_dir)
    results = []
    fixtures = fixtures or {}

    for step in recipe.get("steps", []):
        capsule_id = step.get("capsule")
        if not capsule_id:
            continue
        result = runner.run(
            capsule_id,
            target=target,
            scope_file=scope_file,
            profile=step.get("profile", profile),
            execute=execute,
            fixture=fixtures.get(capsule_id),
            token_budget=token_budget,
        )
        results.append(result.to_dict())

    combined = {
        "recipe_id": recipe.get("id", recipe_id_or_path),
        "target": target,
        "runs": results,
        "summary": {
            "run_count": len(results),
            "finding_count": sum(len(r["structured"].get("findings", [])) for r in results),
            "endpoint_count": sum(len(r["structured"].get("endpoints", [])) for r in results),
            "service_count": sum(len(r["structured"].get("services", [])) for r in results),
        },
    }

    out_dir = Path(runs_dir) / f"recipe_{combined['recipe_id']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "recipe_run.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return combined

