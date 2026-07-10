from __future__ import annotations

import json
from pathlib import Path


def export_markdown(run_dir: str | Path) -> str:
    path = Path(run_dir)
    run = json.loads((path / "run.json").read_text(encoding="utf-8"))
    obs = run["observation"]
    lines = [
        f"# sec-capsules run {run['run_id']}",
        "",
        f"- Tool: `{run['capsule_id']}`",
        f"- Profile: `{run['profile']}`",
        f"- Exit code: `{run['exit_code']}`",
        f"- Dry run: `{run['dry_run']}`",
        "",
        "## Observation",
        "",
        obs.get("summary", ""),
        "",
    ]
    if obs.get("top_findings"):
        lines.extend(["## Top Findings", ""])
        for finding in obs["top_findings"]:
            lines.append(
                f"- **{finding.get('severity', 'unknown')}** {finding.get('title')} "
                f"on `{finding.get('affected')}` ({finding.get('evidence_ref')})"
            )
        lines.append("")
    lines.extend(["## Artifacts", ""])
    for artifact in run.get("artifacts", []):
        lines.append(f"- `{artifact['path']}` sha256 `{artifact['sha256']}`")
    return "\n".join(lines).rstrip() + "\n"

