from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sec_capsules.core.artifacts import ArtifactStore
from sec_capsules.core.exporters import export_markdown
from sec_capsules.core.recipe import run_recipe
from sec_capsules.core.registry import CapsuleRegistry, capsule_to_public_dict
from sec_capsules.core.runner import CapsuleRunner


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover - CLI safety net
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sec-capsules")
    parser.add_argument("--runs-dir", default="runs", help="Directory for run artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List built-in capsules")
    list_p.set_defaults(func=cmd_list)

    describe_p = sub.add_parser("describe", help="Describe a capsule")
    describe_p.add_argument("capsule_id")
    describe_p.add_argument("--level", choices=["brief", "usage", "full"], default="brief")
    describe_p.set_defaults(func=cmd_describe)

    search_p = sub.add_parser("search", help="Search capsules")
    search_p.add_argument("query", nargs="?")
    search_p.add_argument("--stage")
    search_p.add_argument("--risk-level")
    search_p.set_defaults(func=cmd_search)

    doctor_p = sub.add_parser("doctor", help="Check required external tools")
    doctor_p.add_argument("capsule_id", nargs="?")
    doctor_p.add_argument("--require", action="store_true", help="Exit non-zero when a required tool is unavailable")
    doctor_p.set_defaults(func=cmd_doctor)

    plan_p = sub.add_parser("plan", help="Create a safe command plan")
    plan_p.add_argument("capsule_id")
    plan_p.add_argument("--target", required=True)
    plan_p.add_argument("--profile", default="safe")
    plan_p.add_argument("--arguments-json", default="{}", help="Agent-style semantic arguments as a JSON object")
    plan_p.add_argument("--scope", help="Accepted for CLI symmetry; plan does not execute")
    plan_p.set_defaults(func=cmd_plan)

    run_p = sub.add_parser("run", help="Run or replay a capsule")
    run_p.add_argument("capsule_id")
    run_p.add_argument("--target", required=True)
    run_p.add_argument("--scope", required=True)
    run_p.add_argument("--profile", default="safe")
    run_p.add_argument("--arguments-json", default="{}", help="Agent-style semantic arguments as a JSON object")
    run_p.add_argument("--fixture")
    run_p.add_argument("--approval-file", help="Operator approval record required by some profiles")
    run_p.add_argument("--execute", action="store_true", help="Actually execute the external tool")
    run_p.add_argument("--budget", type=int, default=800)
    run_p.add_argument("--timeout", type=int, default=120)
    run_p.add_argument("--max-output-bytes", type=int)
    run_p.add_argument("--runs-dir", default=argparse.SUPPRESS, help="Directory for run artifacts")
    run_p.set_defaults(func=cmd_run)

    recipe_p = sub.add_parser("recipe", help="Recipe commands")
    recipe_sub = recipe_p.add_subparsers(dest="recipe_command", required=True)
    recipe_run_p = recipe_sub.add_parser("run", help="Run a deterministic recipe")
    recipe_run_p.add_argument("recipe_id")
    recipe_run_p.add_argument("--target", required=True)
    recipe_run_p.add_argument("--scope", required=True)
    recipe_run_p.add_argument("--profile", default="safe")
    recipe_run_p.add_argument(
        "--arguments-by-step-json",
        default="{}",
        help="Semantic arguments keyed by recipe step id",
    )
    recipe_run_p.add_argument("--execute", action="store_true")
    recipe_run_p.add_argument("--fixture", action="append", default=[], help="capsule=path")
    recipe_run_p.add_argument("--approval-file")
    recipe_run_p.add_argument("--budget", type=int, default=800)
    recipe_run_p.add_argument("--timeout", type=int, default=120)
    recipe_run_p.add_argument("--runs-dir", default=argparse.SUPPRESS, help="Directory for run artifacts")
    recipe_run_p.set_defaults(func=cmd_recipe_run)

    observe_p = sub.add_parser("observe", help="Print an existing run observation")
    observe_p.add_argument("run_id")
    observe_p.add_argument("--runs-dir", default=argparse.SUPPRESS, help="Directory for run artifacts")
    observe_p.set_defaults(func=cmd_observe)

    artifact_p = sub.add_parser("artifact", help="Artifact commands")
    artifact_sub = artifact_p.add_subparsers(dest="artifact_command", required=True)
    artifact_get_p = artifact_sub.add_parser("get", help="Print a bounded artifact snippet")
    artifact_get_p.add_argument("artifact_ref")
    artifact_get_p.add_argument("--start-line", type=int)
    artifact_get_p.add_argument("--end-line", type=int)
    artifact_get_p.add_argument("--max-lines", type=int, default=200)
    artifact_get_p.add_argument("--max-chars", type=int, default=16_000)
    artifact_get_p.add_argument("--runs-dir", default=argparse.SUPPRESS, help="Directory for run artifacts")
    artifact_get_p.set_defaults(func=cmd_artifact_get)

    export_p = sub.add_parser("export", help="Export a run")
    export_p.add_argument("run_id")
    export_p.add_argument("--format", choices=["markdown"], default="markdown")
    export_p.add_argument("--runs-dir", default=argparse.SUPPRESS, help="Directory for run artifacts")
    export_p.set_defaults(func=cmd_export)
    return parser


