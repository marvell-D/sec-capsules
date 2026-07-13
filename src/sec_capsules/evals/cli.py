from __future__ import annotations

import argparse
import json

from sec_capsules.evals.harness import benchmark_planner, grade_candidate, load_data


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

    args = parser.parse_args(argv)
    if args.command == "grade":
        result = grade_candidate(load_data(args.scenario), load_data(args.candidate))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["passed"] else 1

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
