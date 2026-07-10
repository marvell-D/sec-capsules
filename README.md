# sec-capsules

Agent-native security tool capsules for structured outputs, evidence artifacts, scope-safe execution, and token-efficient observations.

`sec-capsules` is not an autonomous pentest framework. It is a tool invocation layer for security agents: it describes when a tool should be used, checks scope before execution, preserves raw artifacts, normalizes outputs, and returns compact `ObservationPacket` objects to the model.

## Why

Plain wrappers usually do this:

```text
input args -> shell command -> raw stdout -> model context
```

`sec-capsules` does this:

```text
tool card disclosure
  -> scope and policy check
  -> safe command plan
  -> execution or fixture replay
  -> artifact preservation
  -> structured parsing
  -> evidence references
  -> token-budgeted ObservationPacket
```

## v0.1 Scope

The first vertical slice focuses on a small WebSec capsule pack:

- `httpx`: HTTP service probing
- `katana`: endpoint collection
- `nuclei`: baseline finding collection

The goal is to prove the runtime shape, not to support the largest tool catalog.

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

sec-capsules list
sec-capsules doctor --require
sec-capsules describe nuclei --level usage
sec-capsules plan nuclei --target http://localhost:3000 --scope examples/juice-shop-local/scope.yml
sec-capsules run nuclei --target http://localhost:3000 --scope examples/juice-shop-local/scope.yml --fixture src/sec_capsules/capsules/nuclei/fixtures/sample.jsonl
```

The `run` command defaults to fixture or dry-run oriented behavior. Real tool execution requires `--execute`.

## Execution Controls

- `doctor` verifies that a capsule's executable is available before an operator starts a live run.
- Live runs resolve the target host and reject private, link-local, metadata, multicast, and out-of-scope addresses unless the scope explicitly allows an authorized local target.
- The profile rate limit cannot exceed `scope.max_requests_per_minute`.
- A profile or scope action that requires approval needs an operator-provided approval record via `--approval-file`; this is an auditable workflow acknowledgement, not proof of legal authorization.
- Each run writes a manifest with its scope decision, tool version, exit state, artifact hashes, timeout state, and output-truncation state.
- MCP live execution is disabled unless the MCP host explicitly sets `SEC_CAPSULES_ALLOW_MCP_EXECUTE=1`.

Artifact inspection is explicit and bounded:

```bash
sec-capsules artifact get artifact://run_xxx/artifacts/nuclei.jsonl#L1
```

For an authorized local integration check, install the three ProjectDiscovery tools and run:

```bash
scripts/e2e-local.sh
```

The script starts a local Juice Shop container bound only to `127.0.0.1`, runs the deterministic recipe, and removes the container afterwards.

## Non-Goals

- No autonomous attack planning
- No auto exploit decisions
- No multi-agent framework
- No long-term memory system
- No replacement for Nmap, Nuclei, ZAP, Burp, or other security tools
- No out-of-scope scanning
- No default exposure of raw sensitive output to model context

## Current Interfaces

- CLI: usable v0.1 interface
- MCP: thin adapter, designed around meta-tools
- Python core: importable runtime modules

MCP should expose capabilities, not dozens of direct scanner tools. The intended tool surface is:

```text
search_capsules
get_capsule
run_capsule
run_recipe
get_observation
get_artifact
export_run
```
