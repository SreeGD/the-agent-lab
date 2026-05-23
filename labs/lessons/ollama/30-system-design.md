# 30 — System Design Interview Prep (Session 18)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/30_system_design_helper_ollama.py`.

> **The interview signal isn't "do you know LangChain" — it's whether you can hold the architecture, the math, and the trade-offs in your head while an interviewer pokes holes in real time.** This session gives you a runnable interview-prep tool, the 8-question framework, a reference architecture that fits 80% of LLM systems, and a 5-point self-evaluation rubric.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-17 (foundation + RAG + production + memory)         Track G: ARCHITECT SKILLS
                                                             ▶ Session 18: SYSTEM DESIGN INTERVIEW  ◄ HERE
                                                             ○ Session 19: Red-teaming
                                                             ○ Session 20: Governance & Audit
                                                             ○ Session 21: UX patterns
                                                           Track H: ○ Verticals
                                                           Track M: ○ Claude Code Mastery
```

**Why this lesson now:** Track F (production) covered the *what* — eval, cost, streaming, deploy, observability. Track G (architect skills) covers the *who-explains-it* — interview prep, red-teaming, governance, UX. Senior+ AI roles in 2026 hire on system-design fluency more than on framework knowledge; this is the first session aimed at that signal directly.

---

## File involved

| File | Role |
|---|---|
| [`30_system_design_helper_ollama.py`](../ollama/30_system_design_helper_ollama.py) | A real, runnable interview-prep tool. Pass a problem statement; the model returns a structured `SystemDesign` (Pydantic) with requirements clarifications, ASCII architecture diagram, components, data flow, trade-offs (named decisions with options + recommendation + reasoning), capacity estimates (with assumptions), risk register, likely interviewer follow-ups. The demo runs three classic scenarios end-to-end. |

---

## What problem it solves

You can build agent systems. You can RAG. You can deploy. But put you in a 45-minute system design interview and you'd:
- Skip the requirement-clarifying questions (50% of your interview score, gone)
- Draw a vague block diagram with no numbers attached
- Recommend the same model for everything because a smaller model didn't come to mind
- Fold under "but what if we have 10× the traffic" because you didn't size anything
- Run out of time before getting to the trade-offs (where most of the senior-IC signal lives)

This session is the *practice* layer. The framework + the helper tool turn open-ended "design X" prompts into structured outputs you can review, internalize, and replicate under interview conditions.

---

## The analogy

**Chess opening prep.**

Grandmasters don't compute the first 15 moves at the board — they recognize patterns and play the responses they've drilled. Interview-grade system design is the same: the strong candidates have a **template** they snap any problem into (gateway → router → retrieval → LLM → guardrails → eval), and they spend their interview minutes on the *substantive* parts (capacity math, the one weird constraint, the trade-off the interviewer wanted to hear).

This lesson gives you the opening book. The 8 questions are your first 5 moves. The reference architecture is your middlegame. The follow-up Qs are your endgame.

---

## Visual — the reference architecture (fits 80% of LLM systems)

```
                            ┌─────────────────────┐
   USER ─────────────────►  │   API gateway       │ ◄── auth, rate limit, TLS
                            │   + auth            │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │ Session manager     │ ◄── Redis (conv history)
                            │ + request ID        │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │ Orchestrator        │ ◄── intent classifier (small model)
                            │ (decides path)      │      routes to RAG / tool / direct
                            └─┬────────┬────────┬─┘
                              │        │        │
              ┌───────────────┘        │        └───────────────┐
              ▼                        ▼                        ▼
   ┌─────────────────┐        ┌─────────────────┐      ┌─────────────────┐
   │ RAG pipeline    │        │ Tool router     │      │ Escalation      │
   │ (hybrid/CRAG)   │        │ (function calls)│      │ (to human)      │
   └────────┬────────┘        └────────┬────────┘      └─────────────────┘
            │                          │
            └──────────┬───────────────┘
                       ▼
            ┌──────────────────────┐
            │  LLM Gateway         │ ◄── model routing (small/full),
            │  (caching, retry)    │      per-role model selection
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ Response validator   │ ◄── guardrails, PII scrub, policy gates
            │ + PII scrubber       │
            └──────────┬───────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   ┌──────────┐               ┌──────────────┐
   │ User     │               │ Audit logger │ ◄── structured logs + traces
   │ (stream) │               │ + metrics    │      Prometheus + S3
   └──────────┘               └──────────────┘
