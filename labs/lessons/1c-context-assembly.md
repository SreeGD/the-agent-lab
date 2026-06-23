# 1c — Context Assembly (Session 1c)

> **The context window is not a dump — it's a curated model input.** Every token Claude sees on a single call is a deliberate choice: system prompt, tools, memory, RAG docs, conversation history. Context assembly is the engineering discipline of deciding what goes in, what stays out, and how much budget each slot gets.

---

## Roadmap — where this lesson sits

```
═══════ TRACK A: AGENTIC PATTERNS ═══════

  ✓ Session 1:  MCP (Model Context Protocol)
  ✓ Session 1b: A2A (Agent-to-Agent Protocol)
  ▶ Session 1c: CONTEXT ASSEMBLY  ◄ HERE
    Session 2:  Reflection + Plan-and-Execute
    Session 3:  Multi-agent + Long-term Memory
```

**Why here:** Sessions 1 and 1b covered the protocol stack — how agents talk to tools (MCP) and to each other (A2A). Session 1c bridges to the agent loop internals: before Claude can reason, *someone* has to decide what it sees. That someone is your context assembly layer.

---

## Files involved

| File | Role |
|---|---|
| [`1c_context_assembly.py`](../1c_context_assembly.py) | Dynamic context composer with slot budgets |

---

## What problem it solves

Most engineers start with this approach to context:

```python
messages = [
    {"role": "system", "content": GIANT_SYSTEM_PROMPT},
    *conversation_history,   # all of it
    *all_retrieved_docs,     # everything from RAG
    {"role": "user", "content": user_query}
]
```

Problems:
1. **Token cost** — you pay for every token on every call. Unbounded history = unbounded cost.
2. **Attention dilution** — models perform worse with noisy, irrelevant context. "Lost in the middle" is a documented phenomenon: information buried deep in a long context is less likely to be used.
3. **Context window exhaustion** — exceed the limit and the call fails, or earlier content gets truncated silently.
4. **No control** — when something goes wrong, you can't reason about *what the model saw*.

Context assembly solves this by making the composition explicit and bounded.

---

## The analogy

Think of the context window as a **briefing packet** given to an analyst before a meeting.

A bad briefing: photocopy every document in the filing cabinet and hand it over. The analyst either ignores most of it or gets confused.

A good briefing: curate exactly what the analyst needs — the agenda, the three most relevant prior meeting notes, the key data points, the open questions. Nothing else.

The context window has the same constraint. The model's "attention" is finite. **Curate, don't dump.**

---

## Visual: context slots

```
  ┌─────────────────────────────────────────────────────┐
  │              CONTEXT WINDOW (e.g. 200k tokens)       │
  ├───────────────┬──────────────────────────────────────┤
  │ System prompt │ ~1k tokens  (identity + hard rules)  │
  ├───────────────┼──────────────────────────────────────┤
  │ Tools         │ ~2k tokens  (tool schemas)            │
  ├───────────────┼──────────────────────────────────────┤
  │ Memory        │ ~1k tokens  (retrieved facts/decisions│
  ├───────────────┼──────────────────────────────────────┤
  │ RAG docs      │ ~8k tokens  (top-k retrieved chunks)  │
  ├───────────────┼──────────────────────────────────────┤
  │ History       │ ~4k tokens  (recent N turns only)     │
  ├───────────────┼──────────────────────────────────────┤
  │ User query    │ ~0.5k tokens                          │
  ├───────────────┼──────────────────────────────────────┤
  │ Reserved      │ ~4k tokens  (for model's response)    │
  └───────────────┴──────────────────────────────────────┘
  Total: ~20.5k tokens used out of 200k available
         (leaves headroom for complex multi-turn sessions)
```

Each slot has a **budget** and a **selection strategy**. The context assembler fills each slot up to its budget, then stops.

---

## Key patterns

### 1. Slot-based budget allocation

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class ContextSlot:
    name: str
    max_tokens: int
    priority: int          # lower = evicted first under pressure
    loader: Callable       # returns the content for this slot

SLOTS = [
    ContextSlot("system",  max_tokens=1000,  priority=1, loader=load_system_prompt),
    ContextSlot("tools",   max_tokens=2000,  priority=2, loader=load_tool_schemas),
    ContextSlot("memory",  max_tokens=1000,  priority=3, loader=load_relevant_memory),
    ContextSlot("rag",     max_tokens=8000,  priority=4, loader=load_rag_docs),
    ContextSlot("history", max_tokens=4000,  priority=5, loader=load_recent_history),
]
```

### 2. Dynamic composition

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4")  # claude uses same tokenizer approximately

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

def assemble_context(query: str, session_id: str, budget: int = 16_000) -> list[dict]:
    remaining = budget
    messages = []

    for slot in sorted(SLOTS, key=lambda s: s.priority):
        content = slot.loader(query=query, session_id=session_id)
        tokens = count_tokens(content)

        if tokens <= remaining:
            messages.append({"role": "system" if slot.name == "system" else "user",
                              "content": content})
            remaining -= tokens
        else:
            # Truncate to fit budget
            truncated = truncate_to_tokens(content, remaining)
            if truncated:
                messages.append({"role": "user", "content": truncated})
            remaining = 0
            break  # no budget left

    messages.append({"role": "user", "content": query})
    return messages
```

### 3. History windowing

Don't send all conversation history — send the last N turns or last K tokens, whichever comes first:

