from __future__ import annotations

import json
from typing import Any

from sec_capsules.core.artifacts import artifact_ref


def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, Any]:
    endpoints: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()

    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        request = item.get("request") if isinstance(item.get("request"), dict) else {}
        url = item.get("url") or item.get("endpoint") or request.get("endpoint")
        if not url or url in seen:
            continue
        seen.add(url)
        ref = artifact_ref(run_id, artifact_name, line_no)
        method = request.get("method") or item.get("method") or "GET"
        endpoints.append(
            {
                "type": "endpoint.v1",
                "url": url,
                "method": method,
                "source_tool": "katana",
                "evidence_refs": [ref],
            }
        )
        evidence.append(
            {
                "type": "evidence.v1",
                "source_tool": "katana",
                "artifact_ref": ref,
                "summary": f"Crawler discovered {method} {url}",
            }
        )

    return {"services": [], "endpoints": endpoints, "findings": [], "evidence": evidence}

