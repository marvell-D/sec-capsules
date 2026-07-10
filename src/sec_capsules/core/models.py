from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def estimate_tokens(value: Any) -> int:
    text = value if isinstance(value, str) else repr(value)
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class Capsule:
    id: str
    name: str
    category: str
    summary: str
    raw: dict[str, Any]
    root: Path

    @property
    def stages(self) -> list[str]:
        return list(self.raw.get("stage", []))

    @property
    def risk_level(self) -> str:
        return str(self.raw.get("risk_level", "unknown"))

    def profile(self, name: str) -> dict[str, Any]:
        profiles = self.raw.get("profiles", {})
        if name not in profiles:
            available = ", ".join(sorted(profiles)) or "none"
            raise KeyError(f"unknown profile {name!r} for {self.id}; available: {available}")
        return dict(profiles[name])


@dataclass
class CommandPlan:
    capsule_id: str
    profile: str
    command: list[str]
    requires_approval: bool
    risk_level: str
    note: str = "Command is a plan. Execution requires scope and policy checks."

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "profile": self.profile,
            "command": self.command,
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "note": self.note,
        }


@dataclass
class ArtifactRecord:
    artifact_id: str
    path: str
    sha256: str
    content_type: str
    redacted: bool
    produced_by: str
    run_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "sha256": self.sha256,
            "content_type": self.content_type,
            "redacted": self.redacted,
            "produced_by": self.produced_by,
            "run_id": self.run_id,
        }


@dataclass
class RunResult:
    run_id: str
    capsule_id: str
    profile: str
    command: list[str]
    started_at: str
    finished_at: str
    exit_code: int | None
    artifacts: list[ArtifactRecord]
    structured: dict[str, Any]
    observation: dict[str, Any]
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "capsule_id": self.capsule_id,
            "profile": self.profile,
            "command": self.command,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "structured": self.structured,
            "observation": self.observation,
            "dry_run": self.dry_run,
        }


@dataclass
class RunContext:
    target: str
    scope_file: Path
    profile: str = "safe"
    token_budget: int = 800
    run_id: str | None = None
    artifacts_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

