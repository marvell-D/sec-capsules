from __future__ import annotations

import argparse
import json

from sec_capsules.evals.harness import benchmark_planner, grade_candidate, load_data
from sec_capsules.evals.providers.siliconflow import (
    DEFAULT_BASE_URL,
    SiliconFlowClient,
    evaluate_scenario,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sec_capsules.evals.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    grade = sub.add_parser("grade", help="Grade one provider-neutral invocation candidate")
    grade.add_argument("--scenario", required=True)
    grade.add_argument("--candidate", required=True)

    benchmark = sub.add_parser("benchmark", help="Measure planner overhead without an agent")
    benchmark.add_argument("--capsule", required=True)
    benchmark.add_argument("--target", required=True)
    benchmark.add_argument("--profile", default="safe")
    benchmark.add_argument("--arguments-json", default="{}")
    benchmark.add_argument("--iterations", type=int, default=1000)

    siliconflow_models = sub.add_parser(
        "siliconflow-models",
        help="List chat models available to the configured SiliconFlow account",
    )
    siliconflow_models.add_argument("--base-url", default=DEFAULT_BASE_URL)
    siliconflow_models.add_argument("--timeout", type=float, default=60.0)

    siliconflow_grade = sub.add_parser(
        "siliconflow-grade",
        help="Run a two-stage live model evaluation without adding an agent loop",
    )
    siliconflow_grade.add_argument("--scenario", required=True)
    siliconflow_grade.add_argument("--model")
    siliconflow_grade.add_argument("--base-url", default=DEFAULT_BASE_URL)
    siliconflow_grade.add_argument("--timeout", type=float, default=60.0)

    args = parser.parse_args(argv)
    if args.command == "grade":
        result = grade_candidate(load_data(args.scenario), load_data(args.candidate))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["passed"] else 1

    if args.command == "siliconflow-models":
        client = SiliconFlowClient(base_url=args.base_url, timeout=args.timeout)
        models = client.list_chat_models()
        print(json.dumps({"models": models}, indent=2, ensure_ascii=False))
        return 0

    if args.command == "siliconflow-grade":
        client = SiliconFlowClient(base_url=args.base_url, timeout=args.timeout)
        result = evaluate_scenario(
            load_data(args.scenario),
            client=client,
            model=args.model,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["grade"]["passed"] else 1

    arguments = json.loads(args.arguments_json)
    if not isinstance(arguments, dict):
        parser.error("--arguments-json must contain a JSON object")
    result = benchmark_planner(
        args.capsule,
        target=args.target,
        profile=args.profile,
        arguments=arguments,
        iterations=args.iterations,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
