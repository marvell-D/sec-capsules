from __future__ import annotations

import json
from typing import Any

from sec_capsules.core.artifacts import artifact_ref


def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        info = item.get("info") if isinstance(item.get("info"), dict) else {}
        title = info.get("name") or item.get("template-id") or "Nuclei finding"
        severity = info.get("severity") or item.get("severity") or "unknown"
        affected = item.get("matched-at") or item.get("host") or item.get("url")
        template_id = item.get("template-id")
        ref = artifact_ref(run_id, artifact_name, line_no)

        finding = {
            "type": "finding.v1",
            "title": title,
            "severity": severity,
            "confidence": "high" if item.get("matcher-status", True) else "low",
            "affected": affected,
            "source_tool": "nuclei",
            "template_id": template_id,
            "tags": info.get("tags", []),
            "classification": info.get("classification", {}),
            "evidence_refs": [ref],
        }
        findings.append(finding)
        evidence.append(
            {
                "type": "evidence.v1",
                "source_tool": "nuclei",
                "artifact_ref": ref,
                "summary": f"{severity} finding {title!r} on {affected}",
            }
        )

    return {"services": [], "endpoints": [], "findings": findings, "evidence": evidence}

