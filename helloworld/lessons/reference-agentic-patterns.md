# Reference — Agentic Patterns (one-pager)

Three core patterns cover ~95% of production agents. Everything else is a variation, layering, or refinement.

This is a **reference page** — not part of the linear lesson sequence. Land here when picking a pattern for a real task.

---

## Roadmap — where this reference fits

```
═══════ PHASE 1: FOUNDATION ═══════           Reference docs (read when relevant)

  ✓ 01-12 (foundation lessons)                ▶ reference-agentic-patterns  ◄ YOU
                                              ○ visual-summary

═══════ PHASE 2: ADVANCED PATTERNS ═══════

  Session 2 — Reflection + Plan-and-Execute   ← BUILDS the patterns on this page
  Session 3 — Multi-agent
  ...
```

Read this **before Session 2** to map the patterns to code, and **come back** whenever you're picking between ReAct / Reflection / Plan-and-Execute on a real task.

---

## Side-by-side

| | **ReAct** | **Reflection** | **Plan-and-Execute** |
|---|---|---|---|
| **Core idea** | Think → act → observe → repeat | Draft → critique → revise | Plan all steps → execute → aggregate |
| **Agents involved** | 1 (loops on itself) | 2 (writer + critic) | 2-3 (planner + executor + aggregator) |
| **Decision shape** | One step at a time | Quality gate at each iteration | All upfront |
| **LLM calls per task** | 1 to N (N = tool steps) | 2 to 2k (k iterations) | 1 + N + 1 (~fixed) |
| **Self-correcting?** | No | Yes (explicit critic) | No (one-shot plan) |
| **Decomposes upfront?** | No | No | Yes |
| **Cost-tunable?** | Limited | Iteration budget | Use cheap model for planner |
| **Best for** | Tool-heavy, conversational, ambiguous | Quality-critical, creative | Multi-step workflows |
| **Worst for** | Hard multi-step with order | Simple Q&A (overkill) | Conversational (no plan needed) |

---

## ReAct — *Reason + Act*

**Shape:**

```
  model.invoke(history)  →  AIMessage with tool_calls
       ▲                          │
       │                          ▼
       └─── append result ── run tool
```

**Use when:** the task involves tools, the next step depends on what you observe, and you don't know the shape of the answer upfront.

**Don't use when:** the task is multi-step in a way where order matters and the model would benefit from seeing the whole picture before starting.

**Common problems:**
- **Repeated tool calls** — model calls the same tool with slight variations because it forgets it already tried (mitigate: trim history, summarize prior tool results)
- **Wandering** — agent loops without converging (mitigate: recursion limit, "you have N steps left" in the prompt)
- **Bad first step locks in bad path** — once committed, the model rarely backtracks (mitigate: pair with Reflection)

**Examples:** customer support, calculator-with-tools, Q&A over a KB, conversational coding assistant.

**In this repo:** `agent.py`, `agent_lg.py`, `agent_chatbot.py`, `production_chatbot.py` — all ReAct.

---

## Reflection — *self-critique → revise*

**Shape:**

```
       ┌──────────┐                                 
       │  WRITER  │  ◄──────┐                       
       │  drafts  │         │                       
       └────┬─────┘         │                       
            ▼               │ revise                 
       ┌──────────┐  feedback│                       
       │  CRITIC  │─────────┘                       
       │ reviews  │                                  
       └────┬─────┘                                  
            │ approved                                
            ▼                                        
       final answer                                  
```

**Use when:** the cost of a wrong answer is much higher than the cost of an extra LLM call. Output quality matters more than latency.

**Don't use when:** transactional Q&A, low-stakes chat, anywhere the user expects a one-shot response.

**Common problems:**
- **Critic-writer collusion** — same model in both roles agrees with itself (mitigate: different system prompts, optionally different models, hard rubric)
- **Iteration explosion** — critic always nitpicks (mitigate: hard iteration budget, "approve" if criteria met)
- **Cost runaway** — 2-5× base cost (mitigate: cache writer/critic prompt prefixes; use smaller critic model)
- **Echoing not revising** — writer regenerates similar drafts (mitigate: feed back specific feedback, not just "try again")

**Examples:** code review (writer + linter-critic), legal/medical draft generation, marketing copy with brand-voice critic, technical documentation with accuracy critic.

**Variant — Reflexion:** like Reflection but agent maintains *persistent memory* of past failures across runs. Better for agents that retry the same task category.

