# AGENTS.md

This repository implements `sec-capsules`, a security tool invocation layer for AI agents.

## Project Boundaries

- Keep the project focused on tool cards, safe execution, artifacts, parsers, observations, and evidence.
- Do not turn this into an autonomous pentest agent.
- Do not add exploit automation or agent planning logic.
- Prefer small, testable runtime modules.
- Raw tool output should be stored as artifacts and not returned to the model by default.
- Scope checks must happen before any real tool execution.

## Development

- Run `scripts/ci.sh` before handing off changes.
- Add parser fixtures for any new capsule.
- Add or update capsule docs when changing command behavior.
- Keep CLI and MCP behavior consistent by routing both through core runtime modules.

