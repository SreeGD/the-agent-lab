# Testing Standard

## Framework
pytest only. No unittest.

## File layout
- tests/unit/test_<module>.py        — unit tests
- tests/integration/test_<feature>.py — integration tests
- tests/conftest.py                  — shared fixtures

## Naming
test_<function>_<scenario>_<expected>
Example: test_resume_tailor_empty_jd_raises_value_error

## Coverage requirements
- Every new public function: 1 happy-path + 1 edge-case test minimum
- Every bug fix: a regression test that would have caught the bug

## What NOT to test
- Private helpers — test via the public function that calls them
- LLM output content — test structure and schema, not wording
- LangGraph internals — test the graph's input→output contract only
