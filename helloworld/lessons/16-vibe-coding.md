# 16 — Vibe Coding (Session 5)

> **Loose intent → generate code → run it → on error, feed the error back → repeat.** No spec, no tasks, no formal verification — just generate-and-try. The improvisational opposite of Spec-Driven Development (Session 4).

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: Agentic Patterns
                                                             ✓ S1: MCP, ✓ S2: Refl+PE, ✓ S3: MA+LTM
                                                           Track B: Workflow & Skill
                                                             ✓ Session 4: SDD (lesson 15)
                                                             ▶ Session 5: VIBE CODING  ◄ HERE
                                                             ○ Session 6: Claude Skills
                                                           Track C-F + Phase 3 verticals
                                                           Track M: Claude Code Mastery (optional)
```

**Why this lesson now:** you just built the rigorous version (SDD). Now build its opposite. After this, the **vibe ↔ spec spectrum** becomes a real lever you can pick from — slow + rigorous for production, fast + improvisational for prototypes.

---

## Files involved

| File | Role |
|---|---|
| [`vibe_coding.py`](../vibe_coding.py) | The loop: generate → sandbox → retry on error. Two demo intents. |
| [`generated_vibe_1.py`](../generated_vibe_1.py) | Output of Intent 1 (SHA-256 hasher) |
| [`generated_vibe_2.py`](../generated_vibe_2.py) | Output of Intent 2 (top-5 largest files) |

---

## What problem it solves

You have a one-line intent. You want code. You don't want to write a spec, decompose into tasks, generate the code, then verify it. You just want **the code, now**.

For prototypes, throwaway scripts, exploration, and "let me see if this is even possible" work, **SDD is overkill**. The whole spec-tasks-verification ceremony is friction you don't need.

Vibe coding strips all of that away: ask, get code, run it, ship it (or iterate).

The risk: nothing's checked. If the code runs but does the wrong thing, vibe coding has no way to know. The "verifier" is *"did it crash?"* — that's it.

For prototypes, that's enough. For production, that's a liability.

---

## The analogy

**Jamming on a riff vs. composing a symphony.**

SDD is the symphony: score (spec), parts (tasks), rehearsals (implementation), conductor's review (verification). Slow to start, but everyone knows what they're playing.

Vibe coding is the jam session: someone picks a key, you start playing, you respond to what others play. If a note clashes, you adjust. No score, no rehearsal — just *vibes*.

For getting a song out tonight, the jam wins. For releasing a recorded album, the symphony wins. **Same instrument, different process for different goals.**

---

## Visual

```
                  intent (1 line)
                        │
                        ▼
                ┌───────────────┐
                │  generate     │ ◄─────────┐
                │  code (LLM)   │           │
                └───────┬───────┘           │
                        ▼                   │ feed stderr
                ┌───────────────┐           │ back as
                │ run in        │           │ context
                │ sandbox       │           │
                │ (subprocess +  │           │
                │  timeout)     │           │
                └───────┬───────┘           │
                        ▼                   │
                    success?                │
                      │                     │
                      ├── no ─► error ──────┘
                      │
                      yes
                      ▼
              done — save final code

  Loop budget: hard cap (5 iterations default). Without it,
  a stubborn intent + a flailing model = bills you can't explain.
```

---

## The concept

```python
def vibe_code(intent: str, max_iterations: int = 5) -> VibeRun:
    code, error = "", ""
    for i in range(1, max_iterations + 1):
        # GENERATE — prior code + error give the model context to fix what broke
        ai_msg = generator_pipe.invoke({
            "intent": intent, "prior_code": code, "error": error
        })
        code = strip_code_fences(ai_msg.content)

        # EXECUTE — subprocess with timeout
        result = execute_in_sandbox(code)
        if result.success:
            return VibeRun(success=True, iterations=i, code=code, ...)

        error = result.stderr   # feeds next iteration's context

    return VibeRun(success=False, iterations=max_iterations, ...)