---

## Plan-and-Execute — *plan all → execute each → aggregate*

**Shape:**

```
       user task
           │
           ▼
      ┌──────────┐
      │ PLANNER  │  ── emits typed Plan (list of Steps)
      └────┬─────┘
           ▼
   ┌──────────────┐
   │   EXECUTOR   │  ── loops over Plan.steps
   │  runs each   │
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │  AGGREGATOR  │  ── combines results
   └──────┬───────┘
          ▼
    final answer
```

**Use when:** the task is genuinely multi-step, steps are independent or have known dependencies, and a small model can do the planning while a larger model does the execution.

**Don't use when:** single-step tasks, conversational chat, anything where the user's intent is ambiguous.

**Common problems:**
- **Bad plan poisons the whole run** — if the planner mis-decomposes, no amount of executor smartness recovers (mitigate: typed `Plan` schema; validate before executing; pair with Reflection on the plan itself)
- **No replanning when reality differs** — executor hits something unanticipated (mitigate: "should I replan?" gate, or switch to ReWOO)
- **Sub-step context loss** — step 3 doesn't know what step 1 produced (mitigate: pass prior step results as context)
- **Aggregator hallucination** — final summarizer adds things the steps didn't produce (mitigate: structured aggregator output; faithfulness check)

**Examples:** research agents, coding workflows (scaffold → implement → test → docs), data pipelines, report generation.

**Variant — ReWOO (Reasoning WithOut Observation):** Plan-and-Execute with **no replanning step**. One big upfront plan, executed without feedback. Cheaper but more brittle.

---

## Other patterns worth knowing

- **Chain of Thought (CoT)** — write reasoning before the answer; trick: put a `reasoning: str` field *first* in your Pydantic model
- **Self-Consistency** — run N parallel attempts; take majority answer. Reduces variance at N× cost
- **Tree of Thoughts (ToT)** — branching exploration of reasoning paths; useful for puzzles, search-heavy problems
- **Self-Ask** — agent explicitly asks itself sub-questions before the final answer (cheap cousin of PE)
- **Constitutional AI** — rule-based self-critique using a fixed "constitution." Anthropic's flavor of Reflection
- **Verifier / Judge** — external LLM or program validates output; used in evals and as output-side guardrails
- **Tool-Use w/ Retry** — baby Reflection: try a tool, retry with error appended on failure
- **Multi-agent (Supervisor / Swarm)** — N specialists coordinated by a router; *between* agents, not *within* one

---

## Common problems across ALL patterns

1. **Cost explosion** — every pattern multiplies LLM calls. Always instrument; always set hard budgets.
2. **Hallucination compounds** — bad first step poisons later steps. Add a verifier/grounding check at the output.
3. **Loop budgets are non-optional** — every iterative pattern needs a max-iterations safety floor.
4. **Eval is harder than building** — for any pattern beyond ReAct, you need to measure whether complexity helps. See Track F evaluation.
5. **Single-model self-critique is weak** — using the same model as producer and critic gives diminishing returns fast. Use different models, or at least different system prompts.
6. **The "prompt loop" trap** — when an agent doesn't work, the temptation is to add more prompt instructions. Often the answer is *less* prompt + a better pattern.

---

## Pick-the-right-pattern decision tree

```
   "What kind of task?"
         │
         ├── "Single answer, ambiguous, needs tools"        → ReAct
         ├── "Quality-critical, drafting, creative"          → Reflection
         ├── "Multi-step workflow with known structure"      → Plan-and-Execute
         ├── "Mechanical multi-step, no feedback needed"     → ReWOO
         ├── "Hard reasoning, variance reduction"            → Self-Consistency
         ├── "Search / branching exploration"                → Tree of Thoughts
         └── "Multiple specialist domains"                   → Multi-agent (Session 3)
```

---

## Mental model in one line

> **ReAct decides one step at a time. Reflection adds a quality gate after each draft. Plan-and-Execute decides everything upfront. Pick the one whose cost shape and failure mode match your task.**

---

## Related

- **Foundation for the agent loop:** [03 — Agent tool loop](03-agent-tool-loop.md)
- **The 32-session curriculum where these are built:** [`../CURRICULUM.md`](../CURRICULUM.md) — Sessions 2-3 (Reflection + PE, Multi-agent)
- **Visual map of the whole course:** [visual-summary](visual-summary.md)
