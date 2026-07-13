from __future__ import annotations

from string import Template
from typing import Any

from sec_capsules.core.arguments import resolve_arguments, resolve_rate_limit, template_value
from sec_capsules.core.models import Capsule, CommandPlan


def build_command_plan(
    capsule: Capsule,
    target: str,
    profile_name: str = "safe",
    arguments: dict[str, Any] | None = None,
) -> CommandPlan:
    profile = capsule.profile(profile_name)
    command_template = profile.get("command")
    if not command_template:
        raise ValueError(f"capsule {capsule.id} profile {profile_name} has no command template")

    resolved = resolve_arguments(capsule, profile_name, arguments)
    variables: dict[str, str] = {
        "target": target,
        "capsule_root": str(capsule.root),
    }
    variables.update({name: template_value(value) for name, value in resolved.values.items()})

    command = []
    for part in command_template:
        try:
            expanded = Template(str(part)).substitute(**variables)
        except KeyError as exc:
            raise ValueError(
                f"capsule {capsule.id} profile {profile_name} references undefined variable {exc.args[0]!r}"
            ) from exc
        if expanded:
            command.append(expanded)

    return CommandPlan(
        capsule_id=capsule.id,
        profile=profile_name,
        command=command,
        requires_approval=bool(profile.get("requires_approval", False)),
        risk_level=capsule.risk_level,
        action=str(profile.get("action", capsule.category)),
        arguments=resolved.values,
        argument_sources=resolved.sources,
        rate_limit=resolve_rate_limit(capsule, resolved.values),
    )
