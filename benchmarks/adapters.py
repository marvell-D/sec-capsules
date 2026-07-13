from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from benchmarks.models import AdapterResult
from sec_capsules.core.executor import run_command
from sec_capsules.core.models import RateLimit
from sec_capsules.core.registry import CapsuleRegistry, capsule_to_public_dict
from sec_capsules.core.runner import CapsuleRunner
from sec_capsules.core.scope import ScopePolicy


class RawToolAdapter:
    variant = "raw"

    def __init__(
        self,
        scenario: dict[str, Any],
        *,
        scenario_path: Path,
        mode: str = "replay",
        runs_dir: Path | str = "benchmark-runs/raw",
    ) -> None:
        self.scenario = scenario
        self.scenario_path = scenario_path
        self.mode = mode
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.scope_file = _resolve_path(scenario_path, str(scenario["scope_file"]))
        self.approval_file = _resolve_path(scenario_path, str(scenario["approval_file"]))
        self.scope = ScopePolicy.from_file(self.scope_file)
        self.approval = ScopePolicy.approval_from_file(self.approval_file)
        self.registry = CapsuleRegistry()
        self.wordlist = self.registry.get("ffuf").root / "wordlists" / "web-small.txt"

    def instructions(self) -> str:
        return f"""Raw tool interface (ordinary argv/stdout integration):
- Tool name: run_command
- Input: {{"argv":["binary","arg",...]}}
- Allowed Nmap form uses nmap -sT -Pn -n --reason --max-retries 2 --host-timeout 60s --max-rate RATE -p PORTS -oX - TARGET.
- Allowed FFUF form uses ffuf -w {self.wordlist} -u TARGET/FUZZ -json -s -noninteractive -t 5 -rate RATE -timeout 5 -maxtime 60 -mc STATUS_CODES.
The tool returns raw stdout. Only the scenario targets are permitted. Both commands require approval.
"""

    def invoke(self, action: dict[str, Any]) -> AdapterResult:
        started = time.perf_counter()
        if action.get("tool") != "run_command":
            return self._denied("raw adapter exposes only run_command", started)
        payload = action.get("input")
        argv = payload.get("argv") if isinstance(payload, dict) else None
        if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
            return self._denied("argv must be a non-empty string array", started)

        try:
            command = self._validate(argv)
            decision = self.scope.decide(
                command["target"],
                action=command["action"],
                active=True,
                requested_rate_limit=command["rate_limit"],
                requires_approval=True,
                approval=self.approval,
                resolve_dns=self.mode == "live",
            )
            decision.raise_if_denied()
        except (PermissionError, ValueError) as exc:
            return self._denied(str(exc), started)

        if self.mode == "replay":
            fixture = _resolve_fixture(self.scenario, self.scenario_path, str(argv[0]))
            stdout = fixture.read_text(encoding="utf-8")
            stderr = ""
            exit_code = 0
            status = "replayed"
        elif self.mode == "live":
            execution = run_command(
                argv,
                timeout=int(self.scenario.get("limits", {}).get("tool_timeout_seconds", 120)),
                max_output_bytes=int(
                    self.scenario.get("limits", {}).get("max_raw_output_bytes", 4_194_304)
                ),
            )
            stdout = execution.stdout
            stderr = execution.stderr
            exit_code = execution.exit_code
            status = "succeeded" if exit_code == 0 and not execution.timed_out else "failed"
        else:
            return self._denied(f"unsupported benchmark mode: {self.mode}", started)

        run_id = f"raw_{uuid.uuid4().hex[:12]}"
        artifact_path = self.runs_dir / f"{run_id}.{_artifact_suffix(str(argv[0]))}"
        artifact_path.write_text(stdout, encoding="utf-8")
        output = {
            "status": status,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "artifact_ref": str(artifact_path),
        }
        visible_bytes = _json_bytes(output)
        return AdapterResult(
            status=status,
            model_output=output,
            raw_output_bytes=len(stdout.encode("utf-8")) + len(stderr.encode("utf-8")),
            model_visible_bytes=visible_bytes,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            run_id=run_id,
            artifact_refs=[str(artifact_path)],
            policy=decision.to_dict(),
        )

    def _validate(self, argv: list[str]) -> dict[str, Any]:
        if any("\x00" in value or "\n" in value or "\r" in value for value in argv):
            raise ValueError("argv contains forbidden control characters")
        if argv[0] == "nmap":
            values, positional = _parse_options(
                argv[1:],
                no_value={"-sT", "-sV", "-Pn", "-n", "--reason", "--version-light"},
                value_options={
                    "--max-retries",
                    "--host-timeout",
                    "--max-rate",
                    "-p",
                    "-oX",
                },
            )
            if len(positional) != 1 or positional[0] != self.scenario["targets"]["host"]:
                raise ValueError("nmap must use exactly the authorized host target")
            _require_option(values, "-p")
            ports = [int(value) for value in values["-p"].split(",")]
            if not ports or len(ports) > 64 or any(port < 1 or port > 65535 for port in ports):
                raise ValueError("nmap ports must contain 1 to 64 valid TCP ports")
            if values.get("-oX") != "-":
                raise ValueError("nmap XML output must be written to stdout")
            rate = _bounded_int(values, "--max-rate", maximum=200)
            if values.get("--max-retries") not in {None, "2"}:
                raise ValueError("nmap max retries may not exceed the benchmark profile")
            if values.get("--host-timeout") not in {None, "60s", "90s"}:
                raise ValueError("nmap host timeout is outside the benchmark profile")
            return {
                "target": positional[0],
                "action": "service_version_scan" if "-sV" in argv else "port_scan",
                "rate_limit": RateLimit("packets_per_second", rate, "packets_per_second"),
            }

        if argv[0] == "ffuf":
            values, positional = _parse_options(
                argv[1:],
                no_value={"-json", "-s", "-noninteractive"},
                value_options={"-w", "-u", "-t", "-rate", "-timeout", "-maxtime", "-mc"},
            )
            if positional:
                raise ValueError("ffuf does not accept positional arguments in this benchmark")
            if values.get("-w") != str(self.wordlist):
                raise ValueError("ffuf must use the packaged benchmark wordlist")
            expected_url = f"{self.scenario['targets']['web'].rstrip('/')}/FUZZ"
            if values.get("-u") != expected_url:
                raise ValueError("ffuf must use the authorized web target with one FUZZ marker")
            for required in ("-json", "-s", "-noninteractive"):
                if required not in values:
                    raise ValueError(f"ffuf requires {required}")
            if values.get("-t") != "5" or values.get("-timeout") != "5":
                raise ValueError("ffuf thread and timeout controls are fixed")
            if values.get("-maxtime") != "60":
                raise ValueError("ffuf maximum execution time is fixed at 60 seconds")
            statuses = values.get("-mc", "").split(",")
            if not statuses or len(statuses) > 10 or any(not item.isdigit() for item in statuses):
                raise ValueError("ffuf status matcher must contain at most 10 numeric codes")
            rate = _bounded_int(values, "-rate", maximum=50)
            return {
                "target": self.scenario["targets"]["web"],
                "action": "content_discovery",
                "rate_limit": RateLimit("requests_per_second", rate, "requests_per_second"),
            }
        raise ValueError("only nmap and ffuf are available in this scenario")

    def _denied(self, reason: str, started: float) -> AdapterResult:
        output = {"status": "denied", "error": reason}
        return AdapterResult(
            status="denied",
            model_output=output,
            model_visible_bytes=_json_bytes(output),
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            policy={"allowed": False, "reasons": [reason]},
        )


