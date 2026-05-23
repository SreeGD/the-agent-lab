# 13 — Reflection + Plan-and-Execute (Session 2)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/13_reflection_ollama.py`.

> **Two canonical post-ReAct agent patterns, built side-by-side on the same task.** Reflection adds self-correction (writer + critic loop). Plan-and-Execute adds upfront decomposition (planner → executors → aggregator). Pick the one whose cost shape matches your problem.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation, complete)                           Track A: Agentic Patterns
                                                             Session 1: MCP ✓ (lesson 12)
                                                             ▶ Session 2: REFLECTION + PE  ◄ HERE
                                                             ○ Session 3: Multi-agent + LTM
                                                           Track B: Workflow & Skill
                                                             ○ SDD, Vibe, Skills
                                                           Track C: Alt Architectures
                                                           Track D: Data & Multi-modal
                                                           Track E: Graph Depth
                                                           Track F: Production
```

**Why this lesson now:** every prior agent was ReAct (one model, propose-execute-feedback loop). Real production agents go beyond ReAct when quality matters (Reflection) or when tasks are multi-step (Plan-and-Execute). This lesson builds both so you can feel the difference.

---

## Files involved

| File | Role |
|---|---|
| [`13_reflection_ollama.py`](../ollama/13_reflection_ollama.py) | Writer + critic loop with iteration budget |
| [`13_plan_execute_03_agent_manual.py`](../13_plan_execute_03_agent_manual.py) | Planner emits typed Plan; executor runs each step; aggregator combines |

Both solve the **same task** so you can directly compare outputs and economics.

---

## What problem it solves

ReAct works for ~70% of production agents. It does *not* work well when:

| Problem | Why ReAct struggles |
|---|---|
| **Quality non-negotiable** — wrong answer worse than no answer | ReAct produces *one* output and stops; no self-correction step |
| **Multi-step where order matters** | ReAct decides one step at a time, often realizing too late that an earlier step was wrong |
| **Cost matters** — small model can plan, big model executes | ReAct uses one model for everything; you pay full rates for trivial sub-steps |

**Reflection** adds a quality gate — writer drafts, critic reviews, writer revises until approved. **Plan-and-Execute** adds upfront decomposition — one planner emits the whole plan; executors run each step; an aggregator combines. Both are essential additions to your agentic toolkit.

---

## The analogy

**Reflection** = a writer with an editor sitting next to them.
Writer drafts → editor red-pens → writer revises → loop until editor approves. The output gets better each round.

**Plan-and-Execute** = a project manager running a team.
The PM (planner) breaks the goal into 5 tickets. Each ticket goes to a different engineer (executor). Once all done, the PM (aggregator) reviews and assembles. Linear, no replanning, all upfront.

---

## Visual

```
   REFLECTION (writer + critic)                  PLAN-AND-EXECUTE (planner + executor + aggregator)
   ─────────────────────                         ────────────────────────────────────────────────

           user task                                       user task
               │                                              │
               ▼                                              ▼
         ┌──────────┐                                   ┌──────────┐
         │  WRITER  │  ◄──────┐                         │ PLANNER  │
         │  drafts  │         │                         │  emits   │
         └────┬─────┘         │                         │  Plan    │
              │               │                         │ (typed)  │
              ▼               │ revise                  └────┬─────┘
         ┌──────────┐  feedback│                              │
         │  CRITIC  │─────────┘                               ▼
         │ reviews  │                                ┌──────────────┐
         └────┬─────┘                                │   EXECUTOR   │
              │ approved                             │  runs each   │
              ▼                                      │  step (loop) │
         final answer                                └──────┬───────┘
                                                          ▼
                                                   ┌──────────────┐
                                                   │  AGGREGATOR  │
                                                   │ combines     │
                                                   └──────┬───────┘
                                                          │
                                                          ▼
                                                    final answer

   Loop: writer ↔ critic                          Linear: 1 plan → N steps → 1 reduce
   Variable calls (1+2k where k iterations)       Fixed-ish calls (1 + N + 1)
   Self-correcting; quality climbs                Decompositional; quality from breakdown
