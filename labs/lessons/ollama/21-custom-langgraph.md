# 21 — Custom LangGraph + HITL (Session 10)

> **Provider variant — Ollama (`llama3.2`)** This lesson's code is provider-agnostic — it does not directly instantiate an LLM. No Ollama-specific code file is needed; use the original file unchanged.

> **Drop down from `create_react_agent` to your own `StateGraph`.** Define nodes, conditional edges, and pauses for human approval. The same machinery underneath `create_react_agent` — now exposed for workflows that don't fit the ReAct shape.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═���═════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: ✓ all 3 done
                                                           Track B: ✓ all 3 done
                                                           Track C: ✓ all 2 done
                                                           Track D: ✓ all 1 done
                                                           Track E: Graph Depth
                                                             ▶ Session 10: CUSTOM LangGraph  ◄ HERE  (Track E COMPLETE)
                                                           Track E.5: ○ RAG Architectures
                                                           Track F: ○ Production
```

**Why this lesson now:** every previous agent has been a `create_react_agent` (one specific graph shape). Real workflows often have **phases** (research → draft → review → publish) or **approval gates** (HITL). Sessions 1-9 used graphs without ever calling them graphs. Session 10 lifts the lid.

---

## Files involved

| File | Role |
|---|---|
| [`21_custom_graph.py`](../21_custom_graph.py) | Financial transaction approval — conditional edges + interrupts + 3 scenarios (small/approved/denied) |
| [`21_time_travel.py`](../21_time_travel.py) | Replay a graph from any prior checkpoint with a different decision — same starting state, two outcomes |

These files are provider-agnostic — the LangGraph state machine logic does not require an LLM. Run the originals unchanged.

---

## What problem it solves

`create_react_agent` is a **prebuilt graph**: one model node, one conditional edge (tool_calls? yes/no), one loop. It's perfect for conversational agents that call tools. It's the **wrong shape** for:

- Workflows with explicit phases (research → draft → publish — no looping back to research after drafting)
- Anything with HITL approval gates (pause mid-graph, wait for a human, resume)
- Multi-agent supervisor flows (route to one of N specialists)
- Pipelines with branches that may take very different paths

For those, you build your own graph. Same `StateGraph` machinery — you just specify the topology.

---

## The analogy

**`create_react_agent` is a kit-built model train**: comes assembled, two cars, one loop. Great for conversations on rails.

**Custom LangGraph is the model railway hobby kit**: pieces of track, switches, sidings, stations. You decide the layout. The trains, signals, and switching logic are all the same components — you just lay the track for what you need.

`interrupt()` is the railway version of a red signal that pauses the train at a station until someone manually clears it. The train state is preserved (knows which platform, which destination); when cleared, it resumes from exactly where it stopped.

---

## Visual

```
  Custom graph for transaction approval:

       START
         │
         ▼
   ┌──────────┐
   │ propose  │  amount, recipient, reason → state
   └────┬─────┘
        │
        ▼
   ┌─────────────────────────────────────┐
   │  needs_review(state) — router       │
   │   if amount > $1000 → human_review  │
   │   else              → execute       │
   └────────┬────────────────────────────┘
            │
   ┌────────┼─────────────────────┐
   ▼                              ▼
┌───────────────┐           ┌──────────┐
│ human_review  │           │ execute  │
│   interrupt() │           │          │
│   ⏸ pauses    │           └────┬─────┘
└──────┬────────┘                │
       │ resume                  │
       ▼                          │
   ┌──────────┐                  │
   │ execute  │ ←────────────────┘
   └────┬─────┘
        ▼
       END
```

When `interrupt()` fires, the graph is **paused mid-flow**. State persists in the checkpointer. A separate process (web UI, Slack approval, cron job) can resume hours or days later — same state, same graph, exactly where it left off.

---

## Concept — custom StateGraph

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver


class TxState(TypedDict, total=False):
    amount: float
    recipient: str
    reason: str
    status: str
    approver_note: str


def propose(state):
    return {"status": "proposed"}

def human_review(state):
    # Pauses execution. The dict shown here is what the human sees.
    decision = interrupt({
        "amount": state["amount"],
        "recipient": state["recipient"],
        "prompt": "Approve this transaction?",
    })
    return {"status": "approved" if decision["approved"] else "denied",
            "approver_note": decision.get("note", "")}

def execute(state):
    return {"status": "executed" if state["status"] == "approved" else "blocked"}


def needs_review(state):
    return "human_review" if state["amount"] > 1000 else "execute"


graph = StateGraph(TxState)
graph.add_node("propose", propose)
graph.add_node("human_review", human_review)
graph.add_node("execute", execute)
graph.add_edge(START, "propose")
graph.add_conditional_edges("propose", needs_review, ["human_review", "execute"])
graph.add_edge("human_review", "execute")
graph.add_edge("execute", END)

agent = graph.compile(checkpointer=MemorySaver())
```

