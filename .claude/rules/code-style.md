# Code Style Rules

## Python
- Type hints on all public function signatures
- Descriptive names with auxiliary verbs: is_active, has_permission, should_retry
- No single-letter variables except loop indices (i, j, k)
- Early returns over deep nesting
- Max function length: 50 lines — split if longer
- No commented-out code — delete or commit

## Imports
- stdlib → third-party → local (separated by blank lines)
- Absolute imports only; no relative imports

## Comments
- Write WHY, not WHAT — code explains what, comments explain intent
- No multi-line comment blocks; one short line max
- No docstring novels — one sentence for simple functions

## Formatting
- ruff format is the enforcer; do not argue with it
