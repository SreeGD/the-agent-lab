# 15 — Spec-Driven Development (Session 4)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/15_spec_driven_ollama.py`.

> **Turn a vague intent into a working artifact through four typed phases: Spec → Tasks → Code → VerificationReport.** Every phase produces a Pydantic object the next phase consumes. Phase gates make assumptions explicit. The opposite of vibe coding — slow start, dramatically better outcomes for non-trivial work.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: Agentic Patterns
                                                             ✓ S1: MCP, ✓ S2: Refl+PE
                                                             ✓ S3: Multi-agent+LTM
                                                           Track B: Workflow & Skill
                                                             ▶ Session 4: SDD  ◄ HERE
                                                             ○ Session 5: Vibe Coding
                                                             ○ Session 6: Claude Skills
                                                           Track C-F + Phase 3 verticals
```

**Why this lesson now:** Track A taught agentic *patterns*. Track B is about **workflow patterns** — how an agent should structure its work. SDD is the rigorous workflow used for non-trivial production code. The next lesson (Vibe Coding) is its improvisational opposite — together they bracket the LLM-driven-coding spectrum.

---

## Files involved

| File | Role |
|---|---|
| [`15_spec_driven_ollama.py`](../ollama/15_spec_driven_ollama.py) | Four-phase SDD agent — emits Spec → TaskList → Code → VerificationReport |
| [`generated_wordcount.py`](../generated_wordcount.py) | The artifact the SDD agent produced (a 7.5 KB working CLI word counter) |

---

## What problem it solves

You give an LLM the prompt: *"Build me a CLI tool that counts word occurrences and prints the top N."* Vibe coding gives you code immediately — often broken in subtle ways (no error handling, wrong tie-breaking, no encoding fallback, "what if --top is negative?" never considered).

SDD turns that vague intent into a working artifact by **forcing the agent to think before it codes**:

1. **CLARIFY** — Make every implicit assumption explicit. "Should `Hello` and `hello` count as the same word?" "What about punctuation?" "How do we break ties?" The spec answers all of these *before any code is written*.
2. **DECOMPOSE** — Break the spec into ordered tasks. Each task has a `done_when` criterion.
3. **IMPLEMENT** — Generate code that satisfies the tasks.
4. **VERIFY** — Check every acceptance criterion against the actual code.

The trade-off: more LLM calls, more upfront thinking, **much** higher confidence the artifact does what you wanted.

---

## The analogy

**A house architect vs. a contractor with a hammer.**

The contractor (vibe coding) starts swinging. Sometimes you get a usable shed. Sometimes you discover halfway through that the roof was supposed to be load-bearing but isn't.

The architect (SDD) first sits with you for an hour. *"Where does the front door face? How many bedrooms? Do you want hardwood or carpet? What's the budget?"* You get a blueprint. The contractor then builds from the blueprint. At the end, a building inspector (verifier) walks through and checks every code requirement on a checklist.

You **start slower**, but the building doesn't fall down. For trivial work, the contractor wins. For non-trivial work, the architect wins by a lot.

---

## Visual

```
   INTENT (1 sentence)
   ──────
   "Build a CLI word counter"
            │
            ▼
   ┌────────────────────┐                                          
   │   PHASE 1: CLARIFY │  emits Spec(BaseModel):                  
   │   prompt + model   │    title, description, inputs, outputs,   
   │   .with_structured │    functional_requirements,               
   │   _output(Spec)    │    non_functional_requirements,           
   │                    │    acceptance_criteria[],                 
   │                    │    out_of_scope                           
   └─────────┬──────��───┘                                          
             │ phase gate: no decompose without an approved spec    
             ▼                                                      
   ┌─────────────���──────┐                                          
   │PHASE 2: DECOMPOSE  │  emits TaskList(BaseModel):                
   │                    │    tasks[]: Task(description, done_when)   
   └────────���┬──────────┘                                          
             │ phase gate: no implement without a task list         
             ▼                                                      
   ┌───────��──────���─────┐                                          
   │PHASE 3: IMPLEMENT  │  emits Implementation(BaseModel):          
   │                    │    code: str (the runnable program)        
   │                    │    rationale: str                          
   │                    │  writes generated_wordcount.py to disk     
   └─────────┬─────────��┘                                          
             │ phase gate: no deliver without verification           
             ▼                                                      
   ┌───────���────────────┐                                          
   │ PHASE 4: VERIFY    │  emits VerificationReport:                 
   │                    │    overall_passed: bool                    
   │                    │    criterion_results[]                     
   │                    │      criterion, passed, evidence           
   └─────────┬────────��─┘                                          
             │                                                      
             ▼                                                      
        deliver to user
