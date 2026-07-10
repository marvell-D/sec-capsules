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

