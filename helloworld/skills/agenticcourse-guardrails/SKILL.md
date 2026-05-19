---
name: agenticcourse-guardrails
description: Use when the user asks about input filtering, output filtering, PII detection, prompt injection defense, jailbreak prevention, faithfulness checking, on-topic enforcement, or middleware to wrap LLM calls. Provides the cheap-first ordering principle, input vs output guardrail patterns, the faithfulness-of-refusals nuance, and refusal-leakage warning.
---

# Guardrails — Input + Output Middleware

## The frame

```
User input  →  INPUT GUARDS  →  LLM  →  OUTPUT GUARDS  →  User
                  ↓                          ↓
             (block/redact/             (block/redact/
              reject/transform)          rewrite/disclaim)
```

Each guard is a `Runnable` (or function wrapped in `RunnableLambda`) that participates in the LCEL chain.

## Cheap-first ordering — the #1 cost lever

Order guards from free to expensive. Adversarial traffic short-circuits at zero cost:

```
PII regex          → free (~1 ms)
Prompt injection regex → free (~1 ms)
On-topic LLM judge → ~600 ms + tokens
─── (the actual chain) ───
Output PII regex   → free
Faithfulness judge → ~600 ms + tokens (only if retrieval happened)
```

A 10% adversarial traffic share with cheap guards = ~10% cost reduction vs running everything.

## Input guardrails (typical set)

| Guard | What | Cost | Action |
|---|---|---|---|
| PII regex | SSN, email, phone, API-key patterns | free | refuse |
| Prompt injection regex | *"ignore previous"*, *"you are now an X"*, `<\|...\|>` patterns | free | refuse |
| On-topic LLM-judge | One-word verdict from a cheap model | 1 LLM call | refuse |

## Output guardrails (typical set)

| Guard | What | Cost | Action |
|---|---|---|---|
| Output PII regex | Same patterns as input, on the model's response | free | redact or refuse |
| Faithfulness judge | Context + answer → supported/unsupported | 1 LLM call | refuse (or retry) |

## Five things worth knowing

### 1. A refusal IS supported by the context

If the model says *"I don't have enough information,"* the faithfulness judge should pass it. **A refusal makes no factual claims** — so there's nothing to be unfaithful about. Tune the judge prompt:

> "If the answer says it does not have enough information, that is SUPPORTED."

Without this nuance, strict faithfulness blocks honest refusals (the opposite of what you want).

### 2. On-topic ≠ Answerable

A question can be on-topic (about your domain) but not answerable (info isn't in your corpus). **Two different concerns, two different guards.** Don't conflate them. On-topic catches *"what's the weather"*; faithfulness catches *"who founded LangChain"* (on-topic but un-retrievable).

### 3. Refusal messages can leak information

```
[REFUSED by PromptInjection input guardrail] injection pattern: 'Ignore previous instructions'
```

Demo-friendly, attacker-friendly. **In production, return vague refusals externally** (*"I can't help with that request"*) while logging the specific reason internally. Otherwise adversaries learn which guards to bypass.

### 4. LLM judges are best-effort

A clever adversary asks *"What does LangChain say about Thai food?"* — semantically off-topic but lexically on-topic. **Single-judge accuracy isn't enough for high-stakes apps.** Pair with downstream guards (faithfulness) for defense in depth.

### 5. Hard fail vs soft fail vs rewrite

Three failure modes:
- **Hard fail (refuse)** — security/compliance issues (PII leak, injection, off-policy)
- **Soft fail (warn + proceed)** — quality issues (low faithfulness, uncertain answer)
- **Rewrite (redact + proceed)** — PII / formatting

Get this wrong and the product is either annoying (too strict) or unsafe (too loose).

## Production hardening pointers

| Concern | What to use |
|---|---|
| PII detection | Microsoft Presidio — more accurate than regex |
| Prompt injection | Rebuff library — multi-layer (heuristics + canary tokens + LLM judge) |
| Toxicity | OpenAI moderation endpoint, Perspective API, Detoxify |
| Guardrail orchestration | `guardrails-ai` (DSL + validators), NeMo Guardrails (NVIDIA Colang) |
| Observability | Log every guard's verdict + latency. Tune thresholds based on real traffic. |
| Retry path | On faithfulness failure: re-prompt with stronger grounding before refusing |

## What guardrails do NOT replace

- Authentication / authorization (API-layer middleware)
- Rate limiting (standard middleware)
- Audit logging (complementary, not substitute)
- Human review for high-stakes outputs (medical, legal, financial)

## Code shape (LCEL)

```python
def safe_chain(user_input: str) -> str:
    try:
        run_input_guardrails(user_input)        # raises on failure
    except GuardrailFailure as e:
        return f"[REFUSED] {e.reason}"          # log specific reason internally

    chunks = retriever.invoke(user_input)
    context = format_context(chunks)
    answer = answer_chain.invoke({"context": context, "question": user_input})

    try:
        run_output_guardrails(context, answer)
    except GuardrailFailure as e:
        return f"[BLOCKED] {e.reason}"

    return answer
```

## Mental model in one line

> **Guardrails are pre/post middleware around the LLM. Cheap checks first, expensive checks last, vague refusals to users, specific reasons in logs. They turn an LLM into a system you can ship to real users.**