```

---

## The concept

### Reflection

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

writer_pipe = writer_prompt | model       # → AIMessage
critic_pipe = critic_prompt | model

draft, feedback = "", ""
for iteration in range(1, MAX_ITERATIONS + 1):
    writer_msg = writer_pipe.invoke({"task": TASK, "prior_draft": draft, "feedback": feedback})
    draft = writer_msg.content

    critic_msg = critic_pipe.invoke({"task": TASK, "draft": draft})
    feedback = critic_msg.content.strip()
    if feedback.upper().startswith("APPROVED"):
        break
```

### Plan-and-Execute

```python
class Step(BaseModel):
    description: str
    rationale: str

class Plan(BaseModel):
    steps: list[Step]

planner = model.with_structured_output(Plan, include_raw=True)
plan: Plan = planner.invoke([
    SystemMessage("Decompose the task into 3-5 ordered subtasks."),
    HumanMessage(f"Task: {TASK}"),
])["parsed"]

step_results = []
for step in plan.steps:
    prior = "\n".join(f"Step {j+1}: {r}" for j, r in enumerate(step_results))
    result = executor_pipe.invoke({"task": TASK, "prior_context": prior, "step": step.description, "rationale": step.rationale})
    step_results.append(result.content)

final = aggregator_pipe.invoke({"task": TASK, "step_results": combined})
```

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/13_reflection_ollama.py
python 13_plan_execute_03_agent_manual.py
```

Both files solve the same task: *"Write a 3-paragraph technical explainer about prompt caching for a senior backend engineer."*

---

## Real numbers — same task, same model

```
                    Reflection      Plan-and-Execute
─────────────────────────────────────────────────────
iterations / steps:      1                 4
LLM calls:               2                 6
input tokens:          881              5,812
output tokens:         477              3,153
wall clock:           17 s               60 s
─────────────────────────────────────────────────────
                                  PE was 6.6× more calls
                                  and 3.5× slower for this task
                                  (no API cost with Ollama)
