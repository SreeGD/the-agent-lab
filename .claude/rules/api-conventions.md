# API Conventions

## FastAPI routes
- Path params for resource identity: /users/{user_id}
- Query params for filtering/pagination: ?limit=20&offset=0
- Request bodies via Pydantic models — never raw dicts
- Always return typed response models (not dict)
- HTTP 422 for validation errors (FastAPI default — keep it)
- HTTP 409 for business-logic conflicts (not 400)

## LangChain / LangGraph
- Use with_structured_output() for typed LLM responses
- Prefer ainvoke/astream for all production I/O-bound calls
- State TypedDict over dataclass — LangGraph requires it
- Never mutate state in place — return a new dict slice

## Anthropic SDK (direct)
- claude-opus-4-7: no temperature parameter (deprecated in 4.x)
- claude-sonnet-4-6, claude-haiku-4-5: temperature=0 for determinism
- Always set max_tokens explicitly — never rely on default
