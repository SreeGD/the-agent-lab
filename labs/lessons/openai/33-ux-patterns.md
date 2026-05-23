# 33 — AI Product & UX Patterns (Session 21)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_openai.ChatOpenAI`, model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/33_ux_audit_helper_openai.py`.

> **The session that asks the question every other session assumed away — should this even be AI?** Then, given it should: which UX patterns calibrate user trust, which add friction, and what does the failure UX look like? This is the *product* half of senior AI work — and the closing artifact of Track G.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-20 (foundation + RAG + production + governance)     Track G: ARCHITECT SKILLS
                                                              ✓ Session 18: System Design Interview
                                                              ✓ Session 19: Red-teaming
                                                              ✓ Session 20: Governance & Audit
                                                              ▶ Session 21: UX PATTERNS  ◄ HERE  (Track G complete)
                                                            Track H: ○ Verticals
                                                            Track M: ○ Claude Code Mastery
```

**Why this lesson now:** Sessions 18-20 covered the *engineering* discipline (architecture, attacks, governance). Track G closes with the *product* discipline — the questions that determine whether the engineered system feels magical or haunted. Combined with the other three Track G tools, you now have a four-step pre-flight every AI feature should pass before it ships.

---

## File involved

| File | Role |
|---|---|
| [`openai/33_ux_audit_helper_openai.py`](../../openai/33_ux_audit_helper_openai.py) | The audit tool. Input: feature description. Output: structured `UXAudit{should_be_ai, ai_scope, required_ux_patterns, trust_calibration, failure_ux, risks, recommendations, rollout_guidance}` via `with_structured_output`. Four demo features hit different shapes of the design space. |

---

## What problem it solves

Most AI features ship with the wrong UX shape:

- **Deterministic problems forced into LLMs** — ticket categorization, autocomplete, format conversion. The team reaches for an LLM because *"we're an AI company now."* Rules would be 10× faster, 100× cheaper, fully auditable.
- **No confidence surfacing** — a high-stakes output (medical, financial, legal) renders identically to a low-stakes one. Users have no way to tell which to verify.
- **No edit path** — the AI produces a draft that the user must either accept whole or rewrite from scratch. The "draft" framing collapses to "another thing to fix."
- **No escalation** — when the AI fails, the user is stuck. No "talk to a human" button.
- **Vague failures** — `"Something went wrong"` instead of `"We couldn't read your bank statement — try again or upload manually."`

Each is fixable with one of 10 UX patterns. The audit tool surfaces *which* patterns this specific feature requires (not all 10), what failure modes need design treatment, and a rollout plan that catches problems before users do.

---

## The analogy

**Building codes for AI features.**

Building a house: you don't get to skip electrical, plumbing, or structural. Code inspectors check each in sequence; missing any one and the house doesn't get a certificate of occupancy.

Shipping an AI feature: you don't get to skip *should-this-be-AI*, *trust calibration*, *failure UX*, or *rollout*. The audit tool is the inspector — runs the four checks, produces a structured report, leaves the team with a punch list before launch.

Houses get built without inspectors; they often catch fire. AI features get built without audits; they often get pulled.

---

## Visual — the four-question audit

```
                FEATURE PROPOSAL
                ("AI suggests reply to support email")
                       │
                       ▼
   ┌─────────────────────────────────────────────────────┐
   │ Q1 — Should this be AI at all?                      │
   │                                                     │
   │   • Deterministic? rules                            │
   │   • Sub-100ms required? lookup / rules             │
   │   • Errors unrecoverable? AI-assisted at most      │
   │   • Personalization-trivial? rules                  │
   │   • All else → AI-fit; pick scope                   │
   └────────────────┬────────────────────────────────────┘
                    │ yes_assisted / human_in_loop / suggestion / no
                    ▼
   ┌─────────────────────────────────────────────────────┐
   │ Q2 — Which UX patterns are MANDATORY?               │
   │                                                     │
   │   From the 10-pattern catalog, pick the ones        │
   │   whose WHEN clause fits this feature.              │
   │   Typically 3-6 patterns per feature.               │
   └────────────────┬────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────┐
   │ Q3 — What is the failure UX per failure mode?       │
   │                                                     │
   │   confident_wrong, refuses_unnecessarily, slow,     │
   │   inconsistent, off_topic_drift, tool_failure,      │
   │   rate_limited                                      │
   │   → each gets a user-facing handling + app action.  │
   └────────────────┬────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────┐
   │ Q4 — How do you roll this out safely?               │
   │                                                     │
   │   shadow → 1% → 10% → full, with kill switch        │
   │   + concrete success metrics                        │
   └─────────────────────────────────────────────────────┘
