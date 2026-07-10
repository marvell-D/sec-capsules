from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_capsules.core.models import ArtifactRecord


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_text(
        self,
        *,
        run_id: str,
        produced_by: str,
        name: str,
        content: str,
        content_type: str = "text/plain",
        redacted: bool = False,
    ) -> ArtifactRecord:
        run_dir = self.root / run_id / "artifacts"
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / name
        path.write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact = ArtifactRecord(
            artifact_id=f"art_{digest[:12]}",
            path=str(path),
            sha256=digest,
            content_type=content_type,
            redacted=redacted,
            produced_by=produced_by,
            run_id=run_id,
        )
        metadata_path = run_dir / f"{name}.artifact.json"
        metadata_path.write_text(json.dumps(artifact.to_dict(), indent=2), encoding="utf-8")
        return artifact

    def write_json(self, *, run_id: str, produced_by: str, name: str, value: object) -> ArtifactRecord:
        return self.write_text(
            run_id=run_id,
            produced_by=produced_by,
            name=name,
            content=json.dumps(value, indent=2, ensure_ascii=False),
            content_type="application/json",
            redacted=False,
        )


def artifact_ref(run_id: str, artifact_name: str, line: int | None = None) -> str:
    suffix = f"#L{line}" if line else ""
    return f"artifact://{run_id}/artifacts/{artifact_name}{suffix}"