```python
def load_recent_history(query: str, session_id: str,
                        max_turns: int = 6,
                        max_tokens: int = 4000) -> str:
    history = get_history(session_id)  # all turns
    recent = history[-max_turns:]       # last N turns
    text = format_history(recent)

    # Further trim if over token budget
    while count_tokens(text) > max_tokens and recent:
        recent = recent[1:]             # drop oldest
        text = format_history(recent)

    return text
```

### 4. The curate-don't-dump principle

Three questions before adding anything to context:

1. **Would Claude answer better with this?** If removing it wouldn't change the output, it's noise.
2. **Is this the right granularity?** A full document vs. the relevant paragraph? RAG chunk vs. the whole file?
3. **Does this belong in this turn?** Some context is needed once (system prompt), some per-turn (RAG), some never in context (static reference docs → tool call instead).

### 5. What goes where

| Content | Slot | Strategy |
|---|---|---|
| Agent identity, hard rules | System prompt | Always present, small, cached |
| Tool definitions | Tools | Always present; exclude tools irrelevant to this task |
| User facts, preferences | Memory | Retrieved by relevance to query |
| Reference documents | RAG | Top-k by cosine similarity to query |
| Conversation | History | Last N turns; summarise older turns |
| Large static docs | Tool call | Never in context — retrieve on demand |
| Code files | Read tool | Never dump full files — read relevant sections |

---

## Run it

```bash
python 1c_context_assembly.py
```

Expected output:

```
Context Assembly Demo
─────────────────────
Query: "What's the best chunking strategy for my PDF pipeline?"

Slot budgets:
  system   → 847 tokens  (used 847 / 1000)
  tools    → 512 tokens  (used 512 / 2000)
  memory   → 203 tokens  (used 203 / 1000)
  rag      → 6,241 tokens (used 6,241 / 8000)
  history  → 1,102 tokens (used 1,102 / 4000)
  query    → 12 tokens

Total: 8,917 / 16,000 tokens (55.7% utilised)
Headroom: 7,083 tokens for response

Context assembled in 23ms
```

---

## Walk-through

### Lost in the middle — why position matters

Research shows LLMs recall information at the start and end of a long context significantly better than information in the middle. Implications for slot ordering:

```
BEST positions for critical content:
  [START]  System prompt, hard rules, user identity
  [END]    The current user query

WORST position for critical content:
  [MIDDLE] Conversation history, RAG docs

Implication: put RAG docs close to the query (near the end),
not buried after a long history.
```

Concrete slot ordering recommendation:
```
1. System prompt    (start — always recalled)
2. Memory facts     (start — high recall)
3. History          (middle — acceptable loss)
4. RAG docs         (near end — high recall)
5. User query       (end — always recalled)
```

### Summarise, don't truncate history

When history exceeds budget, don't just drop the oldest turns — summarise them:

```python
def summarise_history(turns: list[dict], model: ChatAnthropic) -> str:
    response = model.invoke([
        SystemMessage("Summarise this conversation in 3-5 bullet points. "
                      "Preserve: decisions made, key facts established, open questions."),
        HumanMessage(format_history(turns))
    ])
    return f"[Earlier conversation summary]\n{response.content}"
```

A 2,000-token summary of 10,000 tokens of history retains more signal than truncation.

### Cache the expensive slots

System prompt and tool schemas don't change between turns. Cache them with Anthropic's prompt caching to avoid re-paying for them:

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    model_kwargs={
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}  # cache this slot
            }
        ]
    }
)
```

A cached system prompt costs ~10% of the normal input token price. At 1,000 tokens × 100 calls/day, that's ~90% savings on the system prompt alone.

---

## Try this

1. **Budget experiment** — set `max_tokens=2000` for the RAG slot and run the assembler on a query that retrieves many chunks. Observe which chunks get dropped. Try reordering the chunks before truncation to keep the most relevant ones.

2. **Lost-in-the-middle test** — put a key fact at the start of context, the middle, and the end (three separate tests). Ask the same question. Compare answer quality. You'll see the middle recall penalty directly.

3. **History summarisation** — build a 20-turn conversation, then call the summariser. Compare the summary to the original. What did it preserve? What did it lose?

4. **Slot tracing** — add logging to each slot loader that records what it included and excluded. After 10 calls, analyse the logs: which slots are consistently under-budget? Over-budget? Adjust the allocation.

5. **Prompt cache hit rate** — add `cache_control: ephemeral` to the system prompt slot. After 50 calls, check your Anthropic usage dashboard. What fraction of system-prompt tokens are cache hits? (Target: >80% for stable system prompts.)

---

## Mental model in one line

> **Context assembly is slot-based budgeting: assign a token budget to each input type (system, tools, memory, RAG, history), fill each slot with the most relevant content up to its budget, order slots so critical content lands near the start or end, and cache the stable slots to cut costs.**

---

## Related

- **Previous:** [1b — A2A Protocol](12b-a2a-protocol.md)
- **Next:** [Session 2 — Reflection + Plan-and-Execute](13-reflection-plan-execute.md)
- **Prompt caching (cost savings):** [04 — Prompt Caching](04-prompt-caching.md)
- **RAG retrieval (fills the RAG slot):** [09 — RAG](09-rag.md)
- **Memory (fills the memory slot):** [14 — Multi-Agent + LTM](14-multi-agent-ltm.md)
- **Skills and rules (extend the system slot):** [17 — Claude Skills](17-claude-skills.md)
- **Curriculum tracker:** Session 1c of 46
