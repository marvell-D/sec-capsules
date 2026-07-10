from __future__ import annotations

from string import Template
from typing import Any

from sec_capsules.core.models import Capsule, CommandPlan


def build_command_plan(capsule: Capsule, target: str, profile_name: str = "safe") -> CommandPlan:
    profile = capsule.profile(profile_name)
    command_template = profile.get("command")
    if not command_template:
        raise ValueError(f"capsule {capsule.id} profile {profile_name} has no command template")

    variables: dict[str, Any] = {
        "target": target,
        "rate_limit": profile.get("rate_limit", ""),
        "severity": ",".join(profile.get("severity", [])),
        "capsule_root": str(capsule.root),
    }
    variables.update(profile.get("vars", {}))

    command = [
        Template(str(part)).safe_substitute(**variables)
        for part in command_template
        if Template(str(part)).safe_substitute(**variables) != ""
    ]

    return CommandPlan(
        capsule_id=capsule.id,
        profile=profile_name,
        command=command,
        requires_approval=bool(profile.get("requires_approval", False)),
        risk_level=capsule.risk_level,
        action=str(profile.get("action", capsule.category)),
        rate_limit=int(profile["rate_limit"]) if profile.get("rate_limit") is not None else None,
    )
