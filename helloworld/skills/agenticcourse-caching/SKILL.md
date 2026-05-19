---
name: agenticcourse-caching
description: Use when the user asks about prompt caching, KV cache, cache_control marker, cache hit rate, prefill, cache TTL, or how to reduce LLM input costs. Provides the cache_control rules, the 4 breakpoint placements, byte-exact key sensitivity, write premium economics, and 76%-cheaper math.
---

# Prompt Caching — Rules + Economics

## What it does

Mark a stable prefix in your prompt with `cache_control`. Anthropic caches the KV state (the computed attention key/value tensors at every layer). Subsequent requests reusing that exact prefix skip the prefill compute — billed at ~10% of normal input cost, ~50-80% faster latency.

## The cache_control marker

```python
from langchain_core.messages import SystemMessage

cached_system = SystemMessage(
    content=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},   # ← the magic keyword
        }
    ]
)

agent = create_react_agent(
    model,
    tools=[...],
    prompt=cached_system,
)
```

The cache key is the **entire prefix up to and including** the marker.

## The 4 canonical breakpoints

You can mark up to 4 cache breakpoints per request. From start of prompt:

```
┌──────────────────────────┐
│ System prompt            │ ← breakpoint 1 (most stable)
├──────────────────────────┤
│ Tool definitions         │ ← breakpoint 2
├──────────────────────────┤
│ Long static context      │ ← breakpoint 3 (RAG snippets shared per session)
├──────────────────────────┤
│ Conversation history     │ ← breakpoint 4 (grows turn by turn)
├──────────────────────────┤
│ Latest user message      │ ← never cached (always changes)
└──────────────────────────┘
```

**Critical rule**: changing anything earlier in the prefix invalidates all markers after it. Order matters.

## Three rules that bite

1. **Byte-exact cache keys** — a trailing space, different timestamp embedded in system, reordered tool list → cache miss. Linters that "tidy" prompts can silently nuke hit rates.
2. **Per-API-key + per-org + per-region scoping** — two app instances on different keys don't share a cache.
3. **Minimum cacheable size** — ~1024 tokens for Sonnet, ~2048 for Opus. Below that, caching is a no-op (silent).

## TTLs

| TTL | Write premium | Use when |
|---|---|---|
| 5 minutes (default) | 1.25× | Active conversations, back-to-back messages |
| 1 hour | 2× | Big static context shared across users (50k+ token system + RAG) |

Cache is silently extended on every hit — so 5-minute caches usually outlive their stated TTL in active apps.

## Pricing math (Sonnet 4.6)

| Token type | Multiplier vs base input |
|---|---|
| Normal input | 1× ($3/MTok) |
| Cache write (first time, 5-min TTL) | 1.25× ($3.75/MTok) |
| Cache write (1-hour TTL) | 2× ($6/MTok) |
| Cache read (hit within TTL) | **0.1× ($0.30/MTok)** |
| Output | unchanged ($15/MTok) |

## Real measurement from production_chatbot.py

```
scenario             fresh    out   c.read   c.create   cost      vs baseline
─────────────────────────────────────────────────────────────────────────────
baseline              4468    141        0          0   $0.0155      —
cached cold             4    141     2148       2241   $0.0090   −42%
cached warm             4    141     4389         75   $0.0037   −76%
```

**Warm run is 76% cheaper than baseline.** Cold run pays the write premium but still beats baseline because part of the call already hits cache.

## Why the discount is real (not marketing)

LLM inference has two phases:
- **Prefill** (compute-bound) — process all input tokens, compute KV cache. 60-90% of GPU work.
- **Decode** (memory-bandwidth-bound) — generate tokens one at a time.

Cached tokens skip prefill entirely — KV tensors are loaded from server memory instead of recomputed. That's the 80%+ of GPU work that vanishes, hence the 90% discount.

## When NOT to cache

- Single-turn one-shot prompts (write premium > savings)
- Prompts where every byte is dynamic per request
- Prompts under ~1k tokens (below cacheable minimum)
- Prototypes where the prompt changes every iteration

## How to verify cache hits

Check `response.usage_metadata.input_token_details`:

```
cache_read     = N  → cache hit; N tokens served from cache
cache_creation = M  → cache write; M tokens written to cache
```

If both are 0, caching isn't engaging. Common reasons: prompt too short, cache_control marker missing, byte-different prefix from prior request.

## Mental model in one line

> **Prompt caching is a server-side optimization. The client sends the full prompt every time; the server either does the full forward pass or reuses cached KV state. `cache_control` is a hint about where to draw cache boundaries — not a reference to anything the client holds.**
