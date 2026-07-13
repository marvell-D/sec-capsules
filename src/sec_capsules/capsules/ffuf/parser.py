from __future__ import annotations

import json
from typing import Any

from sec_capsules.core.artifacts import artifact_ref


def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, Any]:
    endpoints: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None, int | None]] = set()
    diagnostics = {
        "input_records": 0,
        "parsed_records": 0,
        "invalid_records": 0,
        "duplicate_records": 0,
        "emitted_records": 0,
    }

    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        diagnostics["input_records"] += 1
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            diagnostics["invalid_records"] += 1
            continue
        if not isinstance(item, dict):
            diagnostics["invalid_records"] += 1
            continue

        url = item.get("url")
        if not isinstance(url, str) or not url:
            diagnostics["invalid_records"] += 1
            continue
        diagnostics["parsed_records"] += 1

        method = str(item.get("method") or "GET").upper()
        status = _optional_int(item.get("status"))
        content_length = _optional_int(item.get("length"))
        dedupe_key = (url, method, status, content_length)
        if dedupe_key in seen:
            diagnostics["duplicate_records"] += 1
            continue
        seen.add(dedupe_key)

        ref = artifact_ref(run_id, artifact_name, line_no)
        endpoint: dict[str, Any] = {
            "type": "endpoint.v1",
            "url": url,
            "method": method,
            "source_tool": "ffuf",
            "evidence_refs": [ref],
        }
        _copy_optional(endpoint, "status_code", status)
        _copy_optional(endpoint, "content_length", content_length)
        _copy_optional(endpoint, "content_type", item.get("content-type"))
        _copy_optional(endpoint, "words", _optional_int(item.get("words")))
        _copy_optional(endpoint, "lines", _optional_int(item.get("lines")))
        _copy_optional(endpoint, "redirect_location", item.get("redirectlocation"))

        fuzz_input = item.get("input")
        if isinstance(fuzz_input, dict):
            value = fuzz_input.get("FUZZ")
            if isinstance(value, str) and value:
                endpoint["fuzz_input"] = value

        endpoints.append(endpoint)
        evidence.append(
            {
                "type": "evidence.v1",
                "source_tool": "ffuf",
                "artifact_ref": ref,
                "summary": f"FFUF observed {method} {url} with status {status or 'unknown'}",
            }
        )

    diagnostics["emitted_records"] = len(endpoints)
    diagnostics["partial"] = diagnostics["invalid_records"] > 0
    return {
        "assets": [],
        "services": [],
        "endpoints": endpoints,
        "findings": [],
        "evidence": evidence,
        "parse_diagnostics": diagnostics,
    }


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _copy_optional(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None and value != "":
        target[key] = value