```

---

## Concept walk-through

### Q1 — Should this be AI?

The audit tool picks one of five verdicts:

| Verdict | Meaning | Example |
|---|---|---|
| `yes_full_ai` | AI handles end-to-end autonomously | Generating marketing copy variants |
| `yes_assisted` | AI does most work, human reviews before commit | Draft customer support reply |
| `yes_with_human_approval` | AI proposes structured decisions; human approves each | Generate SQL → run button |
| `probably_rules` | Deterministic enough that rules / classical ML beat LLM | Closed-label classification with clear keywords |
| `no_not_ai` | Pure deterministic — don't reach for AI at all | Currency conversion, date formatting |

**The signal moves are `probably_rules` and `no_not_ai`.** A senior reviewer who says *"this should be rules"* saves the team months. The audit tool is willing to say this — note Feature 2 in the demo run below.

### Q2 — The 10 UX patterns

Each pattern has a **WHEN** clause. Using it outside the WHEN adds friction without trust gain:

| Pattern | When | NOT when |
|---|---|---|
| **CONFIDENCE_DISPLAY** | High-stakes outputs (medical, financial, irreversible) | Trivial tasks (autocomplete) |
| **CITATIONS_SOURCES** | Factual/knowledge retrieval (RAG) | Creative writing, code-from-scratch |
| **EDITABLE_OUTPUT** | The AI output IS the final artifact (email, code, doc) | Pure Q&A |
| **ALTERNATIVES_REGENERATE** | Multiple valid answers exist (titles, summaries) | Single-truth questions |
| **UNDO** | AI takes any state-changing action | Read-only outputs |
| **STREAMING_FEEDBACK** | Any LLM call > 1s | Sub-second responses, batch ops |
| **ESCALATION_TO_HUMAN** | High-stakes domains, user stuck | Low-stakes utility tools |
| **HONEST_REFUSAL** | Factual / safety-critical (always) | Creative tasks |
| **SUGGESTION_NOT_ACTION** | Non-trivial cost / irreversibility | Pure retrieval |
| **PROGRESSIVE_DISCLOSURE** | Complex outputs (long analyses) | Short outputs |

**The audit picks the 3-6 patterns whose WHEN actually fits the feature** — not all 10 by default. Pattern bloat is friction; pattern omission is risk; the audit calibrates between them.

### Q3 — The failure UX taxonomy

Most teams design the happy path and treat failures as "we'll figure it out." The audit forces a UI for each:

| Failure mode | User sees | App action |
|---|---|---|
| **confident_wrong** | High-confidence wrong answer (worst) | Log mismatch on user correction; trigger eval; alert if rate > 2%/hr |
| **refuses_unnecessarily** | "I can't help with that" on a legit request | Surface escalation; log false-refusal rate |
| **slow_response** | Spinner > 3s | Streaming feedback; soft timeout with "still working…"; hard timeout with retry |
| **inconsistent_outputs** | Same input → different outputs across runs | Nightly consistency audit; flag near-duplicate inputs with divergent outputs |
| **off_topic_drift** | AI ignores the question | Guardrail; transparent refusal to user |
| **tool_failure** | Underlying API down | Fail open or fail closed (chosen per feature); explicit "service unavailable" |
| **rate_limited** | 429 from provider | Backoff + retry; explicit "we're a bit busy" message |

**Confident_wrong is the most dangerous.** Users can self-correct slow or inconsistent outputs; they can't self-correct a confident wrong answer. Every audit must show how the UI helps the user *catch* this — confidence chip, citation badge, "verify before sending" disclaimer.

### Q4 — Rollout guidance

Same discipline as classical feature flags, applied to AI:

1. **Shadow mode** (weeks 1-2) — AI runs but never affects the user; compare to ground truth daily
2. **1% canary** (week 3) — small population sees the AI output; monitor everything
3. **10% rollout** (week 4) — broader sample; tune the threshold
4. **Full rollout** (week 5+) — assuming success metrics hold
5. **Kill switch always available** — any team lead can revert to manual in 60s without an engineering deploy

The audit tool includes a `rollout_guidance` paragraph in every result. Sample output (Feature 2 below) specifies *"Week 3: enable auto-routing for high-confidence ≥ 0.85 in billing and technical only. Keep account and abuse in human-review mode."* That's the level of specificity that makes a rollout plan executable.

---

## Run it

```
cd labs
./.venv/bin/python openai/33_ux_audit_helper_openai.py
```

~2-3 minutes (4 features × 1 structured LLM call each). Cost ~$0.10.

---

## Real output highlights

The most pedagogically valuable result was **Feature 2 — auto-categorize incoming support tickets**:

> **Verdict: PROBABLY_RULES**
>
> *"At only four fixed categories with well-defined keywords and patterns, a rules-based classifier (regex + keyword DSL, or a lightweight fine-tuned classifier) is faster, cheaper, fully auditable, and deterministic. Full LLM is overkill and introduces unnecessary latency, cost, and hallucination risk for a closed-label classification task. If accuracy on edge cases is genuinely poor with rules, a fine-tuned small model (BERT-class) is the right step up — not a generative LLM. Reserve AI for the ambiguous tail (~5-15% of tickets) via a hybrid: rules handle the confident cases, AI handles the rest with human-in-the-loop review."*

The auditor recommended a **DistilBERT fine-tune as the next step up** (10× cheaper, 5× faster, fully on-premise), and a **hard-coded abuse keyword bypass list** that overrides the model output — because abuse misclassification has legal liability and no model should be sole gatekeeper for safety-critical tickets.

That's the level of opinionated push-back a senior product reviewer gives. Engineering hears *"can we use AI?"* and says yes; a senior reviewer hears the same question and says *"only for the 15% tail; rules for the rest."*

**The other three verdicts:**

| Feature | Verdict | Key UX patterns |
|---|---|---|
| AI suggests reply to support emails | `yes_assisted` | EDITABLE_OUTPUT, ALTERNATIVES_REGENERATE, CONFIDENCE_DISPLAY, HONEST_REFUSAL |
| AI summarizes monthly bank statement | `yes_assisted` | CONFIDENCE_DISPLAY, CITATIONS_SOURCES (which transactions drove the summary), HONEST_REFUSAL, PROGRESSIVE_DISCLOSURE (3-sentence summary → click for detail) |
| AI generates SQL from natural language | `yes_with_human_approval` | SUGGESTION_NOT_ACTION (always — never auto-run), EDITABLE_OUTPUT (the query, before run), CONFIDENCE_DISPLAY, ALTERNATIVES_REGENERATE, UNDO |

Notice how the patterns differ per feature. The audit tool resists the temptation to recommend all 10 everywhere — that would be feature bloat. It picks the 3-6 that actually fit.

---

## Production patterns

### The four-tool Track G "AI feature kit"

```
Session 18  →  System design helper      (architecture + capacity math)
Session 19  →  Red-team harness          (attack catalog + defense layers)
Session 20  →  Governance auditor        (confidence + policy + audit)
Session 21  →  UX audit helper           (should-be-AI + UX + failure UX + rollout)
```

Run a feature proposal through all four before it ships. Combined output: architecture + capacity numbers + attack/defense map + policy + UX shape + rollout plan. Hand the bundle to engineering / security / legal / design / leadership and you have a pre-flight that costs ~$0.30 and 3 minutes — vs. months of meetings to surface the same questions.

The discipline these tools encode is the difference between a feature that ships smoothly and one that ships, breaks, gets pulled, then gets rebuilt the right way.

### When the audit's verdict is "no, don't use AI"

If `should_be_ai = no_not_ai` or `probably_rules`:

1. **Don't argue with the audit.** It's surfacing a constraint you might be motivated to ignore.
2. **Build the non-AI version first.** Get the baseline. Measure error rates.
3. **Only add AI for the residual.** The "ambiguous tail" pattern from Feature 2: rules handle 85%, AI handles the 15% with human-in-the-loop.
4. **Re-audit after the non-AI version ships.** Sometimes the data tells you AI IS warranted for cases you didn't predict.

### The "AI-generated, please verify" badge

Trust calibration's most common pattern. Every AI-produced output gets a visible label:

- **High-stakes** — `"AI-generated · 94% confident · Please review before sending"`
- **Medium-stakes** — `"AI-generated · You can edit"`
- **Low-stakes** — `"AI suggested"`

The label is also the **opt-out signal**: when users build trust, they stop reading it. When they don't trust the AI, the label gives them the override hook ("Replace with my own draft").

### Failure UX is where teams underinvest

The audit tool surfaces 3-5 failure modes for every feature. The most common gap is **confident_wrong** — teams assume the LLM will be honest about its uncertainty. It often isn't.

Three concrete defenses:

1. **Cross-check structured fields** — if the LLM says "your savings increased by $500," verify against the actual numbers before rendering.
2. **Surface conflicting signals** — if the LLM cites a source that doesn't support the claim, show *"Source [3] cited; verify"* not a confident statement.
3. **Calibrate based on data class** — financial summaries get a heavier "please verify" treatment than creative writing.

### Cross-platform UX

Many teams ship the same AI feature across mobile, web, CLI, and voice. The audit patterns translate but **the affordances differ**:

| Pattern | Mobile | Web | CLI | Voice |
|---|---|---|---|---|
| CONFIDENCE_DISPLAY | Badge chip | Inline confidence bar | Color suffix `[94%]` | Spoken hedge: *"I'm fairly sure but..."* |
| EDITABLE_OUTPUT | Sheet with edit field | In-place edit | Pipe-able output | Read-back + confirm |
| ESCALATION_TO_HUMAN | Persistent "Get help" link | Sidebar button | `--help-human` flag | "Connect me to an agent" |
| UNDO | Snackbar with action | Toast + button | `revert` command | "Undo that" |

The audit's recommendations should specify the right affordance per platform, not just "show confidence."

---

## Try this

1. **Run the audit on a feature you're shipping.** Print the result. Walk the team through it. Ask: which of the 3-5 recommendations are NOT in the design doc? Add them.

2. **Run it twice on the same feature with different framings.** *"AI suggests reply"* vs *"AI sends reply automatically"* — same underlying feature, but the verdict / patterns will differ. Calibrate which framing matches your team's actual intent.

3. **Test the "probably_rules" verdict deliberately.** Pass it a feature like *"AI calculates 15% tax on a purchase amount"*. Expect a sharp pushback. Use the response to talk your team out of AI-fitting deterministic problems.

4. **Add a 5th demo feature for your own domain.** Edit `DEMO_FEATURES` to include something specific (e.g., *"AI explains the patient's lab results to them in plain English"*). Run. Capture the audit. Use it in your next product review.

5. **Build the integrated kit.** Write a wrapper that takes a feature description and calls all four Track G tools sequentially: design helper → red-team → governance audit → UX audit. Save the combined output as a single PDF for the product review meeting.

6. **Quarterly re-audit existing features.** Pick a shipped AI feature, run the audit, look at the gap between what the audit recommends and what's actually built. The gap is your tech debt list — often shorter than expected.

---

## Mental model

> **The first question isn't "how do we build this with AI?" It's "should we build this with AI?" The second question isn't "what does the happy path look like?" It's "what does the user see when the AI fails?"**

Most teams skip both questions. The audit forces them.

Three slogans for closing Track G:

1. **"Engineering picks the architecture; product picks the trust contract."** Sessions 18-20 are engineering. Session 21 is product.
2. **"Failure UX is the half nobody designs."** Every audit ends here for a reason.
3. **"Pattern-without-when is friction; pattern-when-needed is trust."** Confidence chips everywhere = noise. Confidence chip when stakes are high = signal.

---

## FAQ

**Q: How is this different from the system-design helper (Session 18)?**

A: System design = boxes, capacity, trade-offs. UX audit = should-this-be-AI, patterns, failure UX, rollout. The system-design helper assumes you've decided AI; the UX audit interrogates that assumption. Both are necessary; running them in order (UX audit → system design) catches the "don't build this with AI" case before the architecture is wasted.

**Q: Why does the audit have only 10 UX patterns? Aren't there more?**

A: 10 is the minimum useful catalog. Patterns like *citation tooltips* or *response length toggles* are variants of the existing 10 (PROGRESSIVE_DISCLOSURE, CITATIONS_SOURCES). The catalog should be small enough that a reviewer can hold it in head and apply it under pressure. Add a pattern only when something fundamentally distinct emerges.

**Q: How do I disagree with the audit's verdict?**

A: The verdict is opinion, not law. Push back with a *constraint* — *"the audit says rules, but our domain has 200+ implicit categories and the keyword set drifts weekly; LLM is the only thing that handles that."* If you have the constraint, you have the override. If you don't have the constraint, the audit was right.

**Q: Should the audit pick only one verdict, or rank multiple?**

A: One. The whole point is to force an opinion. Ranked alternatives are a different artifact (research review). The audit is meant to read like a senior reviewer's note, not a TAC option matrix.

**Q: Are the trust-calibration messages going to make users distrust the feature?**

A: Honest disclosure builds *long-term* trust at the cost of short-term magic. Users who feel deceived by an over-confident system churn faster than users who see "AI-generated, please verify" upfront. Calibration is the trade-off where short-term flash loses to long-term retention.

**Q: How do I handle features where the user IS the AI evaluator (e.g., creative writing)?**

A: Different rules. The user wants alternatives, regenerate, edit — not confidence chips. The `yes_full_ai` scope often fits here. The audit should recommend ALTERNATIVES_REGENERATE and EDITABLE_OUTPUT heavily; skip CONFIDENCE_DISPLAY (no ground truth to be confident about).

**Q: How does this interact with the model card (Session 19) and policy engine (Session 20)?**

A: The model card is *external transparency* (what the system does + doesn't do, for compliance). The policy engine is *internal enforcement* (which requests are allowed). The UX audit is *user-facing trust* (what the user sees and trusts). All three exist; each addresses a different stakeholder (auditor, security team, user).

**Q: What if my team won't use the audit?**

A: Make the bar simple: any feature gated by a leadership review must come with the audit attached. Once the audit is required for sign-off, teams will run it. The barrier is usually social, not technical — the tool is `./.venv/bin/python openai/33_ux_audit_helper_openai.py` and a string.

**Q: Can I generate the audit in real time as the user describes the feature in a meeting?**

A: Yes — the tool runs in ~30s per feature. Some teams put it on a shared screen during product reviews. The shared output becomes the discussion artifact for the next 30 minutes. *"The audit says X — do we agree or do we have a constraint?"* is a much better meeting than *"what do you all think?"*

**Q: How does this map to AI/UX research literature?**

A: This synthesizes Microsoft's HAX (Human-AI eXperience) guidelines, Google PAIR (People + AI Research) patterns, Anthropic's published guidance on trust calibration, and field experience from production teams. The patterns aren't original; the *integration into a tool that produces a structured audit* is.

**Q: Does this lesson have a "what we WON'T do" list?**

A: Yes — explicitly no UI mockups, no broad-UX-principles coverage, no replay of Session 16's streaming material. The audit *recommends* UX patterns; the design team draws them. The audit *references* streaming; Session 16 covers it deeply.

**Q: Track G is done — what should I read for further depth?**

A: Three sources outside this curriculum:
- *Designing Machine Learning Systems* (Chip Huyen) — for the full systems lifecycle
- *Anthropic's Responsible Scaling Policy* — for the safety / governance perspective
- *Microsoft HAX Toolkit* — for the design / UX patterns at production depth

The four Track G tools in this course are an opinionated synthesis; those three sources are where to go deeper on each axis.

---

## Related

- **Previous:** [32 — AI Governance & Audit](32-governance.md)
- **Next:** Phase 3 — Verticals (Track H: Healthcare / Agriculture / Finance / Vidya Karana / Family AI) or Track M (Claude Code Mastery, optional)
- **Builds on:** [30 — System Design](30-system-design.md) (the architecture half), [31 — Red-teaming](31-red-teaming.md) (the attack/defense half), [32 — Governance](32-governance.md) (the policy half), [16 — Streaming](27-streaming.md) (the latency-UX half referenced in failure_ux), [14 — Multi-agent + LTM](14-multi-agent-ltm.md) (LTM is itself a UX choice — what to remember vs. forget)
- **Track G status:** ✓ **COMPLETE.** Architect Skills (Sessions 18-21) shipped: System Design → Red-teaming → Governance → UX. Combined with Track F (Production: Eval, Cost, Streaming, Deploy), you have the full senior-AI-IC pre-flight stack.
