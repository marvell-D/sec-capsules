from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from benchmarks.models import ProviderResponse
from sec_capsules.evals.providers.siliconflow import SiliconFlowClient


class SiliconFlowAgentProvider:
    name = "siliconflow"

    def __init__(self, client: SiliconFlowClient) -> None:
        self.client = client

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        max_tokens: int,
    ) -> ProviderResponse:
        content, metrics = self.client.chat_json(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return ProviderResponse(
            content=content,
            usage=dict(metrics.get("usage", {})),
            latency_ms=float(metrics.get("latency_ms", 0.0)),
            trace_id=metrics.get("trace_id"),
        )


class ScriptedProvider:
    """Deterministic provider for harness tests; it never calls a model API."""

    name = "scripted"

    def __init__(
        self,
        responses: Iterable[dict[str, Any]],
        *,
        usage_per_call: dict[str, int] | None = None,
    ) -> None:
        self.responses = list(responses)
        self.usage_per_call = usage_per_call or {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        }

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        max_tokens: int,
    ) -> ProviderResponse:
        if not self.responses:
            raise RuntimeError("scripted provider has no response left")
        return ProviderResponse(
            content=self.responses.pop(0),
            usage=dict(self.usage_per_call),
            latency_ms=1.0,
        )