class CapsuleToolAdapter:
    variant = "capsule"

    def __init__(
        self,
        scenario: dict[str, Any],
        *,
        scenario_path: Path,
        mode: str = "replay",
        runs_dir: Path | str = "benchmark-runs/capsule",
    ) -> None:
        self.scenario = scenario
        self.scenario_path = scenario_path
        self.mode = mode
        self.registry = CapsuleRegistry()
        self.runner = CapsuleRunner(registry=self.registry, runs_dir=runs_dir)
        self.scope_file = _resolve_path(scenario_path, str(scenario["scope_file"]))
        self.approval_file = _resolve_path(scenario_path, str(scenario["approval_file"]))
        self.available = set(str(value) for value in scenario.get("available_capsules", []))

    def instructions(self) -> str:
        return """Capsule interface (progressive disclosure and observation-only integration):
- search_capsules input: {"query":"..."}; returns brief cards.
- get_capsule input: {"capsule_id":"..."}; returns the usage card and semantic input schema.
- run_capsule input: {"capsule_id":"...","target":"...","profile":"safe","arguments":{...}}.
Search first, fetch usage only for a relevant capsule, then run it. The runtime enforces scope,
approval, semantic argument bounds and command templates. Tool results hide raw output and return
compact observations plus evidence references.
"""

    def invoke(self, action: dict[str, Any]) -> AdapterResult:
        started = time.perf_counter()
        tool = action.get("tool")
        payload = action.get("input") if isinstance(action.get("input"), dict) else {}
        try:
            if tool == "search_capsules":
                query = str(payload.get("query", ""))
                cards = [
                    capsule_to_public_dict(capsule, "brief")
                    for capsule in self.registry.search(query=query)
                    if capsule.id in self.available
                ]
                return _metadata_result({"capsules": cards}, started)
            if tool == "get_capsule":
                capsule_id = str(payload.get("capsule_id", ""))
                self._require_available(capsule_id)
                card = capsule_to_public_dict(self.registry.get(capsule_id), "usage")
                return _metadata_result({"capsule": card}, started)
            if tool != "run_capsule":
                raise ValueError("unknown capsule adapter tool")

            capsule_id = str(payload.get("capsule_id", ""))
            self._require_available(capsule_id)
            fixture = (
                _resolve_fixture(self.scenario, self.scenario_path, capsule_id)
                if self.mode == "replay"
                else None
            )
            result = self.runner.run(
                capsule_id,
                target=str(payload.get("target", "")),
                scope_file=self.scope_file,
                profile=str(payload.get("profile", "safe")),
                arguments=payload.get("arguments", {}),
                execute=self.mode == "live",
                fixture=fixture,
                approval_file=self.approval_file,
                token_budget=int(
                    self.scenario.get("limits", {}).get("observation_token_budget", 800)
                ),
                timeout=int(self.scenario.get("limits", {}).get("tool_timeout_seconds", 120)),
                max_output_bytes=int(
                    self.scenario.get("limits", {}).get("max_raw_output_bytes", 4_194_304)
                ),
            )
        except (KeyError, PermissionError, ValueError) as exc:
            output = {"status": "denied", "error": str(exc)}
            return AdapterResult(
                status="denied",
                model_output=output,
                model_visible_bytes=_json_bytes(output),
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                policy={"allowed": False, "reasons": [str(exc)]},
            )

        output = result.observation
        artifact_refs = [artifact.path for artifact in result.artifacts]
        raw_bytes = sum(
            Path(artifact.path).stat().st_size
            for artifact in result.artifacts
            if Path(artifact.path).is_file()
        )
        return AdapterResult(
            status=result.status,
            model_output=output,
            raw_output_bytes=raw_bytes,
            model_visible_bytes=_json_bytes(output),
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            run_id=result.run_id,
            artifact_refs=artifact_refs,
            policy=result.scope_decision,
        )

    def _require_available(self, capsule_id: str) -> None:
        if capsule_id not in self.available:
            raise ValueError(f"capsule is not available in this scenario: {capsule_id}")


