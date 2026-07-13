from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from benchmarks.models import AgentProvider, ToolAdapter
from sec_capsules.core.models import utc_now


COMMON_SYSTEM_PROMPT = """You are a thin reference security-recon agent operating only on an authorized local lab.
Use the provided tool interface to collect enough evidence for the task. Never invent observations.
Every response must be one JSON object with exactly one action shape:
{"type":"tool","tool":"tool_name","input":{...}}
or
{"type":"final","answer":{"assets":[],"services":[],"endpoints":[],"findings":[],"evidence_refs":[]}}
Keep evidence references from tool results in the final answer. Do not use web search or outside knowledge.
"""


def run_reference_agent(
    scenario: dict[str, Any],
    *,
    adapter: ToolAdapter,
    provider: AgentProvider,
    model: str,
    max_turns: int = 6,
    max_tokens: int = 768,
) -> dict[str, Any]:
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    started_at = utc_now()
    started = time.perf_counter()
    public_scenario = {
        "id": scenario.get("id"),
        "task": scenario.get("task"),
        "targets": scenario.get("targets", {}),
    }
    messages = [
        {"role": "system", "content": f"{COMMON_SYSTEM_PROMPT}\n{adapter.instructions()}"},
        {
            "role": "user",
            "content": json.dumps(public_scenario, ensure_ascii=False, sort_keys=True),
        },
    ]
    model_calls: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    final_answer: dict[str, Any] = {}
    status = "turn_limit"
    peak_context_bytes = 0

    for turn in range(1, max_turns + 1):
        context_text = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        context_bytes = len(context_text.encode("utf-8"))
        peak_context_bytes = max(peak_context_bytes, context_bytes)
        response = provider.complete(messages, model=model, max_tokens=max_tokens)
        content = response.content
        model_calls.append(
            {
                "turn": turn,
                "context_bytes": context_bytes,
                "messages_sha256": hashlib.sha256(context_text.encode("utf-8")).hexdigest(),
                "response": content,
                "usage": response.usage,
                "latency_ms": response.latency_ms,
                "provider_trace_id": response.trace_id,
            }
        )

        if content.get("type") == "final" and isinstance(content.get("answer"), dict):
            final_answer = dict(content["answer"])
            status = "completed"
            break
        if content.get("type") != "tool":
            status = "invalid_model_action"
            break

        result = adapter.invoke(content)
        tool_calls.append(
            {
                "turn": turn,
                "tool": content.get("tool"),
                "input": content.get("input", {}),
                "status": result.status,
                "model_output": result.model_output,
                "raw_output_bytes": result.raw_output_bytes,
                "model_visible_bytes": result.model_visible_bytes,
                "duration_ms": result.duration_ms,
                "run_id": result.run_id,
                "artifact_refs": result.artifact_refs,
                "policy": result.policy,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(content, ensure_ascii=False, sort_keys=True),
            }
        )
        messages.append(
            {
                "role": "user",
                "content": "Tool result: "
                + json.dumps(result.model_output, ensure_ascii=False, sort_keys=True),
            }
        )

    usage = _sum_usage(model_calls)
    return {
        "type": "agent_trace.v1",
        "trace_id": trace_id,
        "scenario_id": scenario.get("id"),
        "variant": adapter.variant,
        "provider": provider.name,
        "model": model,
        "started_at": started_at,
        "finished_at": utc_now(),
        "status": status,
        "config": {"max_turns": max_turns, "max_tokens": max_tokens},
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "final_answer": final_answer,
        "score": {},
        "totals": {
            **usage,
            "raw_tool_output_bytes": sum(call["raw_output_bytes"] for call in tool_calls),
            "model_visible_tool_bytes": sum(call["model_visible_bytes"] for call in tool_calls),
            "peak_context_bytes": peak_context_bytes,
            "tool_calls": len(tool_calls),
            "tool_failures": sum(call["status"] not in {"ok", "replayed", "succeeded"} for call in tool_calls),
            "policy_denials": sum(call["status"] == "denied" for call in tool_calls),
            "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }


def _sum_usage(model_calls: list[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
    }
    for call in model_calls:
        usage = call.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["total_tokens"] += int(usage.get("total_tokens", input_tokens + output_tokens) or 0)
        totals["cached_tokens"] += int(
            usage.get("cached_tokens", usage.get("prompt_cache_hit_tokens", 0)) or 0
        )
    return totals
