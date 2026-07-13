from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from benchmarks.adapters import CapsuleToolAdapter, RawToolAdapter
from benchmarks.agent import run_reference_agent
from benchmarks.providers import SiliconFlowAgentProvider
from benchmarks.reporting import build_report, load_traces, render_markdown
from benchmarks.scoring import score_trace
from sec_capsules.evals.providers.siliconflow import SiliconFlowClient


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "report":
        return _report(args)
    parser.error("a command is required")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sec-Capsules reference Agent benchmark")
    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="run raw/capsule Agent trials")
    run.add_argument("--scenario", type=Path, required=True)
    run.add_argument("--variant", choices=["raw", "capsule", "both"], default="both")
    run.add_argument("--mode", choices=["replay", "live"], default="replay")
    run.add_argument("--model")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--output-dir", type=Path, default=Path("benchmark-reports/traces"))
    report = commands.add_parser("report", help="aggregate existing trace JSON files")
    report.add_argument("traces", nargs="+")
    report.add_argument("--json-output", type=Path, required=True)
    report.add_argument("--markdown-output", type=Path, required=True)
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    scenario_path = args.scenario.resolve()
    scenario = _load_scenario(scenario_path)
    client = SiliconFlowClient()
    model = client.choose_model(args.model)
    provider = SiliconFlowAgentProvider(client)
    variants = ["raw", "capsule"] if args.variant == "both" else [args.variant]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for repeat in range(1, args.repeats + 1):
        for variant in variants:
            runs_dir = args.output_dir / "artifacts" / variant
            adapter = (
                RawToolAdapter(
                    scenario,
                    scenario_path=scenario_path,
                    mode=args.mode,
                    runs_dir=runs_dir,
                )
                if variant == "raw"
                else CapsuleToolAdapter(
                    scenario,
                    scenario_path=scenario_path,
                    mode=args.mode,
                    runs_dir=runs_dir,
                )
            )
            trace = run_reference_agent(
                scenario,
                adapter=adapter,
                provider=provider,
                model=model,
                max_turns=int(scenario.get("limits", {}).get("max_turns", 6)),
                max_tokens=int(scenario.get("limits", {}).get("model_max_tokens", 768)),
            )
            trace["score"] = score_trace(trace, scenario)
            path = args.output_dir / f"{trace['trace_id']}-{variant}-r{repeat}.json"
            path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
            paths.append(str(path))
            print(path)

    traces = load_traces(paths)
    report = build_report(traces)
    json_path = args.output_dir / "report.json"
    markdown_path = args.output_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(markdown_path)
    return 0


def _report(args: argparse.Namespace) -> int:
    report = build_report(load_traces(args.traces))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    return 0


def _load_scenario(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError("benchmark scenario must contain an object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