def _metadata_result(output: dict[str, Any], started: float) -> AdapterResult:
    return AdapterResult(
        status="ok",
        model_output=output,
        model_visible_bytes=_json_bytes(output),
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )


def _resolve_path(scenario_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (scenario_path.parent / path).resolve()


def _resolve_fixture(scenario: dict[str, Any], scenario_path: Path, tool: str) -> Path:
    fixtures = scenario.get("fixtures", {})
    if tool not in fixtures:
        raise ValueError(f"scenario has no replay fixture for {tool}")
    return _resolve_path(scenario_path, str(fixtures[tool]))


def _parse_options(
    values: list[str],
    *,
    no_value: set[str],
    value_options: set[str],
) -> tuple[dict[str, str | None], list[str]]:
    parsed: dict[str, str | None] = {}
    positional: list[str] = []
    index = 0
    while index < len(values):
        token = values[index]
        if token in no_value:
            if token in parsed:
                raise ValueError(f"duplicate option: {token}")
            parsed[token] = None
            index += 1
            continue
        if token in value_options:
            if token in parsed or index + 1 >= len(values):
                raise ValueError(f"invalid option value: {token}")
            parsed[token] = values[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            raise ValueError(f"option is not allowed: {token}")
        positional.append(token)
        index += 1
    return parsed, positional


def _require_option(values: dict[str, str | None], name: str) -> None:
    if not values.get(name):
        raise ValueError(f"required option is missing: {name}")


def _bounded_int(values: dict[str, str | None], name: str, *, maximum: int) -> int:
    raw = values.get(name)
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]+", raw):
        raise ValueError(f"{name} must be a positive integer")
    value = int(raw)
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _artifact_suffix(binary: str) -> str:
    return "xml" if binary == "nmap" else "jsonl"


def _json_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))
