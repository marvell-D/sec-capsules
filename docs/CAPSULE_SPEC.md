# Capsule Spec Draft

Each capsule is a machine-readable security tool card.

Required fields:

- `id`
- `name`
- `category`
- `summary`
- `stage`
- `risk_level`
- `best_for`
- `avoid_when`
- `profiles`
- `outputs`
- `artifacts`
- `model_exposure`
- `next_actions`

Each profile should define:

- `description`
- `active`
- `action`
- `requires_approval`
- `command`

The command is a list of argv tokens. The runtime expands `$target`, `$rate_limit`, and other profile variables.