```

Every phase uses `model.with_structured_output(...)`. Artifacts are typed Pydantic objects, not free-form text.

---

## The concept

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

# Pydantic models for each artifact
class Spec(BaseModel):
    title: str; description: str
    inputs: list[str]; outputs: list[str]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    out_of_scope: list[str]

class TaskList(BaseModel):
    tasks: list[Task]   # Task = (description, done_when)

class Implementation(BaseModel):
    code: str; rationale: str

class VerificationReport(BaseModel):
    overall_passed: bool
    criterion_results: list[CriterionResult]
    notes: str

# Four chains — each emits a typed artifact
spec_phase    = spec_prompt    | model.with_structured_output(Spec,    include_raw=True)
task_phase    = task_prompt    | model.with_structured_output(TaskList, include_raw=True)
impl_phase    = impl_prompt    | model.with_structured_output(Implementation, include_raw=True)
verify_phase  = verify_prompt  | model.with_structured_output(VerificationReport, include_raw=True)

# Run sequentially — phase gates enforce ordering
spec = spec_phase.invoke({"intent": INTENT})["parsed"]
tasks = task_phase.invoke({"spec_json": spec.model_dump_json()})["parsed"]
impl = impl_phase.invoke({
    "spec_json": spec.model_dump_json(),
    "tasks_json": tasks.model_dump_json(),
})["parsed"]
report = verify_phase.invoke({
    "spec_json": spec.model_dump_json(),
    "code": impl.code,
})["parsed"]
```

**The phases are just LCEL chains.** What makes this SDD is the discipline: typed outputs throughout, no skipping, verification at the end.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/15_spec_driven_ollama.py
```

Then run the generated tool:

```bash
python generated_wordcount.py NOTES.md --top 5
```

Output:
```
1. the: 15
2. phase: 8
3. lesson: 6
4. of: 6
5. lessons: 5
```

It works. **The agent produced a runnable artifact end-to-end.**

---

## Real numbers from a clean run

```
phase            in    out   time
─────────────────────────────────
clarify        1154   1336  23.8s
decompose      2042    672  11.6s
implement      2574   2297  31.6s
verify         4010   1270  21.3s
─────────────────────────────────
TOTAL          9780   5575  88.3s
(no API cost — Ollama runs locally)
```

**~90 seconds** for a fully-specified, decomposed, implemented, and verified ~7.5 KB Python program with 7 acceptance criteria. No API cost.

Compare to vibe coding (Session 5 next): maybe 20s, but you have to test, iterate, and trust that the model thought of every edge case.

For prototypes: vibe wins. For production code: SDD wins by a lot. The ~5× inference time buys an audit trail (spec.md, tasks.md, verification_report.md) that you can show a manager, a compliance reviewer, or future-you.

---

## Walk-through

### Phase 1: CLARIFY — make implicit assumptions explicit

Sample acceptance criteria the agent generated for the word-counter intent:

```
✓ "Running `python wordcount.py sample.txt` with a file containing 'Hello
   world hello.' prints exactly '1. hello: 2' as the first line and
   '2. world: 1' as the second line, then exits with code 0."
✓ "Running `python wordcount.py sample.txt --top 1` on a file whose two
   most frequent words are tied alphabetically prints the word that comes
   first alphabetically as rank 1."
✓ "Running `python wordcount.py nonexistent.txt` prints a message containing
   'Error' (case-insensitive) to stderr and exits with code 1."
```

Notice: **specific, testable, no hand-waving.** The agent decided case-insensitivity, tie-breaking, error-exit-code, and stderr-vs-stdout — all from the vague intent. *These are the decisions that bite you in vibe coding.*

### Phase 2: DECOMPOSE — ordered tasks with done_when

The agent produced 7 tasks for the word counter:

```
1. Parse CLI arguments (positional file path + --top N)
   done when: argparse accepts both args, --top defaults to 10
2. Validate the input file exists and is readable
   done when: invalid path prints Error to stderr and exits 1
3. Stream-read the file line by line with UTF-8 encoding
   done when: function yields lines without loading whole file
4. Tokenize each line, lowercase, strip punctuation
   done when: 'Hello,' and 'hello' both produce token 'hello'
... etc.
```

Sequential implementation: task 3 uses the file path from task 1; task 4 consumes tokens from task 3. The order is the architecture.

### Phase 3: IMPLEMENT — generate the code

The agent emitted 7.5 KB of Python — a complete `wordcount.py` with type hints, generators, `argparse`, error handling, regex tokenization, and a top-level `__main__` block. **It compiles and runs on first try.** No human edits.

### Phase 4: VERIFY — every criterion checked against the code

For each acceptance criterion, the verifier returned a `CriterionResult` with a `passed` flag and concrete evidence from the code:

```
✓ "...alphabetical tie-breaking..."
  evidence: "ranked_words() sorts with key=lambda item: (-item[1], item[0]),
             so ties in count are broken by ascending alphabetical order."

✓ "...prints to stderr and exits 1..."
  evidence: "validate_args() checks `if not os.path.exists(args.file)` and
             calls `_exit_error(f"Error: File not found: '{args.file}'.", code=1)`"