def cmd_list(args: argparse.Namespace) -> int:
    registry = CapsuleRegistry()
    for capsule in registry.list():
        print(f"{capsule.id}\t{capsule.category}\t{capsule.risk_level}\t{capsule.summary}")
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    registry = CapsuleRegistry()
    print_json(capsule_to_public_dict(registry.get(args.capsule_id), args.level))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    registry = CapsuleRegistry()
    print_json(
        [
            capsule_to_public_dict(capsule, "brief")
            for capsule in registry.search(args.query, args.stage, args.risk_level)
        ]
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    runner = CapsuleRunner(runs_dir=args.runs_dir)
    reports = runner.doctor(args.capsule_id)
    print_json(reports)
    if args.require and any(not report["health"]["available"] for report in reports):
        return 1
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    runner = CapsuleRunner(runs_dir=args.runs_dir)
    print_json(
        runner.plan(
            args.capsule_id,
            target=args.target,
            profile=args.profile,
            arguments=parse_json_object(args.arguments_json, "--arguments-json"),
        )
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    runner = CapsuleRunner(runs_dir=args.runs_dir)
    result = runner.run(
        args.capsule_id,
        target=args.target,
        scope_file=args.scope,
        profile=args.profile,
        arguments=parse_json_object(args.arguments_json, "--arguments-json"),
        execute=args.execute,
        fixture=args.fixture,
        approval_file=args.approval_file,
        token_budget=args.budget,
        timeout=args.timeout,
        max_output_bytes=args.max_output_bytes,
    )
    print_json(
        {
            "run_id": result.run_id,
            "observation": result.observation,
            "artifacts": [artifact.to_dict() for artifact in result.artifacts],
            "dry_run": result.dry_run,
        }
    )
    return 0 if result.status in {"dry_run", "replayed", "succeeded"} else 1


def cmd_recipe_run(args: argparse.Namespace) -> int:
    fixtures = {}
    for item in args.fixture:
        if "=" not in item:
            raise ValueError("--fixture must be in capsule=path form")
        capsule_id, path = item.split("=", 1)
        fixtures[capsule_id] = path
    result = run_recipe(
        args.recipe_id,
        target=args.target,
        scope_file=args.scope,
        profile=args.profile,
        arguments_by_step=parse_nested_json_object(
            args.arguments_by_step_json,
            "--arguments-by-step-json",
        ),
        execute=args.execute,
        fixtures=fixtures,
        approval_file=args.approval_file,
        runs_dir=args.runs_dir,
        token_budget=args.budget,
        timeout=args.timeout,
    )
    print_json(result)
    failed = [step for step in result["steps"] if step["status"] not in {"dry_run", "replayed", "succeeded"}]
    return 0 if not failed else 1


def cmd_observe(args: argparse.Namespace) -> int:
    path = Path(args.runs_dir) / args.run_id / "observation.json"
    print(path.read_text(encoding="utf-8"))
    return 0


def cmd_artifact_get(args: argparse.Namespace) -> int:
    store = ArtifactStore(Path(args.runs_dir))
    print_json(
        store.read_ref(
            args.artifact_ref,
            start_line=args.start_line,
            end_line=args.end_line,
            max_lines=args.max_lines,
            max_chars=args.max_chars,
        )
    )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    run_dir = Path(args.runs_dir) / args.run_id
    if args.format == "markdown":
        print(export_markdown(run_dir))
    return 0


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def parse_json_object(value: str, option_name: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{option_name} must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{option_name} must contain a JSON object")
    return parsed


def parse_nested_json_object(value: str, option_name: str) -> dict[str, dict]:
    parsed = parse_json_object(value, option_name)
    invalid = sorted(key for key, item in parsed.items() if not isinstance(item, dict))
    if invalid:
        raise ValueError(f"{option_name} values must be JSON objects: {', '.join(invalid)}")
    return parsed


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