That's the whole surface area: nodes, edges, conditional edges, compile, optional checkpointer.

---

## Concept — HITL via `interrupt()`

```python
config = {"configurable": {"thread_id": "tx-001"}}

# Start the graph — runs until the interrupt() in human_review
agent.invoke(
    {"amount": 5000.0, "recipient": "Vendor", "reason": "..."},
    config=config,
)
# At this point the graph is PAUSED. State is in the checkpointer.

# Inspect what the human is being asked
pending = agent.get_state(config)
print(pending.interrupts[0].value)  # the dict passed to interrupt()

# Hours/days later, from a UI or another process:
agent.invoke(
    Command(resume={"approved": True, "note": "Budget pre-approved"}),
    config=config,
)
# Graph resumes, runs execute, finishes.
```

**`Command(resume=...)`** is the mechanism. Whatever you pass becomes the return value of `interrupt()` inside the node. The graph picks up exactly where it stopped.

---

## Concept — time travel

```python
# Get the full state history (newest first)
history = list(agent.get_state_history(config))

# Find a specific historical checkpoint
pre_review = next(h for h in history if h.next == ("human_review",))

# Fork the timeline: inject what human_review WOULD have returned
forked_config = agent.update_state(
    pre_review.config,
    {"status": "denied", "approver_note": "[time travel] reconsidered"},
    as_node="human_review",   # treat this as if it came from that node
)

# Continue from the forked checkpoint
final = agent.invoke(None, config=forked_config)
# Same starting state, different decision, different outcome.
```

---

## Run them

```bash
python 21_custom_graph.py    # 3 scenarios: small / approved / denied
python 21_time_travel.py     # original + forked counterfactual
```

### Real output — three scenarios

```
SCENARIO 1 — small transaction ($50): auto-approve, no HITL
  [propose]      $50.00 to 'Coffee Shop'
  [execute]      ✅ EXECUTED $50.00 → 'Coffee Shop'

SCENARIO 2 — large ($5000) APPROVED
  [propose]      $5000.00 to 'CRM Vendor Inc.'
  [human_review] ⏸ pausing...
  ▶ human decision: APPROVED
  [execute]      ✅ EXECUTED $5000.00

SCENARIO 3 — large ($5000) DENIED
  [propose]      $5000.00 to 'Unknown Vendor'
  [human_review] ⏸ pausing...
  ▶ human decision: DENIED
  [execute]      ❌ BLOCKED
                  approver_note: 'Missing purchase order'
```

### Real output — time travel

```
STEP 1: original timeline approved → status='executed'

STEP 2: history (newest first)
  [ 0] next=(end)         status=executed   amount=5000.0
  [ 1] next=execute       status=approved   amount=5000.0
  [ 2] next=human_review  status=proposed   amount=5000.0
  [ 3] next=propose       status=(none)     amount=5000.0
  [ 4] next=__start__     status=(none)     amount=(none)

STEP 3: rewind to checkpoint [ 2 ] (next=human_review)

STEP 4: fork with DENIAL via update_state(as_node='human_review')
  [execute]      ❌ BLOCKED  (note: '[time travel] reconsidered — denying instead')

BEFORE/AFTER — same starting state, two outcomes
  original timeline:        status='executed'   (approved → executed)
  counterfactual timeline:  status='blocked'    (denied → blocked)
```

---

## Walk-through — the production patterns

### Pattern 1 — HITL approval gates

Anywhere a human must sign off mid-workflow (transactions, deploys, content publishes, medical orders), this is the canonical shape:

```
work → check eligibility → interrupt(reasoning) → execute or block
```

The interrupt is the *only* place a human enters. The rest is fully agent-driven.

### Pattern 2 — Phased workflows

```
draft → classify → review → revise → publish
```

Different from a ReAct loop because the order is fixed and some nodes don't loop back. Easy with conditional edges; impossible with `create_react_agent`'s prebuilt shape.

### Pattern 3 — Counterfactual replay

