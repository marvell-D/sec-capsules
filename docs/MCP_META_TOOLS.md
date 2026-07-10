# MCP Meta-Tools

The MCP interface should expose a small set of meta-tools instead of one tool per scanner.

Current intended surface:

- `search_capsules`
- `get_capsule`
- `run_capsule`
- `run_recipe`
- `get_observation`
- `get_artifact`
- `export_run`

This keeps agent context focused on capabilities and observations instead of flooding the model with scanner-specific tool definitions.

`run_capsule` and `run_recipe` default to non-executing behavior. An MCP host must explicitly set `SEC_CAPSULES_ALLOW_MCP_EXECUTE=1` before either tool accepts `execute=true`; scope checks and approval records still apply after that host-level gate.
