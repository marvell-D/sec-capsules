from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

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

    def read_ref(
        self,
        ref: str,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
        max_lines: int = 200,
        max_chars: int = 16_000,
    ) -> dict[str, object]:
        path, fragment_line = self.resolve_ref(ref)
        if max_lines <= 0 or max_chars <= 0:
            raise ValueError("max_lines and max_chars must be positive")
        if fragment_line is not None:
            start_line = fragment_line
            end_line = fragment_line
        if start_line is not None and start_line <= 0:
            raise ValueError("start_line must be positive")
        if end_line is not None and end_line <= 0:
            raise ValueError("end_line must be positive")
        if start_line and end_line and end_line < start_line:
            raise ValueError("end_line must not be less than start_line")

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        first = (start_line or 1) - 1
        last = end_line or min(len(lines), first + max_lines)
        selected = lines[first:last]
        text = "\n".join(selected)
        truncated = len(selected) == max_lines and last < len(lines)
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True
        return {
            "artifact_ref": ref,
            "content": text,
            "start_line": first + 1,
            "end_line": first + len(selected),
            "truncated": truncated,
        }

    def resolve_ref(self, ref: str) -> tuple[Path, int | None]:
        parsed = urlparse(ref)
        if parsed.scheme != "artifact" or not parsed.netloc:
            raise ValueError("artifact access requires an artifact:// reference")
        run_id = parsed.netloc
        if not _is_safe_component(run_id):
            raise ValueError("artifact reference contains an invalid run id")

        relative = Path(parsed.path.lstrip("/"))
        expected_prefix = Path("artifacts")
        if relative.parts[:1] != expected_prefix.parts or len(relative.parts) < 2:
            raise ValueError("artifact reference must point inside a run artifacts directory")
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("artifact reference contains an invalid path")

        run_root = (self.root / run_id / "artifacts").resolve()
        path = (self.root / run_id / relative).resolve()
        try:
            path.relative_to(run_root)
        except ValueError as exc:
            raise ValueError("artifact reference escapes the artifacts directory") from exc
        if not path.is_file():
            raise FileNotFoundError(f"artifact does not exist: {ref}")

        line_no = None
        if parsed.fragment:
            if not parsed.fragment.startswith("L") or not parsed.fragment[1:].isdigit():
                raise ValueError("artifact line fragment must use the form #L<positive integer>")
            line_no = int(parsed.fragment[1:])
            if line_no <= 0:
                raise ValueError("artifact line fragment must be positive")
        return path, line_no


def _is_safe_component(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and "/" not in value and "\\" not in value


def artifact_ref(run_id: str, artifact_name: str, line: int | None = None) -> str:
    suffix = f"#L{line}" if line else ""
    return f"artifact://{run_id}/artifacts/{artifact_name}{suffix}"