Time travel as a debugging tool:
- "Show me what the agent would have done if the user had said X."
- "Replay this billing decision under the rejected proposal."

### Pattern 4 — Durable workflows that pause for days

With `PostgresSaver` instead of `MemorySaver`, the graph state lives in your database. An `interrupt()` can pause overnight. The user opens the app the next day, clicks "approve," and the graph picks up. **The agent has no concept of how much time passed** — it sees state at the resume point and continues.

---

## When to use custom LangGraph vs `create_react_agent`

| Use case | Pick |
|---|---|
| Conversational chatbot with tools | `create_react_agent` (it's already a graph; just hidden) |
| Workflow with explicit phases / order | **Custom StateGraph** |
| Any HITL approval gate | **Custom StateGraph** (`interrupt()` is graph-only) |
| Multi-agent supervisor flow | **Custom StateGraph** (or `create_react_agent` with workers-as-tools — both work) |
| Long-running pause-and-resume | **Custom StateGraph** + `PostgresSaver` |
| Time-travel debugging | **Custom StateGraph** (`get_state_history()` is graph-level) |
| One-shot model call, no state | Plain LangChain `prompt \| model \| parser` — graphs are overkill |

---

## Try this

1. **Add a fourth node** — `notify_finance` that runs after `execute` only on transactions over $10,000. Adds another conditional edge after execute.
2. **Resume from a different process** — start the graph, kill the Python script, then start a NEW script that resumes from the same `thread_id`. (Requires `SqliteSaver` so state survives the restart.)
3. **Build a publish workflow** — nodes: draft → classify → human_review (if controversial) → publish. Wire the conditional edge with an LLM-classifier as the router.
4. **Stream events** — use `agent.stream_events()` to print every node entry/exit. Build a tiny dashboard that shows "agent is at: human_review."
5. **Make a subgraph** — extract the proposal logic into its own graph; use it as a single node inside the parent.

---

## Mental model in one line

> **A custom LangGraph is `create_react_agent` with the lid off — same `StateGraph` machinery, but you specify the nodes, edges, conditional routes, and pause points. Add `interrupt()` for HITL. Add a checkpointer for durability + time travel. Add subgraphs for composition. Everything any LLM agent does in production is one of these shapes.**

---

## FAQ

**Q: When does `create_react_agent` stop being enough?**

A: When you need (a) explicit phases (research → draft → publish), (b) HITL gates (pause for human approval), (c) durable pauses (resume hours later), (d) time-travel debugging, (e) multi-agent supervisor flows with custom routing. For plain conversational tool use, ReAct is fine forever.

**Q: How does `interrupt()` differ from raising an exception?**

A: An exception terminates the run. `interrupt()` **persists state and stops cleanly**. The graph can be resumed later (different process, different day) by another call with `Command(resume=...)`. State stays in the checkpointer; the resume value flows back as the return of `interrupt()` inside the node.

**Q: What's the difference between `Command(resume=...)` and `update_state(as_node=...)`?**

A: `Command(resume=...)` resumes a paused interrupt with a value — but only once per thread. The resume value is sticky. `update_state(as_node=...)` directly writes state as if a specific node produced it — useful for forking timelines or correcting earlier state. Use resume for normal HITL; use update_state for time-travel replay.

**Q: Does `interrupt()` require LangGraph cloud / hosted services?**

A: No. Works in any Python process with a checkpointer. For local dev: `MemorySaver`. For production durability across restarts: `SqliteSaver` or `PostgresSaver`.

**Q: How long can a graph stay paused?**

A: As long as the checkpointer's storage. `MemorySaver` dies with the process; `SqliteSaver` lives in a file; `PostgresSaver` lives in your DB. There's no LangGraph-imposed timeout.

**Q: Is custom LangGraph more expensive than `create_react_agent`?**

A: Per LLM call, no. Graphs add zero LLM inference overhead over the nodes you write. The cost is **engineering time** — you write more code. The trade-off is: code complexity for control + reliability + HITL support.

---

## Related

- **Previous:** [20 — Files & Document AI](20-files-document-ai.md)
- **Next:** Session 11 — Hybrid RAG (Track E.5)
- **Builds on:** [03 — Agent tool loop](03-agent-tool-loop.md) (where `create_react_agent` was introduced) and [08 — Chatbot memory](08-chatbot-memory.md) (where `MemorySaver` first appeared)
- **Pattern reference:** [reference-agentic-patterns](../reference-agentic-patterns.md)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 10 of 40 (Track E complete)
