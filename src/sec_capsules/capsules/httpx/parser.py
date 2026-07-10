from __future__ import annotations

import json
from typing import Any

from sec_capsules.core.artifacts import artifact_ref


def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, Any]:
    services: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        url = item.get("url") or item.get("input")
        host = item.get("host") or item.get("a") or ""
        port = item.get("port")
        scheme = item.get("scheme") or (str(url).split(":", 1)[0] if url else "http")
        ref = artifact_ref(run_id, artifact_name, line_no)

        service = {
            "type": "service.v1",
            "host": host,
            "port": port,
            "protocol": scheme,
            "url": url,
            "status_code": item.get("status_code"),
            "title": item.get("title"),
            "technologies": item.get("tech") or item.get("technologies") or [],
            "source_tool": "httpx",
            "evidence_refs": [ref],
        }
        endpoint = {
            "type": "endpoint.v1",
            "url": url,
            "method": "GET",
            "status_code": item.get("status_code"),
            "source_tool": "httpx",
            "evidence_refs": [ref],
        }
        services.append(service)
        endpoints.append(endpoint)
        evidence.append(
            {
                "type": "evidence.v1",
                "source_tool": "httpx",
                "artifact_ref": ref,
                "summary": f"HTTP probe returned {item.get('status_code')} for {url}",
            }
        )

    return {"services": services, "endpoints": endpoints, "findings": [], "evidence": evidence}