```

**Three exits:** success, budget exhausted, or `subprocess` timeout (infinite loop in generated code).

---

## Run it

```bash
python vibe_coding.py
```

The file runs **two demo intents** back-to-back:

1. *"Print the SHA-256 hash of the string 'hello world'."*
2. *"Build a Python script that lists the top 5 largest files in the current directory (recursive), skipping hidden files."*

Each prints per-iteration trace + final result.

---

## Real numbers from a clean run

```
intent   result      iter     in   out    time       cost
─────────────────────────────────────────────────────────
1        ✅ pass         1    163    45    2.4s    $0.001
2        ✅ pass         1    203   228    3.6s    $0.004
─────────────────────────────────────────────────────────
TOTAL                   2    366   273    6.0s    $0.005
```

**Both intents nailed on iteration 1.** Total $0.005 / 6 seconds for two working programs.

**Compare to Session 4 (SDD):** ~$0.11 / 90 seconds for one program. **Vibe is ~20× cheaper and ~15× faster** *when the model gets it right first try* — which is most of the time for clean, well-scoped intents on a strong model like Sonnet 4.6.

---

## Walk-through

### Why didn't either intent iterate?

You might expect to see the loop kick in — the model errors, sees stderr, retries. **That's the safety net, not the common path.** With a strong model + clean intents, first-try success is the rule.

The iteration loop matters when:
- The intent is genuinely ambiguous (model picks the wrong interpretation)
- The model uses a wrong API (`requests.get` vs `urllib.request.urlopen`, etc.)
- Edge cases trip the first attempt (permission errors, encoding, paths)
- The sandbox environment differs from the model's training assumptions (Python version, available libraries)

When *any* of those happen, the loop saves you. When none happen, the loop never fires — and you pay $0.001 for working code.

### What the model saw on each iteration

```
SYSTEM: "You are a senior Python engineer..."
HUMAN:  "Intent: <the intent>
         Prior attempt (empty on first try): <prior code or "">
         Error from prior attempt (empty on first try): <prior stderr or "">
         Generate the (corrected) Python script now."
```

On iteration 1, prior_code and error are empty — the model writes from scratch. On iteration 2+, the model sees its prior attempt AND the error — that's the "reflection" signal that drives revision.

### The output

`generated_vibe_1.py`:
```python
import hashlib
text = 'hello world'
hash_value = hashlib.sha256(text.encode()).hexdigest()
print(hash_value)
```

Output: `b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9`

`generated_vibe_2.py`: a `os.walk` + `os.path.getsize` script that skips hidden files, sorts by size descending, prints the top 5. Ran in a real directory; produced sensible results (LEARNINGS.md, lesson 14, production_chatbot.py — the actual largest files).

**Both worked. No human edits. No spec. No tasks. No verification.**

---

## The contrast with SDD — same task spectrum, opposite philosophies

| | Vibe Coding | SDD |
|---|---|---|
| Starting input | Vague intent (1-2 sentences) | Vague intent (1-2 sentences) |
| First action | Generate code | Generate a spec |
| Intermediate artifacts | Just final code | Spec, Tasks, Code, Report |
| Phase gates | None | Yes |
| Verification | "Did it run without erroring?" | "Does it satisfy every acceptance criterion?" |
| Auditability | Low | High |
| Cost | $0.001-0.01 per intent | ~$0.10 per intent |
| Speed | Seconds | ~90s |
| Best for | Prototypes, exploration, throwaway scripts | Production code, non-trivial systems |
| Worst for | Anything where "subtle bug" matters | Trivial one-shots |
| Failure mode | Runs but does the wrong thing (silent) | Spec doesn't match user intent (loud) |
| Required prompt engineering | Minimal | Substantial (one prompt per phase) |
| Required tool support | Sandboxed code execution | Typed output, planner, verifier |

---

## When to pick which

```
"Is the cost of a subtle bug high?"
                │
        ┌───────┴───────┐
        yes              no
        │                 │
        ▼                 ▼
       SDD             "Is the task multi-step?"
                              │
                       ┌──────┴──────┐
                       yes            no
                       │              │
                       ▼              ▼
                      SDD            Vibe
                  (might also
                   use a multi-
                   agent or PE
                   pattern)
