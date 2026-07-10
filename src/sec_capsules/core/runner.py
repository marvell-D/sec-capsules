from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sec_capsules.core.artifacts import ArtifactStore
from sec_capsules.core.models import RunResult, utc_now
from sec_capsules.core.observation import build_observation_packet
from sec_capsules.core.parsers import parse_capsule_output
from sec_capsules.core.planner import build_command_plan
from sec_capsules.core.registry import CapsuleRegistry
from sec_capsules.core.scope import ScopePolicy


DEFAULT_RUNS_DIR = Path("runs")


class CapsuleRunner:
    def __init__(
        self,
        *,
        registry: CapsuleRegistry | None = None,
        runs_dir: Path | str = DEFAULT_RUNS_DIR,
    ) -> None:
        self.registry = registry or CapsuleRegistry()
        self.runs_dir = Path(runs_dir)
        self.artifacts = ArtifactStore(self.runs_dir)

    def plan(self, capsule_id: str, *, target: str, profile: str = "safe") -> dict[str, Any]:
        capsule = self.registry.get(capsule_id)
        return build_command_plan(capsule, target=target, profile_name=profile).to_dict()

    def run(
        self,
        capsule_id: str,
        *,
        target: str,
        scope_file: Path | str,
        profile: str = "safe",
        execute: bool = False,
        fixture: Path | str | None = None,
        token_budget: int = 800,
        timeout: int = 120,
    ) -> RunResult:
        capsule = self.registry.get(capsule_id)
        scope = ScopePolicy.from_file(scope_file)
        profile_data = capsule.profile(profile)
        active = bool(profile_data.get("active", True))
        action = str(profile_data.get("action", capsule.category))
        scope.decide(target, action=action, active=active).raise_if_denied()

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        started_at = utc_now()
        plan = build_command_plan(capsule, target=target, profile_name=profile)

        raw_stdout = ""
        raw_stderr = ""
        exit_code: int | None = None
        dry_run = not execute and fixture is None

        if fixture is not None:
            raw_stdout = Path(fixture).read_text(encoding="utf-8")
            exit_code = 0
            dry_run = False
        elif execute:
            completed = subprocess.run(
                plan.command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            raw_stdout = completed.stdout
            raw_stderr = completed.stderr
            exit_code = completed.returncode

        artifact_name = capsule.raw.get("artifacts", {}).get("primary", f"{capsule.id}.out")
        artifacts = []
        artifacts.append(
            self.artifacts.write_text(
                run_id=run_id,
                produced_by=capsule.id,
                name=artifact_name,
                content=raw_stdout,
                content_type=capsule.raw.get("artifacts", {}).get("content_type", "text/plain"),
            )
        )
        if raw_stderr:
            artifacts.append(
                self.artifacts.write_text(
                    run_id=run_id,
                    produced_by=capsule.id,
                    name="stderr.txt",
                    content=raw_stderr,
                    content_type="text/plain",
                )
            )

        structured = parse_capsule_output(capsule, raw_stdout, run_id=run_id, artifact_name=artifact_name)
        observation = build_observation_packet(
            run_id=run_id,
            tool=capsule.id,
            structured=structured,
            token_budget=token_budget,
        )

        finished_at = utc_now()
        result = RunResult(
            run_id=run_id,
            capsule_id=capsule.id,
            profile=profile,
            command=plan.command,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=exit_code,
            artifacts=artifacts,
            structured=structured,
            observation=observation,
            dry_run=dry_run,
        )

        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "observation.json").write_text(
            json.dumps(observation, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "structured.json").write_text(
            json.dumps(structured, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return result

