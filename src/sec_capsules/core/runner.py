from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sec_capsules.core.artifacts import ArtifactStore
from sec_capsules.core.executor import DEFAULT_OUTPUT_LIMIT_BYTES, inspect_tool, run_command
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

    def plan(
        self,
        capsule_id: str,
        *,
        target: str,
        profile: str = "safe",
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        capsule = self.registry.get(capsule_id)
        return build_command_plan(
            capsule,
            target=target,
            profile_name=profile,
            arguments=arguments,
        ).to_dict()

    def doctor(self, capsule_id: str | None = None) -> list[dict[str, Any]]:
        capsules = [self.registry.get(capsule_id)] if capsule_id else self.registry.list()
        reports = []
        for capsule in capsules:
            runtime = capsule.raw.get("runtime", {})
            binary = str(runtime.get("binary", capsule.id))
            version_command = runtime.get("version_command", [binary, "-version"])
            health = inspect_tool([binary], version_command=version_command)
            reports.append(
                {
                    "capsule_id": capsule.id,
                    "health": health.to_dict(),
                    "max_output_bytes": int(runtime.get("max_output_bytes", DEFAULT_OUTPUT_LIMIT_BYTES)),
                }
            )
        return reports

    def run(
        self,
        capsule_id: str,
        *,
        target: str,
        scope_file: Path | str,
        profile: str = "safe",
        arguments: dict[str, Any] | None = None,
        execute: bool = False,
        fixture: Path | str | None = None,
        approval_file: Path | str | None = None,
        token_budget: int = 800,
        timeout: int = 120,
        max_output_bytes: int | None = None,
    ) -> RunResult:
        capsule = self.registry.get(capsule_id)
        plan = build_command_plan(
            capsule,
            target=target,
            profile_name=profile,
            arguments=arguments,
        )
        scope = ScopePolicy.from_file(scope_file)
        approval = ScopePolicy.approval_from_file(approval_file) if approval_file else None
        profile_data = capsule.profile(profile)
        decision = scope.decide(
            target,
            action=plan.action,
            active=bool(profile_data.get("active", True)),
            requested_rate_limit=plan.rate_limit,
            requires_approval=plan.requires_approval,
            approval=approval,
            resolve_dns=execute,
        )
        decision.raise_if_denied()

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        started_at = utc_now()
        raw_stdout = ""
        raw_stderr = ""
        exit_code: int | None = None
        dry_run = not execute and fixture is None
        status = "dry_run" if dry_run else "replayed" if fixture is not None else "succeeded"
        timed_out = False
        output_truncated = False
        tool: dict[str, Any] = {}

        if fixture is not None:
            raw_stdout = Path(fixture).read_text(encoding="utf-8")
            exit_code = 0
        elif execute:
            runtime = capsule.raw.get("runtime", {})
            version_command = runtime.get("version_command")
            health = inspect_tool(plan.command, version_command=version_command)
            tool = health.to_dict()
            if not health.available:
                raw_stderr = health.error or "tool preflight failed"
                status = "preflight_failed"
            else:
                try:
                    execution = run_command(
                        plan.command,
                        timeout=timeout,
                        max_output_bytes=(
                            max_output_bytes
                            if max_output_bytes is not None
                            else int(runtime.get("max_output_bytes", DEFAULT_OUTPUT_LIMIT_BYTES))
                        ),
                    )
                except OSError as exc:
                    raw_stderr = f"tool execution could not start: {exc}"
                    status = "failed"
                else:
                    raw_stdout = execution.stdout
                    raw_stderr = execution.stderr
                    exit_code = execution.exit_code
                    timed_out = execution.timed_out
                    output_truncated = execution.output_truncated
                    if timed_out:
                        status = "timed_out"
                    elif exit_code != 0:
                        status = "failed"

        artifact_name = capsule.raw.get("artifacts", {}).get("primary", f"{capsule.id}.out")
        artifacts = [
            self.artifacts.write_text(
                run_id=run_id,
                produced_by=capsule.id,
                name=artifact_name,
                content=raw_stdout,
                content_type=capsule.raw.get("artifacts", {}).get("content_type", "text/plain"),
            )
        ]
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

        structured = (
            {"assets": [], "services": [], "endpoints": [], "findings": [], "evidence": []}
            if status == "preflight_failed"
            else parse_capsule_output(capsule, raw_stdout, run_id=run_id, artifact_name=artifact_name)
        )
        execution_summary = {
            "status": status,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "output_truncated": output_truncated,
            "tool_version": tool.get("version"),
        }
        observation = build_observation_packet(
            run_id=run_id,
            tool=capsule.id,
            structured=structured,
            token_budget=token_budget,
            execution=execution_summary,
        )

        result = RunResult(
            run_id=run_id,
            capsule_id=capsule.id,
            profile=profile,
            command=plan.command,
            started_at=started_at,
            finished_at=utc_now(),
            exit_code=exit_code,
            artifacts=artifacts,
            structured=structured,
            observation=observation,
            dry_run=dry_run,
            status=status,
            arguments=plan.arguments,
            argument_sources=plan.argument_sources,
            rate_limit=plan.rate_limit.to_dict() if plan.rate_limit else None,
            target=target,
            normalized_target=decision.normalized_target,
            scope_decision=decision.to_dict(),
            approval=decision.approval,
            tool=tool,
            timed_out=timed_out,
            output_truncated=output_truncated,
        )
        self._write_result(result)
        return result

    def _write_result(self, result: RunResult) -> None:
        run_dir = self.runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "observation.json").write_text(
            json.dumps(result.observation, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "structured.json").write_text(
            json.dumps(result.structured, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
