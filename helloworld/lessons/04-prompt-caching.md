# 04 — Prompt Caching

> **Mark stable parts of your prompt with `cache_control` and Anthropic reuses the precomputed KV state on subsequent calls — 90% cheaper inputs, 50-80% faster.** One keyword. Massive win at scale.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01 model wrapper          (hello.py)                   ○ 13 system     ○ 16-19 Healthcare
  ✓ 02 LCEL composition       (chain.py)                       design       ○ 20-22 Agriculture
  ✓ 03 agent tool loop        (agent.py, agent_lg.py)      ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
  ▶ 04 PROMPT CACHING  ◄═══════ YOU ARE HERE                                ○ 29-32 Family AI

  ○ 05 structured output      (structured.py)
  ○ 06 parallel chains        (parallel.py)
  ○ 07 output parsers         (parsers.py)
  ○ 08 chatbot memory         (agent_chatbot.py)
  ○ 09 RAG                    (rag.py)
  ○ 10 guardrails             (safe_rag.py)
  ○ 11 production capstone    (production_chatbot.py)
  ○ 12 MCP                    (mcp_server.py, mcp_client.py)
```

**Why this lesson now:** by lesson 3 you've built a tool-calling agent. Token costs grow turn-over-turn because each call re-sends the whole history. Caching is *the* lever to keep multi-turn agents affordable — pairs naturally with everything that follows (chatbots in 08, RAG in 09).

---

## Files involved

| File | Role |
|---|---|
| [`agent_lg_cached.py`](../agent_lg_cached.py) | Same agent as `agent_lg.py`, plus a cached system prompt — 76% cheaper per warm run |

---

## What problem it solves

LLMs charge per token, and **every turn of a multi-turn agent re-sends the entire conversation history**:

```
turn 1:   640 in
turn 2:   818 in     ← 818 of which 818 already seen
turn 3:  1100 in     ← 1100 of which 1100 already seen
...
turn N: linear growth
```

You pay full price for tokens the model **just processed**. A 10-turn agent doesn't cost 10× turn 1 — it costs `1+2+3+...+10 = 55×`.

Prompt caching breaks this:
- Mark a stable prefix (system prompt, tool schemas, long context) with `cache_control`
- Anthropic caches the precomputed **KV cache state** server-side for ~5 minutes
- Subsequent requests with the same prefix bill cached tokens at **$0.30 / 1M** instead of **$3 / 1M** — 90% off

Net: multi-turn agents become economically viable at scale.

---

## The analogy

A **chef who does the prep work once**.

Without caching: you order the same complex curry every day. The chef chops onions, grinds masala, simmers the base — 30 minutes of prep — *every time*, fresh.

With caching: you order it on Monday and the chef notes the recipe. On Tuesday, the prep is already done (in the fridge from yesterday). The chef heats the base, finishes the dish, plates. **20 minutes of prep skipped; cost drops accordingly.**

In LLM terms:
- "Prep work" = computing the KV cache state for your system prompt + tools + long context
- "Already done" = stored in GPU memory for 5 minutes after the first request
- You still send the full prompt every time, but **the server skips re-computing the cached portion**

---

## Visual

```
WITHOUT caching                          WITH caching (warm run)
───────────────                          ──────────────────────

Your code → Anthropic                    Your code → Anthropic
   full prompt                              full prompt
   (system + tools                          (system + tools + history)
    + history)                              (cache_control marker on system)
        │                                      │
        ▼                                      ▼
   Anthropic GPU:                          Anthropic GPU:
   ╔══════════════════╗                    ╔══════════════════╗
   ║ prefill ALL      ║                    ║ load cached KV   ║  ← free-ish
   ║ tokens through   ║                    ║ for the marked   ║    (~10% of
   ║ all 80 layers    ║                    ║ prefix           ║     full price)
   ║                  ║                    ╟──────────────────╢
   ║ ~hundreds of ms  ║                    ║ prefill ONLY new ║
   ║ COMPUTE-BOUND    ║                    ║ tokens after     ║
   ║                  ║                    ║ the marker       ║
   ╚══════════════════╝                    ╚══════════════════╝
        │                                      │
        ▼                                      ▼
   bills 100% of                           bills:
   input tokens at                          - cached tokens @ 0.1x
   $3/M                                     - new tokens @ 1.0x
                                            = ~10-25% of original cost
