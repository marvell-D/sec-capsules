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
sec-capsules describe nuclei --level usage
sec-capsules plan nuclei --target http://localhost:3000 --scope examples/juice-shop-local/scope.yml
sec-capsules run nuclei --target http://localhost:3000 --scope examples/juice-shop-local/scope.yml --fixture src/sec_capsules/capsules/nuclei/fixtures/sample.jsonl
```

The `run` command defaults to fixture or dry-run oriented behavior. Real tool execution requires `--execute`.

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