```

You'll redraw a version of this for every interview. The boxes you add or remove are *signal*: a fraud-detection scenario adds a real-time risk model; a code-review bot adds a Git API integration; a multi-tenant RAG adds a tenant isolation layer between gateway and orchestrator.

---

## Concept walk-through

### The 8 questions — ask these in the first 5 minutes

Memorize these. They're how you reveal you're senior in the first 60 seconds:

1. **Scale** — QPS, MAU, tokens/day, peak vs steady?
2. **Latency target** — TTFT, p95 end-to-end? Sync or streaming UX?
3. **Quality bar** — acceptable error rate, hallucination tolerance, eval framework?
4. **Cost ceiling** — monthly budget? Per-call target?
5. **Multi-tenancy** — single vs multi-tenant? Isolation requirements?
6. **Safety + compliance** — PII, HIPAA, SOC2, regulated-industry constraints?
7. **Existing infrastructure** — what must I reuse (auth, DB, deploy platform)?
8. **Build vs buy** — which capabilities are differentiating vs commodity?

Don't actually ask all 8 verbatim — ask the 3 that matter most for the scenario, **state your assumptions for the rest aloud** ("I'll assume single-tenant for v1 unless you tell me otherwise"), and let the interviewer correct you. That's the pattern.

### The 6 architectural decisions you'll make in every interview

These come up every time. Have a default + a fallback ready:

| Decision | Common answers | Default for 80% case |
|---|---|---|
| **Retrieval substrate** | dense / sparse / hybrid / graph / CRAG | **Hybrid (BM25 + dense + RRF)** — Session 11 |
| **Model strategy** | one model / per-role (small triage, full final) / fine-tune | **Per-role with small model for cheap, full for hard** — Session 15 |
| **Memory shape** | working / + semantic / + episodic / + hierarchical | **Working + semantic + episodic** — Session 17.5 |
| **Streaming** | none / SSE / WebSocket | **SSE for chat UIs** — Session 16 |
| **Eval** | none / golden + LLM-as-judge / Ragas + LangSmith | **Golden + LLM-judge in CI** — Session 14 |
| **Deploy target** | bare metal / k8s / serverless / Fly.io / Cloud Run | **Container + scale-to-zero PaaS** — Session 17 |

Knowing these defaults means you can answer "what would you reach for first" in 3 seconds, then spend the remaining time on the *exceptions* — the one place where the default is wrong for the scenario.

### Back-of-envelope math you must do in your head

Every senior interview has at least one capacity question. The formulas:

**Monthly LLM cost estimate:**
```
turns/month = MAU × sessions/MAU/month × messages/session
tokens/month = turns × avg_input_tokens × avg_output_tokens
inference_time/month = tokens_in × time_per_token_in + tokens_out × time_per_token_out
```

**Example: fintech chatbot, 10M MAU**
```
10M MAU × 2 sessions/month × 5 turns/session = 100M turns/month
With per-role routing: 70% small model (fast triage), 30% full model (complex)
Small model turns:  70M × (500 input + 200 output) = 49B tokens → fast inference
Full model turns:   30M × (800 input + 400 output) = 36B tokens → slower inference
Total: 85B tokens/month — latency and throughput depend on hardware
```

For cloud providers, substitute per-token pricing (Sonnet: $3/$15 per million input/output). For Ollama/local inference, substitute time-per-token estimates for your hardware. The *shape* of the calculation is identical — you're sizing tokens, then translating to cost or time.

**p95 latency budget:**
```
target: 3s p95
- gateway + auth:        100ms
- session fetch (Redis): 5ms
- intent classify (small model, streamed): 400ms TTFT
- retrieval (vector + BM25): 200ms
- LLM (full model, streamed): 800ms TTFT, 1500ms total for ~300 output tokens
- validator + PII scrub:  50ms
- audit log + response:   100ms
Total: ~1955ms first byte, ~2655ms total response.
Headroom: ~345ms for cold starts, retry, network jitter.
```

If the interviewer says "p95 must be 1 second" — that math doesn't fit. You either drop the full model (use small model for everything), drop retrieval, or move to a faster region. Knowing the budget line-by-line is what lets you negotiate.

### Trade-offs — the senior signal

The 3-5 trade-offs you discuss are where the interviewer decides your seniority. Each trade-off should have:

- **Name**: "Retrieval strategy for the knowledge base"
- **Options**: 2-3 named approaches
- **Recommendation**: pick ONE
- **Reasoning**: the constraint that drives the pick

The helper tool's output for the fintech scenario nailed this format:
```
▸ LLM model selection strategy
    options: Single full model | Two-tier small+full | Fine-tuned smaller
    RECOMMEND: Two-tier small for triage, full for drafting
    because: At 100M turns/month, single full model is expensive;
             two-tier cuts cost significantly by routing 70% of turns to the small model.
             Fine-tuning rejected because policy docs change weekly.