```

The cache is server-side. Your code looks identical except for the `cache_control` marker.

---

## The concept

```python
from langchain_core.messages import SystemMessage

cached_system = SystemMessage(
    content=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT,           # 1500+ tokens for it to be cacheable
            "cache_control": {"type": "ephemeral"},  # ← the magic keyword
        }
    ]
)

agent = create_react_agent(
    model,
    tools=[...],
    prompt=cached_system,
)
```

That's the change. The `cache_control` block tells Anthropic: "Cache the prefix up to this point."

---

## The code

`agent_lg_cached.py` is the same agent as `agent_lg.py`, plus:

- A long system prompt (~1500 tokens — Sonnet's minimum cacheable size is ~1024)
- A `cache_control` block on that system message
- Token tracking that breaks input into fresh / cache_read / cache_create
- A 3-run demo: baseline (no cache_control) vs cold (writes cache) vs warm (reads cache)

---

## Run it

```bash
python agent_lg_cached.py
```

Expected summary (real numbers from a clean run):

```
scenario             fresh    out   c.read   c.create   cost USD     vs baseline
─────────────────────────────────────────────────────────────────────────────────
baseline              4468    141        0          0   $0.01552       —
cached cold            450    141     1807       2211   $0.01230   −20.7%
cached warm              4    141     4389         75   $0.00373   −76.0%
```

**Warm run is 76% cheaper than baseline.** The cold run pays a small write premium and *still* comes out cheaper because it reads back some cached state on later turns.

---

## Walk-through

### What the numbers say

- **Baseline:** all 4468 input tokens billed at full $3/M = $0.0134 input cost.
- **Cached warm:** only **4 tokens** billed at full rate. The other 4389 hit cache at $0.30/M; 75 newly cached at $3.75/M write rate. Input cost drops from $0.0134 → ~$0.0017.
- **76% cheaper per run.** On a 10-turn agent the savings compound (cached prefix gets reused 10×).

### Why the discount is real, not marketing

LLM inference has two phases:

1. **Prefill** — process *all* input tokens through *all* layers. Computes the KV cache. **Compute-bound, dominant cost (60-90% of GPU work).**
2. **Decode** — generate output tokens one at a time. Memory-bandwidth-bound.

With caching, prefill for the cached tokens is **skipped entirely** — replaced with a memory load of the precomputed KV tensors. That's the 80%+ of GPU work that vanishes.

Why not 100% off? Storing KV state in fast memory isn't free, lookup overhead is real, and decode still attends over the cached state. 10% covers that.

### Where to place `cache_control` markers

You can mark up to **4 breakpoints** per request. From start of prompt:

```
┌──────────────────────────┐
│ System prompt            │ ← breakpoint 1 (most stable)
├──────────────────────────┤
│ Tool definitions         │ ← breakpoint 2
├──────────────────────────┤
│ Long static context      │ ← breakpoint 3 (e.g. RAG snippets shared per session)
├──────────────────────────┤
│ Conversation history     │ ← breakpoint 4
├──────────────────────────┤
│ Latest user message      │ ← never cached (always changes)
└──────────────────────────┘
```

Order matters: cached prefix is everything up to and including the marker. Changing the system prompt invalidates every marker after it.

---

## Three rules that bite

1. **Byte-exact caches** — a trailing space, a different timestamp embedded in the system prompt, a re-ordered tool list → cache miss. Linters that "tidy" prompts will silently nuke your hit rate.
2. **Per-API-key + per-org + per-region** — two app instances on different keys don't share a cache.
3. **Minimum cacheable size** — ~1024 tokens for Sonnet, ~2048 for Opus. Caching tiny prompts costs more than it saves.

---

## Production patterns this unlocks

| Pattern | Where caching matters most |
|---|---|
| Multi-turn chatbot | Cache the system prompt + tool schemas; input grows turn-over-turn but cache hit rate climbs |
| RAG with long stable context | Cache retrieved documents that the same user/session will re-query |
| High-volume Q&A | Same instructions reused across users in 5-min windows → cross-user cache hits |
| Long-context analysis | Cache the document once; ask many questions against it |
| Agent with stable tool list | Cache the tool definitions (substantial token cost otherwise) |

---

## Try this

1. **Run twice in a row** — first run pays the write premium; second run shows the full savings.
2. **Wait 6 minutes and re-run** — cache expires after 5 min default TTL; new run pays the write premium again.
3. **Change one character in the system prompt** — cache misses everywhere. Demonstrate byte-exact sensitivity.
4. **Use 1-hour TTL** — `{"type": "ephemeral", "ttl": "1h"}` (2× write premium, but cache survives across user sessions for big shared system prompts).

---

## Mental model in one line

> **Prompt caching is a server-side optimization, transparent to the client. You always send the full prompt; the server decides whether to do the full forward pass or reuse cached state. The `cache_control` marker is a hint about where to draw cache boundaries, not a reference to anything the client holds.**

---

## FAQ

**Q: Does my outbound bandwidth go down with caching?**

A: No. Same bytes on the wire. The optimization is server-side — Anthropic charges you less and runs faster because it skips work, but the request size is identical.

**Q: How can I check if a cache hit actually happened?**

A: Look at `response.usage_metadata.input_token_details`:
```
cache_read     = N  → cache hit; N tokens served from cache
cache_creation = M  → cache write; M tokens written to cache
```
The token report in `agent_lg_cached.py` prints these.

**Q: How long does the cache live?**

A: Default is 5 minutes (ephemeral). Anthropic also offers 1-hour TTL (2× write premium). Cache is silently extended every time you hit it — back-to-back active conversations rarely expire.

**Q: Is the cache shared across users?**

A: Yes — within your API key + org + region. If user A and user B both send a request with the same cached prefix within 5 min, user B benefits from user A's cache write. This is the **shared system prompt** payoff.

**Q: Can I cache the conversation history that grows turn-over-turn?**

A: Yes, but with care. Each turn extends the cached prefix by the previous turn's content. On turn N, you'll see `cache_read = (turn N-1's prefix)` + `cache_creation = (the new turn's content)`. **Incremental caching** — see `agent_lg_cached.py` for the pattern.

**Q: What's the minimum prompt size to cache?**

A: ~1024 tokens for Sonnet, ~2048 for Opus. Below that, caching is silently a no-op. Inflate your system prompt or skip caching for short prompts.

**Q: Does caching work with `tools=[...]`?**

A: Yes — tool definitions are part of the prefix. Mark the system prompt with `cache_control` and the tools (which come before the user message in the wire format) are included in the cached prefix automatically.

**Q: What about cache hits on the output side?**

A: Output is generated per token; it can't be cached the same way. Output stays at full price. Caching helps **input cost**, not output cost. A verbose agent doesn't get cheaper from caching — only its input ingestion does.

**Q: Should I cache everything?**

A: No — caching has a write premium (1.25× for 5-min, 2× for 1-hour). If you only call a prompt **once**, you pay more than the baseline. Caching is for **prompts called repeatedly** (multi-turn, multi-user, multi-query against the same context).

**Q: Is `cache_control` Anthropic-specific?**

A: Yes — the `cache_control` keyword is in Anthropic's Messages API. OpenAI has automatic caching (no marker needed but less control). Gemini supports manual caching with `cachedContent`. The principle is the same; the syntax differs.

---

## Related

- **Previous:** [03 — Agent tool loop](03-agent-tool-loop.md)
- **Next:** [05 — Structured output](05-structured-output.md)
- **Where caching shines:** [08 — Chatbot memory](08-chatbot-memory.md), [09 — RAG](09-rag.md), [11 — Production capstone](11-production-capstone.md)
