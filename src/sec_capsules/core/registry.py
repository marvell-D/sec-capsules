from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from sec_capsules.core.models import Capsule
from sec_capsules.core.paths import CAPSULES_ROOT


class CapsuleRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or CAPSULES_ROOT
        self._capsules: dict[str, Capsule] | None = None

    def load(self) -> dict[str, Capsule]:
        if self._capsules is not None:
            return self._capsules

        capsules: dict[str, Capsule] = {}
        for path in sorted(self.root.glob("*/capsule.yml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            capsule_id = str(raw.get("id") or path.parent.name)
            capsule = Capsule(
                id=capsule_id,
                name=str(raw.get("name") or capsule_id),
                category=str(raw.get("category") or "unknown"),
                summary=str(raw.get("summary") or ""),
                raw=raw,
                root=path.parent,
            )
            capsules[capsule.id] = capsule

        self._capsules = capsules
        return capsules

    def list(self) -> list[Capsule]:
        return list(self.load().values())

    def get(self, capsule_id: str) -> Capsule:
        capsules = self.load()
        if capsule_id not in capsules:
            available = ", ".join(sorted(capsules)) or "none"
            raise KeyError(f"unknown capsule {capsule_id!r}; available: {available}")
        return capsules[capsule_id]

    def search(
        self,
        query: str | None = None,
        stage: str | None = None,
        risk_level: str | None = None,
    ) -> list[Capsule]:
        query_l = (query or "").lower().strip()
        matches: list[Capsule] = []
        for capsule in self.list():
            haystack = " ".join(
                [
                    capsule.id,
                    capsule.name,
                    capsule.category,
                    capsule.summary,
                    " ".join(capsule.stages),
                    " ".join(capsule.raw.get("best_for", [])),
                ]
            ).lower()
            if query_l and query_l not in haystack:
                continue
            if stage and stage not in capsule.stages:
                continue
            if risk_level and risk_level != capsule.risk_level:
                continue
            matches.append(capsule)
        return matches


def capsule_to_public_dict(capsule: Capsule, detail_level: str = "brief") -> dict:
    base = {
        "id": capsule.id,
        "name": capsule.name,
        "category": capsule.category,
        "stage": capsule.stages,
        "risk_level": capsule.risk_level,
        "summary": capsule.summary,
    }
    if detail_level == "brief":
        return base
    if detail_level == "usage":
        return {
            **base,
            "best_for": capsule.raw.get("best_for", []),
            "avoid_when": capsule.raw.get("avoid_when", []),
            "profiles": {
                key: {
                    "description": value.get("description", ""),
                    "requires_approval": bool(value.get("requires_approval", False)),
                }
                for key, value in capsule.raw.get("profiles", {}).items()
            },
            "model_exposure": capsule.raw.get("model_exposure", {}),
            "next_actions": capsule.raw.get("next_actions", []),
        }
    if detail_level == "full":
        return capsule.raw
    raise ValueError("detail_level must be one of: brief, usage, full")


def capsule_rows(capsules: Iterable[Capsule]) -> list[tuple[str, str, str, str]]:
    return [(c.id, c.category, c.risk_level, c.summary) for c in capsules]

