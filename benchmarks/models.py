from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderResponse:
    content: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    trace_id: str | None = None


@dataclass(frozen=True)
class AdapterResult:
    status: str
    model_output: dict[str, Any]
    raw_output_bytes: int = 0
    model_visible_bytes: int = 0
    duration_ms: float = 0.0
    run_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)


class AgentProvider(Protocol):
    name: str

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        max_tokens: int,
    ) -> ProviderResponse: ...


class ToolAdapter(Protocol):
    variant: str

    def instructions(self) -> str: ...

    def invoke(self, action: dict[str, Any]) -> AdapterResult: ...
