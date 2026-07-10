from __future__ import annotations

import os
from pathlib import Path

from sec_capsules.core.artifacts import ArtifactStore
from sec_capsules.core.exporters import export_markdown
from sec_capsules.core.recipe import run_recipe as core_run_recipe
from sec_capsules.core.registry import CapsuleRegistry, capsule_to_public_dict
from sec_capsules.core.runner import CapsuleRunner


def _runs_dir() -> Path:
    return Path(os.environ.get("SEC_CAPSULES_RUNS_DIR", "runs"))


def _require_mcp_execution_enabled(execute: bool) -> None:
    if execute and os.environ.get("SEC_CAPSULES_ALLOW_MCP_EXECUTE") != "1":
        raise PermissionError("MCP execution is disabled; set SEC_CAPSULES_ALLOW_MCP_EXECUTE=1 for an operator-controlled server")


def _run_dir(run_id: str) -> Path:
    if not run_id or run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
        raise ValueError("run_id must be a single path component")
    root = _runs_dir().resolve()
    candidate = (root / run_id).resolve()
    if candidate.parent != root:
        raise ValueError("run_id escapes the configured runs directory")
    return candidate


def search_capsules(query: str = "", stage: str | None = None, risk_level: str | None = None) -> list[dict]:
    registry = CapsuleRegistry()
    return [
        capsule_to_public_dict(capsule, "brief")
        for capsule in registry.search(query=query, stage=stage, risk_level=risk_level)
    ]


def get_capsule(capsule_id: str, detail_level: str = "usage") -> dict:
    registry = CapsuleRegistry()
    return capsule_to_public_dict(registry.get(capsule_id), detail_level)


def run_capsule(
    capsule_id: str,
    target: str,
    scope: str,
    profile: str = "safe",
    fixture: str | None = None,
    execute: bool = False,
    approval_file: str | None = None,
    budget: int = 800,
    timeout: int = 120,
) -> dict:
    _require_mcp_execution_enabled(execute)
    runner = CapsuleRunner(runs_dir=_runs_dir())
    return runner.run(
        capsule_id,
        target=target,
        scope_file=scope,
        profile=profile,
        fixture=fixture,
        execute=execute,
        approval_file=approval_file,
        token_budget=budget,
        timeout=timeout,
    ).to_dict()


def run_recipe(
    recipe_id: str,
    target: str,
    scope: str,
    profile: str = "safe",
    execute: bool = False,
    approval_file: str | None = None,
    budget: int = 800,
    timeout: int = 120,
) -> dict:
    _require_mcp_execution_enabled(execute)
    return core_run_recipe(
        recipe_id,
        target=target,
        scope_file=scope,
        profile=profile,
        execute=execute,
        approval_file=approval_file,
        runs_dir=_runs_dir(),
        token_budget=budget,
        timeout=timeout,
    )


def get_observation(run_id: str) -> dict:
    path = _run_dir(run_id) / "observation.json"
    if not path.is_file():
        raise FileNotFoundError(f"run observation does not exist: {run_id}")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def get_artifact(
    artifact_ref: str,
    start_line: int | None = None,
    end_line: int | None = None,
    max_lines: int = 200,
    max_chars: int = 16_000,
) -> dict:
    return ArtifactStore(_runs_dir()).read_ref(
        artifact_ref,
        start_line=start_line,
        end_line=end_line,
        max_lines=max_lines,
        max_chars=max_chars,
    )


def export_run(run_id: str) -> dict:
    run_dir = _run_dir(run_id)
    if not (run_dir / "run.json").is_file():
        raise FileNotFoundError(f"run does not exist: {run_id}")
    return {"run_id": run_id, "format": "markdown", "content": export_markdown(run_dir)}


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - optional dependency
        raise SystemExit("Install MCP support with: python -m pip install 'sec-capsules[mcp]'") from exc

    mcp = FastMCP("sec-capsules")
    mcp.tool()(search_capsules)
    mcp.tool()(get_capsule)
    mcp.tool()(run_capsule)
    mcp.tool()(run_recipe)
    mcp.tool()(get_observation)
    mcp.tool()(get_artifact)
    mcp.tool()(export_run)
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
