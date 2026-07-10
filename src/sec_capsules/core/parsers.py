from __future__ import annotations

import importlib
from typing import Any

from sec_capsules.core.models import Capsule


def parse_capsule_output(
    capsule: Capsule,
    raw_text: str,
    *,
    run_id: str,
    artifact_name: str,
) -> dict[str, Any]:
    module_name = f"sec_capsules.capsules.{capsule.id}.parser"
    module = importlib.import_module(module_name)
    if not hasattr(module, "parse"):
        raise AttributeError(f"{module_name} must expose parse(raw_text, run_id, artifact_name)")
    return module.parse(raw_text, run_id=run_id, artifact_name=artifact_name)