```

**Concrete evidence, not vague affirmations.** This is what makes SDD's verification trustworthy — the verifier has to point at code, not just say "yeah looks good."

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| Compliance code review | Spec from policy doc; implementation; verifier checks each policy rule against code |
| Internal tools | Engineer writes one-line intent; SDD agent produces a working internal CLI overnight |
| Test generation | After implementation, an extra phase generates `pytest` tests from acceptance criteria |
| API endpoint scaffolding | Spec → router → handler → tests → docs as ordered phases |
| Refactoring | Phase 1 captures current behavior; phase 2 plans the refactor; phase 4 verifies behavior preserved |
| Onboarding doc generation | Spec from product brief; tasks become article sections; verifier checks coverage |

---

## When to use SDD vs. just write the code yourself

| Use SDD when... | Skip SDD when... |
|---|---|
| Task is non-trivial (>50 lines, multiple components) | Throwaway one-liner |
| Acceptance criteria matter (compliance, contracts, public APIs) | Internal exploration |
| Multiple people will maintain it | One-time script |
| You want an audit trail | Speed > rigor |
| You're delegating to an LLM you don't fully trust | You're writing it yourself anyway |

**Don't reach for SDD on trivial work.** The 90-second overhead is worth it for production code, but it's overkill for "rename this variable."

---

## Try this

1. **Change the intent** — e.g., *"Build a Python utility that finds duplicate files in a directory by content hash."* Watch the SDD agent generate a totally different spec + tasks + code.
2. **Tighten the verifier** — instruct the verifier to **execute** the code (write a `tests` field with pytest), not just read it. Closer to true production SDD.
3. **Add an interactive clarification phase** — before phase 1, have the agent ask the user 3-5 clarifying questions. Demonstrates the HITL approval gate.
4. **Replan if verification fails** — if `overall_passed = False`, loop back to phase 3 with the failed criteria as feedback. Add a max-iteration limit.
5. **Compare to vibe coding** (lesson 16 coming) — run the same intent through both; compare quality, inference time, and outcome.

---

## Mental model in one line

> **SDD turns "build this for me" into a *deterministic, auditable, multi-step workflow*. Every phase emits a typed artifact. Phase gates enforce ordering. The verifier checks every acceptance criterion against actual code. Slower to start, dramatically better outcomes for non-trivial work.**

---

## FAQ

**Q: Why use `with_structured_output` for every phase?**

A: To make artifacts machine-readable. Spec must produce a typed `Spec`; you can't have phase 2 consume free-form text from phase 1 reliably. Pydantic validation also catches malformed outputs (e.g., a spec missing required fields) at the boundary instead of letting them propagate.

**Q: Can I skip phase 4 (verify)?**

A: For trivial work, yes. For anything that ships, no — verification is what gives you confidence the implementation matches the spec. Without it, you have a hopeful generation, not a verified artifact.

**Q: How does this differ from Plan-and-Execute (Session 2)?**

A: PE is a single-task pattern — given a task, decompose and execute. SDD is a workflow pattern — given a vague *intent*, produce a spec FIRST. PE skips the spec; SDD's whole point is the spec. Phases 2-3 of SDD look like PE; phase 1 (spec) and phase 4 (verify against spec) are what SDD adds.

**Q: Does the agent execute the generated code during phase 4?**

A: Not in this implementation — phase 4 just reads the code and checks acceptance criteria via reasoning. **Production SDD adds an "execute" sub-phase**: run the code in a sandbox, capture output, compare to expected. That's a hybrid SDD + Vibe-style execution loop. Worth a follow-up implementation.

**Q: What if the spec is wrong?**

A: Two patterns:
- **HITL gate** — pause after phase 1 and ask the user "approve this spec? Y/n". Production SDD always does this.
- **Reflection on the spec** — wrap phase 1 with a reflection loop (Session 2): critic checks the spec, writer refines, until both agree.

**Q: Can I use different local models per phase?**

A: Yes. Use `ChatOllama(model="llama3.2:3b")` for clarify + decompose (faster, cheaper inference), and `ChatOllama(model="llama3.2")` for implement and verify (better quality for complex tasks). That mix-of-models pattern cuts latency ~50% with minimal quality drop.

**Q: Cost-wise, is SDD always more expensive than vibe coding?**

A: Yes in inference time — 4 phases vs. ~1 phase. Roughly 5-10× the inference cost for the same intent. But with Ollama there is no API cost, only local GPU time. The trade-off is wall-clock time vs. code quality. The total time-to-shipped-correct-code is usually lower for SDD on non-trivial work.

---

## Related

- **Previous:** [14 — Multi-agent + LTM](14-multi-agent-ltm.md)
- **Next:** Session 5 — Vibe Coding (the improvisational opposite)
- **Builds on:** [05 — Structured output](05-structured-output.md), [02 — LCEL](02-lcel-composition.md)
- **Pattern reference:** [reference-agentic-patterns](../reference-agentic-patterns.md)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 4 of 32