```

**The pattern: option_set → recommendation → constraint-driven reasoning.** Without the constraint, the reasoning is just opinion. With it, the interviewer can challenge the constraint instead of your reasoning — much easier to defend.

### Risk register — the production-experience signal

Risk register format:
| Risk | Likelihood (L/M/H) | Impact (L/M/H) | Mitigation |
|---|---|---|---|
| LLM hallucinates account balance | M | H | Response validator cross-checks numeric values against tool-returned facts |
| LLM provider API outage | L | H | Circuit-breaker, fallback to "we're experiencing issues, escalating to agent" |
| Prompt injection via user input | M | H | User input sandboxed, never concatenated into system prompt |

Three things a candidate without production experience misses:
1. **Likelihood × Impact** — not all risks are equal. Cheap mitigations for low-impact risks waste time.
2. **Concrete mitigation** — "we'll handle this somehow" gets you no points. "Circuit-breaker with 10s timeout fallback to a static message" is the answer.
3. **Risks you can't eliminate** — admit that. "Hallucination can never be 0; we minimize via grounding + validation + escalation triggers."

### The 5 follow-up questions you'll always get

Senior interviewers always probe in these directions. Pre-arm yourself with answers:

1. **"What if we had 10× the traffic?"** — answer with what scales linearly (stateless services), what doesn't (vector store, Redis), and the architectural change required.
2. **"How would you cut cost by 50%?"** — the levers from Session 15: model selection, prompt compression, parallelism. Quantify each.
3. **"How do you know the system is healthy?"** — answer in observability terms: structured logs, request IDs, p95 latency histograms, error rate alerts. Session 17.
4. **"What's the most likely thing to break in production?"** — name a real failure mode (API 5xx, retrieval miss, prompt injection) and describe the detection + response.
5. **"How would you evaluate this system's quality at scale?"** — Session 14: golden dataset, LLM-as-judge metrics in CI, regression gates.

If you can answer all 5 in 30 seconds each, you have a senior signal regardless of company.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/30_system_design_helper_ollama.py
```

Takes ~30-60 seconds (three full design generations). No API cost — Ollama runs locally.

**Three modes of use:**

1. **Self-test mode** — pick a problem, try to produce YOUR own design first (in a notebook, in 25 min). Then run the tool. Diff where the tool went further. That's your study list.

2. **Calibration mode** — pick a system you actually built at work. Compare the tool's design to what you shipped. Where the tool diverged = either a missed alternative (study it) or a context-specific reason it wouldn't work in your env (be able to articulate the reason).

3. **Pressure mode** — read each `likely_followup` aloud, answer in 30 seconds. Anything you fumble = drill it. Real interviews ARE that fast.

---

## Real output highlights

Running on **"Customer-support chatbot for fintech, 10M MAU"** produced:

**One-line summary:**
> A production-grade, RAG-powered customer support chatbot for a 10M-MAU fintech that resolves account/transaction/fraud queries autonomously and escalates unresolvable cases to live agents with full context handoff.

**Requirements clarifications (8 questions answered):**
- Scope: Tier-1 only (balance, transactions, card lock); Tier-2+ escalates
- Latency: p95 < 3s for bot turns; escalation handoff < 5s
- Availability: 99.95% uptime SLA
- Auth: existing OAuth2 JWT; bot enforces row-level access
- Channels: in-app chat (mobile + web) v1
- Escalation: hybrid — rules as hard gates, LLM confidence as soft gate
- Data freshness: live API for financial data; nightly re-index for KB
- Languages: English v1, i18n hooks built in

**Architecture (ASCII):** 16-component diagram showing API gateway → session manager → orchestrator → RAG + tool router + escalation → LLM gateway (small model triage + full model drafting) → validator → audit logger.

**Capacity (key numbers, with assumptions):**
- Peak QPS: **~580** (10M MAU × 2 sessions/mo × 5 turns × 15× burst)
- Monthly LLM inference: significant token volume — size based on hardware for local, budget for cloud
- Pinecone index size: **~2GB** (50K vectors, <10ms p95)
- Redis: **~12GB** (100K concurrent sessions × 20KB)
- Audit log: **~18TB/yr** (PCI-DSS 7-year retention on Glacier)

**Trade-offs (5 named decisions):**
1. LLM model selection → per-role (small model triage + full model drafting)
2. Retrieval → hybrid BM25 + dense + RRF
3. Financial data freshness → always live (no cache for $$)
4. Escalation triggers → hybrid rules + confidence
5. Conversation state → Redis with 30-min TTL

