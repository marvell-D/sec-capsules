from __future__ import annotations

import json
from collections import defaultdict
from statistics import median
from typing import Any


def build_report(traces: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        grouped[str(trace.get("variant", "unknown"))].append(trace)

    variants = {
        variant: _aggregate_variant(rows)
        for variant, rows in sorted(grouped.items())
    }
    comparison: dict[str, Any] = {}
    if "raw" in variants and "capsule" in variants:
        raw = variants["raw"]
        capsule = variants["capsule"]
        comparison = {
            "median_total_token_delta": (
                capsule["median_total_tokens"] - raw["median_total_tokens"]
            ),
            "median_model_visible_byte_reduction_ratio": _reduction_ratio(
                raw["median_model_visible_tool_bytes"],
                capsule["median_model_visible_tool_bytes"],
            ),
            "milestone_score_delta": round(
                capsule["mean_milestone_score"] - raw["mean_milestone_score"], 4
            ),
        }
    return {
        "type": "agent_benchmark_report.v1",
        "trace_count": len(traces),
        "variants": variants,
        "comparison": comparison,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Sec-Capsules Agent Benchmark",
        "",
        "| Variant | Runs | Success | Milestone score | Median tokens | Raw bytes | Model-visible bytes | Denials |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, row in report.get("variants", {}).items():
        lines.append(
            f"| {variant} | {row['runs']} | {row['success_rate']:.1%} | "
            f"{row['mean_milestone_score']:.3f} | {row['median_total_tokens']:.0f} | "
            f"{row['median_raw_tool_output_bytes']:.0f} | "
            f"{row['median_model_visible_tool_bytes']:.0f} | {row['policy_denials']} |"
        )
    comparison = report.get("comparison", {})
    if comparison:
        lines.extend(
            [
                "",
                "## Paired-direction summary",
                "",
                f"- Median total-token delta (capsule - raw): {comparison['median_total_token_delta']}",
                "- Median model-visible tool-byte reduction: "
                f"{comparison['median_model_visible_byte_reduction_ratio']:.1%}",
                f"- Mean milestone-score delta: {comparison['milestone_score_delta']}",
            ]
        )
    lines.extend(
        [
            "",
            "Safety denials are reported separately from milestone failure. "
            "Token values come from provider usage fields; byte values are deterministic harness measurements.",
            "",
        ]
    )
    return "\n".join(lines)


def load_traces(paths: list[str]) -> list[dict[str, Any]]:
    traces = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        if value.get("type") != "agent_trace.v1":
            raise ValueError(f"not an agent trace: {path}")
        traces.append(value)
    return traces


def _aggregate_variant(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = [row.get("totals", {}) for row in rows]
    scores = [row.get("score", {}) for row in rows]
    return {
        "runs": len(rows),
        "success_rate": sum(bool(score.get("passed")) for score in scores) / len(rows),
        "mean_milestone_score": round(
            sum(float(score.get("milestone_score", 0.0)) for score in scores) / len(rows), 4
        ),
        "median_input_tokens": median(float(total.get("input_tokens", 0)) for total in totals),
        "median_output_tokens": median(float(total.get("output_tokens", 0)) for total in totals),
        "median_total_tokens": median(float(total.get("total_tokens", 0)) for total in totals),
        "median_raw_tool_output_bytes": median(
            float(total.get("raw_tool_output_bytes", 0)) for total in totals
        ),
        "median_model_visible_tool_bytes": median(
            float(total.get("model_visible_tool_bytes", 0)) for total in totals
        ),
        "median_peak_context_bytes": median(
            float(total.get("peak_context_bytes", 0)) for total in totals
        ),
        "tool_failures": sum(int(total.get("tool_failures", 0)) for total in totals),
        "policy_denials": sum(int(total.get("policy_denials", 0)) for total in totals),
        "median_wall_time_ms": median(float(total.get("wall_time_ms", 0)) for total in totals),
    }


def _reduction_ratio(baseline: float, candidate: float) -> float:
    if baseline <= 0:
        return 0.0
    return round((baseline - candidate) / baseline, 4)