```

If you can write the code yourself in 5 minutes, vibe is overkill — just write it.
If you can write the code in an hour, vibe usually wins.
If you can write the code in a week, SDD wins (or at least, *some* spec-up-front pattern).

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| One-shot scripts | "Convert this CSV to JSON" — vibe is perfect |
| Exploration | "Show me a quick proof-of-concept" — vibe is perfect |
| Prototype validation | Before SDD, do a vibe pass to see if the problem is even tractable |
| Test data generation | "Generate 50 plausible-looking customer records" — vibe |
| Internal tools (low stakes) | "Build me a quick log analyzer" — vibe |
| Bug repros | "Write me a 10-line repro of this issue" — vibe |
| Code golf / playful experiments | Pure vibe territory |

---

## Sandbox safety — what this is and isn't

**What this IS:**
- Subprocess isolation from your main Python process (separate memory, separate interpreter state)
- Hard timeout (kills infinite loops)
- Captured stdout/stderr (no contamination of your terminal)
- Clean temp-file lifecycle (script gets deleted after execution)

**What this is NOT:**
- A security sandbox. The generated code can:
  - Read any file your user account can read
  - Write/delete files
  - Make network requests
  - Spawn other processes
  - Consume resources (CPU, memory) up to the timeout

For a real security boundary (untrusted code execution at scale), wrap in **Docker**, **gVisor**, **Firecracker**, or **nsjail** (Linux). Anthropic also provides Code Execution Tool for hosted sandboxed execution.

---

## Try this

1. **Pick a "tricky" intent that exercises the loop** — e.g., *"Use the requests library to fetch the GitHub API for python/cpython repo info and print the top 5 contributors."* (No requests installed → ModuleNotFoundError on iter 1 → model recovers with urllib on iter 2.)
2. **Tighten max_iterations** to 2 — see what happens when the budget is tight.
3. **Use a weaker model** (Haiku) and rerun — likely needs more iterations; demonstrates the model-quality vs iteration-count trade-off.
4. **Combine Vibe + SDD** — run Vibe to get a working prototype, then run SDD against the prototype's behavior as the spec. Vibe explores; SDD productionizes.
5. **Run with a clearly bad intent** — e.g., *"Build a perpetual-motion machine in Python."* Watch the loop produce successively more apologetic but never-correct code; budget exhausted; failure handled gracefully.

---

## Mental model in one line

> **Vibe coding is generate-execute-reflect-retry without any of the structured artifacts of SDD. It's fast and cheap when the model nails it first try, and the iteration loop is the safety net for when it doesn't. The 'verifier' is "did the subprocess return 0" — nothing more. Use for prototypes; use SDD for production.**

---

## FAQ

**Q: Why doesn't the lesson show the loop actually iterating?**

A: Honest answer: both demo intents were clean enough that Sonnet 4.6 nailed them first try. **That's the realistic finding.** With a strong model + reasonable intents, first-try success is the rule, iteration is the safety net. To force iteration: use a weaker model, tighten the intent's edge cases, or pick an intent that requires a non-standard library.

**Q: Is the sandbox safe enough for production?**

A: For trusted code (you wrote the intent yourself, no adversarial input), yes — subprocess + timeout is fine. For *untrusted* code (e.g., users submit intents), no — wrap in Docker / Firecracker / gVisor. The sandbox in this lesson protects against infinite loops, not against malicious code.

**Q: How is this different from "agent.py" with a code-execution tool?**

A: Almost identical in spirit. Vibe coding hardcodes the loop in Python; an agent with a `run_code` tool lets the LLM decide when to run. The agent version is more flexible (the LLM can run multiple snippets, look at outputs, decide next step); vibe is simpler (one-shot generation, run, retry on fail). Pick whichever fits.

**Q: What if the generated code calls `input()` and hangs waiting for stdin?**

A: It'll hit the timeout (15s default) and the sandbox will kill it. The error returned is `"EXECUTION TIMED OUT"` — the model sees that and revises (usually by removing the `input()` call or providing default values).

**Q: What if the generated code modifies my filesystem?**

A: It can. This is one of the real risks of vibe coding. Mitigations:
- Run in a containerized sandbox
- Use a separate user account with limited permissions
- Run in a temp directory and rmrf it after
- Static-analyze the code before executing (look for `os.remove`, `shutil.rmtree`, etc.)
For this lesson's demos, the intents don't touch the filesystem destructively, so we accept the risk.

**Q: Can I parallelize vibe coding (run multiple intents at once)?**

A: Yes — wrap `vibe_code()` in `asyncio` or `concurrent.futures` and run N intents in parallel. Each sandbox is its own subprocess; they don't share state.

**Q: How does vibe compare to "let me just write it myself"?**

A: For tasks you'd take 5 minutes to write: just write it. For tasks you'd take 1 hour: vibe usually wins on time (you supervise + iterate while the LLM types). For tasks you'd take a day+: vibe still works for the rough draft; switch to SDD for production polish.

**Q: Does vibe coding handle creative coding (graphics, games)?**

A: Yes, but the sandbox capture is text-only. For matplotlib plots, the script can save to a file (PNG) and you inspect it. For graphics that need a GUI, the sandbox doesn't display them — you'd point the LLM to save output to a file.

**Q: Can I use vibe to refactor existing code?**

A: Yes — pass the existing code as the intent. *"Refactor this code to use dataclasses: <paste>."* Vibe will generate refactored code; sandbox runs your tests; if tests pass, success. **For real refactors with test suites, this is a powerful pattern.**

**Q: When does vibe coding actively hurt me?**

A: When you accept the output without reading it. Vibe's failure mode is **silent wrongness** — the code runs, returns exit 0, but does the wrong thing (off-by-one, wrong column, wrong API call). The "did it run" check is necessary but not sufficient. **Always read the code on important tasks**, or pair Vibe with a test suite or with SDD's verification step.

---

## Related

- **Previous:** [15 — Spec-Driven Development](15-spec-driven-development.md) (the rigorous opposite)
- **Next:** Session 6 — Claude Skills (Track B 3/3)
- **Builds on:** [03 — Agent tool loop](03-agent-tool-loop.md)
- **Pattern reference:** [reference-agentic-patterns](reference-agentic-patterns.md) (Reflection / iterative refinement entries)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 5 of 40