**Follow-up questions the tool pre-armed:**
- "How do you prevent destructive tool actions?"
- "Walk through fraud dispute end-to-end including Regulation E timelines"
- "How would you cut inference cost by 50% without degrading UX?"
- "Behavior during partial outage where Account API is down?"
- "How do you evaluate quality at scale and detect silent regressions?"
- "What happens when a user returns after 35 minutes mid-dispute?"
- "How would you extend to voice (IVR)?"

That's the depth a real interview goes to. The tool ran in ~15 seconds with Ollama locally.

---

## Self-evaluation rubric

Use this after every practice answer (yours OR the tool's). 5 points per section, 25 total.

| Section | 1 pt | 3 pts | 5 pts |
|---|---|---|---|
| **Requirements clarification** | Skipped or vague | Asked 3-5 questions | Asked all 8 + stated assumptions for unanswered |
| **Architecture diagram** | Boxes only | Boxes + arrows + labeled flows | Boxes + arrows + flows + responsibility per box |
| **Capacity math** | None | One number stated | 3+ numbers with assumptions shown |
| **Trade-offs** | None or 1 hand-waved | 2-3 named, no reasoning | 3-5 named with options + recommendation + constraint-driven reasoning |
| **Follow-up handling** | Stalled on one | Answered most in 60s | Answered all in 30s with crisp specificity |

**Scoring:**
- **22-25** — Strong hire signal at senior/staff. Ship the offer.
- **17-21** — Pass at senior. Some growth needed but reliable.
- **12-16** — Pass at IC2/IC3. Not ready for senior IC.
- **<12** — No-hire at the level interviewing for.

Score yourself harshly. The bar is high.

---

## Production patterns — beyond the interview

### When the reference architecture isn't enough

The 80% architecture above covers most LLM systems. The 20% that doesn't:

- **Real-time multi-modal** (voice agents) — adds streaming TTS / STT, lower latency budget, different state model
- **Long-running async tasks** (research assistants, deep-research bots) — adds task queues, partial-result streaming, > 5 minute LLM passes
- **Edge / on-device** (private LLMs) — different model selection entirely, no cloud API
- **Adversarial-input domains** (security, fraud, content mod) — adds explicit attacker model, defense-in-depth layers

Recognize these by *shape* of the problem statement. A voice agent has "phone" or "call" or "real-time" in it. A research bot has "deep" or "comprehensive" or "multi-step." Adversarial domains have "abuse" or "safety" or "attacker" in them. When you spot one, drop the default architecture and reach for the specialized pattern.

### Drawing diagrams under pressure

Whiteboard / virtual-whiteboard reality: you have 5-7 minutes for the diagram, not 30. Tips:

- Start with 5 boxes max in a line. Add detail by zooming in on one box.
- Always label arrows ("REST/JSON", "gRPC", "Kafka events"). Unlabeled arrows lose points.
- Show data direction with arrowheads. Bi-directional only when truly bi-directional (rare).
- Mark async paths with dashed lines. Audit logger, eval runner, etc.
- Put SLAs / latencies *on* the boxes (`<200ms`, `99.95%`). Shows you think about contracts.

The helper tool's diagrams are reference-quality (15+ boxes); your interview version should be ~6-8 boxes with the *interesting* detail emphasized.

### What to NOT cover

In a 45-minute interview, you can't go deep on everything. Senior candidates know what to skip:

- Don't deep-dive on tokenization / embedding model internals (unless asked)
- Don't reimplement Pinecone (use it as a labeled box; only explain its role)
- Don't redraw a Kubernetes diagram (assume the deploy story works)
- Don't argue authentication (assume JWT, mention OAuth2, move on)

The senior signal is *what you leave abstract on purpose* as much as *what you fill in*.

---

## Try this

1. **Generate 5 designs.** Run the helper against 5 different problem statements. Read each one critically — every trade-off, every capacity number. Ask: "if the interviewer pushed back on this, could I defend it?"

2. **Practice the 30-second answers.** For each scenario the tool generates, read out the `likely_followups` and force yourself to answer aloud in 30 seconds. Use a timer. Anything you fumble — that's tomorrow's study list.

3. **Diff against your real shipped system.** Pick something you've built. Have the tool design it from scratch. Diff. Where the tool diverged, write a 3-sentence justification for what you actually did.

4. **Time-boxed full mock.** Set a 45-minute timer. Pick a fresh problem. Cover paper, do your own design (no tool). At 45 min, stop. THEN run the tool. Diff. This is the most honest calibration you can do.

5. **Domain swap.** Rerun the helper on the same scenario but for a different domain — *"customer-support chatbot for HEALTHCARE with 10M users"*. Watch how the safety / compliance / data-freshness answers change. The skill is recognizing which boxes need rethinking when the constraint changes.

---

## Mental model

> **System design is constraint-driven architecture. The constraints — scale, latency, cost, safety, compliance, existing infra — determine the architecture. The architecture is the cheapest design that satisfies all the constraints.**

That's it. The framework + tool + rubric are scaffolding around that one idea.

When you can:
1. Elicit the constraints (the 8 questions)
2. Snap the constraints into a reference architecture (the 80% template)
3. Defend the trade-offs (with constraint-driven reasoning)
4. Quantify the math (capacity estimates with assumptions)
5. Anticipate the follow-ups (the 5 standard probes)

…you have the senior signal. The rest is practice volume.

---

## FAQ

**Q: Won't using an LLM helper to prep make me lazy in interviews?**
The opposite. Reading 20 LLM-generated designs builds *pattern recognition* faster than 20 self-attempts. The LLM does the boring repeated work; you internalize the structure. In the interview, you're alone — but your pattern library is much deeper.

**Q: How do I prep for a non-LLM system-design interview?**
The structure (clarify → architecture → trade-offs → capacity → risks → follow-ups) is the same. Swap the LLM-specific components for the appropriate ones (DB sharding, queue patterns, etc.). The framework is general; the *defaults* are LLM-specific in this lesson.

**Q: The helper's diagrams have 15+ boxes — interviewers say "keep it simple." How do I reconcile?**
Use the helper's diagram as the **full mental model**. On the whiteboard, draw 6-8 boxes that capture the *core flow*, and have the rest in your head ready to add when the interviewer says "tell me more about X". The helper builds your mental model; you draw a subset of it.

**Q: What about diagram tools — should I use a real one?**
For virtual interviews: Excalidraw / Miro / draw.io are fine if the company specifies. Plain text + markdown is also acceptable. Don't waste time perfecting visuals — the interviewer cares about the structure, not the aesthetics.

**Q: How many practice scenarios is enough?**
Reasonable: 20 different problem statements with full self-practice (no tool first), then tool diff. Strong: 50. Most candidates do 3-5 and call it done. The difference between a 17/25 and a 22/25 is volume.

**Q: What's the single thing that distinguishes a senior IC from a staff candidate?**
At staff level, you proactively flag the **ambiguity in the problem statement** and propose a resolution. "Is fraud detection in-scope? Because if yes, that's a real-time signal pipeline; if no, it's just a chatbot that calls an existing fraud API. These have very different architectures — let's confirm which." Senior ICs answer the question asked. Staff candidates redefine the question to one with a clearer answer.

**Q: How do I improve the trade-off section specifically?**
Read post-mortems of real systems. OpenAI / Notion / Linear / Vercel all publish engineering blogs that describe real trade-offs ("we chose X because Y, even though Z was tempting"). Internalize 10-15 of these and your trade-off sections will sound like someone with real production experience because they reflect the patterns of actual production decisions.

**Q: Will this lesson be enough to pass a staff-level AI interview?**
Necessary, not sufficient. You'll also need: ML fundamentals (transformer architecture, training/inference math), the relevant company's research papers, sample of their public stack decisions, and behavioral prep. This lesson covers the system-design *portion* well.

**Q: Should I share the helper's output verbatim in an interview?**
Absolutely not — that's cheating. The helper is a study tool, like a chess engine. Use it to learn patterns; deliver original work in the interview. Most senior interviews include a "tell me about a system you designed" portion where authentic experience matters.

**Q: What about the rubric — should I share it with my interviewer?**
No. The rubric is for self-calibration. The interviewer has their own. But knowing the rubric helps you recognize what they're scoring you on.

---

## Related

- **Previous:** [29 — Memory Architectures](29-memory-architectures.md)
- **Next:** Session 19 — Red-teaming (probing LLM systems for failure modes — Track G 2/4)
- **Builds on:** All prior production sessions — [14 — Evaluation](25-evaluation.md), [15 — Cost Optimization](26-cost-optimization.md), [16 — Streaming](27-streaming.md), [17 — Deploy + Observability](28-production-deploy.md), [17.5 — Memory Architectures](29-memory-architectures.md). The system-design framework is the *integration layer* over everything Track F + the memory survey taught you.
- **Track G status:** ▶ 1/4 complete. Architect Skills track is the "senior IC interview prep" subtrack — this session is the most directly interview-relevant; Sessions 19-21 cover red-teaming, governance, UX patterns.
