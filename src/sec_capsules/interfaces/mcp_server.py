from __future__ import annotations

from sec_capsules.core.recipe import run_recipe as core_run_recipe
from sec_capsules.core.registry import CapsuleRegistry, capsule_to_public_dict
from sec_capsules.core.runner import CapsuleRunner


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
    budget: int = 800,
) -> dict:
    runner = CapsuleRunner()
    return runner.run(
        capsule_id,
        target=target,
        scope_file=scope,
        profile=profile,
        fixture=fixture,
        execute=execute,
        token_budget=budget,
    ).to_dict()


def run_recipe(
    recipe_id: str,
    target: str,
    scope: str,
    profile: str = "safe",
    execute: bool = False,
    budget: int = 800,
) -> dict:
    return core_run_recipe(
        recipe_id,
        target=target,
        scope_file=scope,
        profile=profile,
        execute=execute,
        token_budget=budget,
    )


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
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