```

**But** PE produced a much more detailed, structured artifact. The extra inference time bought more depth.

The reflection critic approved on iteration 1 — meaning the writer nailed it first try (or the critic was lenient). When that happens, Reflection skips the extra calls. **That's the point** — Reflection only pays for iteration when iteration is needed.

---

## Walk-through

### Reflection's iteration economics

```
iteration 1: write → critique → if approved: done (2 LLM calls total)
iteration 2: revise → critique → if approved: done (4 calls total)
iteration 3: revise → critique → if approved: done (6 calls total)
...
```

Linear time growth per iteration. Hard cap with `MAX_ITERATIONS` so a stubborn critic can't run indefinitely.

### Plan-and-Execute's fixed-ish cost

```
1 planner call + N executor calls + 1 aggregator call = 2 + N total
```

Predictable. Set `temperature=0` on the planner; the plan shape is stable. The cost surprise is N (depends on how aggressively the planner decomposes).

### When to use which

| Scenario | Pick |
|---|---|
| Single answer that needs to be high quality (essay, code review, draft) | Reflection |
| Multi-step task with clear sub-steps (research → write → edit; scaffold → implement → test) | Plan-and-Execute |
| The first draft is usually good enough | Reflection (skips extra calls when not needed) |
| The task has hidden complexity the model would otherwise miss | Plan-and-Execute (forces full decomposition) |

### Variants worth knowing

- **Reflexion** — Reflection with *persistent memory* of past failures. Better for agents that retry the same task category (e.g., a debugging agent that remembers "I tried fix X last time")
- **ReWOO** — Plan-and-Execute with **no replanning**. One big plan, executed without observation feedback. Cheaper but more brittle. Use when steps are mechanical

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| Reflection on code generation | Writer = code-gen agent; critic = linter/test-runner; loop until tests pass |
| Reflection on document drafting | Writer = LLM; critic = style-guide enforcer or domain expert |
| Plan-and-Execute for research | Planner: "search X, search Y, synthesize"; executors run each search; aggregator writes report |
| Plan-and-Execute for codebases | Planner: "scaffold → implement → test → docs"; executors run each phase |
| Plan-and-Execute with cheap planner | Use a smaller model (e.g. `llama3.2:3b`) for planning, larger for execution — reduce latency |
| ReWOO for ETL-style pipelines | Mechanical multi-step with no need for replanning |

---

## Try this

1. **Tighten the critic rubric** — force more iterations. Add criteria like *"every paragraph must cite a specific number"*. Watch the loop go to iteration 2-3.
2. **Use a smaller model for the planner** — switch the planner's model to `llama3.2:3b`. Watch latency drop while quality holds.
3. **Add a "should I replan?" gate** — after each executor step, ask the model whether the plan still makes sense. Convert PE into iterative PE.
4. **Combine them** — wrap the PE output in a Reflection loop. Now you have decomposition AND quality gating.
5. **Try ReWOO** — remove the per-step executor loop and the aggregator; have the planner emit the full final answer directly. Compare quality.

---

## Mental model in one line

> **Reflection iterates on one draft until quality is good enough. Plan-and-Execute decomposes once and runs each step. Reflection costs grow per iteration; PE costs grow per step. Pick the one whose cost shape matches your problem.**

---

## FAQ

**Q: Why did the critic approve on iteration 1?**

A: The writer prompt was strong, the task was bounded, and the critic's criteria were satisfiable in one draft. **This is desired behavior** — Reflection only pays for iteration when iteration is needed. To force more iterations: tighten the rubric ("each paragraph must include 2+ specific numbers"; "each claim must cite a source") and re-run.

**Q: Should the writer and critic use different models?**

A: Yes, ideally. Same-model critique tends toward agreement (the critic shares the writer's blind spots). Use different system prompts to break the agreement bias. In production, you might use the same base model with very different system prompts.

**Q: How is Reflection different from just running the writer twice?**

A: The critic specifically identifies what's wrong. Running the writer twice gives you two attempts but no feedback signal. Reflection's value is in the structured feedback that goes back into the writer's next attempt.

**Q: What's the right `MAX_ITERATIONS`?**

A: 3-5 for most tasks. Beyond 5, you're usually fighting a too-strict critic rather than improving the draft. **Hard cap is non-optional** — without it a critic can loop forever consuming local GPU resources.

**Q: For Plan-and-Execute, why use `with_structured_output` for the planner?**

A: To enforce the plan shape. A free-form planner can emit "I'd suggest doing X, then maybe Y" — ambiguous. A typed `Plan(steps: list[Step])` planner *must* emit a valid Plan or fail validation. That makes the downstream executor loop reliable.

**Q: Can I parallelize the executor steps?**

A: Only if steps are independent (no `depends_on`). For dependent steps (e.g., "step 2 needs step 1's output"), they must run sequentially. The Plan schema can express this with a `depends_on: list[int]` field per step; the executor builds a DAG and runs independent steps in parallel.

**Q: Can I combine Reflection and Plan-and-Execute?**

A: Yes — common in production. Use PE for the overall flow; wrap individual steps (or the final aggregator output) in Reflection for quality. **Layered patterns are the norm in mature agentic systems.**

**Q: How do these relate to ReAct?**

A: ReAct = one agent, one loop, tool calls. Reflection = two agents, iterative quality gate. PE = three agents (planner/executor/aggregator), upfront decomposition. All three are "agentic," but the topology is different. See [reference-agentic-patterns](../reference-agentic-patterns.md) for the side-by-side.

---

## Related

- **Previous:** [12 — MCP](12-mcp.md) (Session 1 of the 32-session curriculum)
- **Next:** Session 3 — Multi-agent + Long-term Memory
- **Pattern reference:** [reference-agentic-patterns](../reference-agentic-patterns.md)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 2 of 32
