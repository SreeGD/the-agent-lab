# 32 — AI Governance & Audit (Session 20)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/32_governance_ollama.py`.

> **Per-system safeguards become org-wide rails.** Red-teaming (Session 19) hardens *one* system. Governance is the discipline that decides — uniformly across many systems — which AI requests are allowed, who decides, on what basis, with what audit trail. Without it, 50 AI features have 50 ad-hoc policies. With it, one policy engine + one audit schema applies everywhere, and audits become a SQL query instead of an engineer interview.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-19 (foundation + RAG + production + red-teaming)    Track G: ARCHITECT SKILLS
                                                              ✓ Session 18: System Design Interview
                                                              ✓ Session 19: Red-teaming
                                                              ▶ Session 20: GOVERNANCE  ◄ HERE
                                                              ○ Session 21: UX patterns
                                                            Track H: ○ Verticals
                                                            Track M: ○ Claude Code Mastery
```

**Why this lesson now:** Session 19 gave you the *per-system* harness — attacks, defenses, model card. Session 20 zooms out to the *org-wide* discipline: confidence scoring + policy gates + decision-reasoning audit logs + compliance framework mapping. One policy engine for many systems; one audit schema for many auditors.

---

## File involved

| File | Role |
|---|---|
| [`32_governance_ollama.py`](../ollama/32_governance_ollama.py) | The minimum-viable governance plane: self-reported + meta-judge confidence scoring, rules-as-code policy engine (5 rules, first-match-wins), structured `GovernanceAuditEntry` per request, 5 demo scenarios exercising each rule, compliance framework mapping table. |

---

## What problem it solves

A company with one chatbot makes ad-hoc safety calls — fine.

A company with 50 AI features cannot. Each team writes its own "should we allow this?" logic; each team logs differently; auditors get 50 different stories. The cost of an SOC 2 audit explodes because the auditor has to interview each team about how *their* system handles each control.

Governance solves this by:
1. **One policy engine** — rules-as-code, version-controlled, applied uniformly
2. **One confidence model** — every system reports self + meta confidence the same way
3. **One audit schema** — every system writes the same `GovernanceAuditEntry` to the same table
4. **One compliance mapping** — single document showing how audit fields satisfy each framework's requirements

Now an auditor's "show me how you handle X" becomes a SQL query against the audit table. Engineer time → near zero. Audit pass rate → near 100%.

---

## The analogy

**Linting and CI for AI risk.**

Before linters, every developer had their own style. Code review was personality-driven. Audits of "is this codebase consistent" required reading every file.

After linters + CI: rules are encoded once, enforced everywhere, violations are detected automatically, audits are a `lint --fail-on-violation` command.

Governance does the same thing for AI risk. The rules become code. The enforcement becomes automatic. The audit becomes a query.

---

## Visual

```
                          ┌───────────────────────┐
   USER REQUEST  ─────►   │  pre-flight (cheap)   │ ──── PII regex → if hit, DENY here
                          │   contains_pii()      │      (don't even call the LLM)
                          └───────────┬───────────┘
                                      │ clean
                                      ▼
                          ┌───────────────────────┐
                          │   ANSWER + self_conf  │ ──── llama3.2
                          │  (Pydantic structured │      with_structured_output(
                          │   output)             │       AnswerWithConfidence)
                          └───────────┬───────────┘
                                      │ {answer, self_conf, reason}
                                      ▼
                          ┌───────────────────────┐
                          │  META-JUDGE confidence│ ──── llama3.2
                          │  (calibration)        │      independent score
                          └───────────┬───────────┘
                                      │ {meta_conf, why}
                                      ▼
                          ┌───────────────────────┐
                          │   POLICY ENGINE       │  Priority-ordered rules:
                          │   (rules-as-code)     │    1. pii_in_input         → deny
                          │                       │    2. external_user_data   → deny
                          │                       │    3. destructive_action   → review
                          │                       │    4. high_stakes_low_conf → review
                          │                       │    5. default_allow        → allow
                          └───────────┬───────────┘
                                      │ {action, rule_fired, reasoning}
                                      ▼
                  ┌──────────────────────────────────────────┐
                  │   GovernanceAuditEntry → SQL / log sink  │
                  │   one row per request, structured JSON   │
                  └──────────────────┬───────────────────────┘
                                     │
                                     ▼
                              DELIVERED RESPONSE
                          (allow → real answer)
                          (deny  → vague refusal to user, specific reason in audit)
                          (review → "queued for human review", escalation path set)
```

---

## Concept walk-through

### 1. Confidence — two numbers, not one

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
answer_model = ChatOllama(model="llama3.2", temperature=0)
judge_model = ChatOllama(model="llama3.2", temperature=0)

class AnswerWithConfidence(BaseModel):
    answer: str
    confidence: float          # self-reported
    reasoning: str

class MetaConfidence(BaseModel):
    calibrated_confidence: float
    why: str
```

**Self-reported confidence** comes from the same model that produced the answer (via `with_structured_output`). Free, but susceptible to the model's bias — models tend to be over-confident on generation, occasionally under-confident on refusals.

**Meta-judge confidence** comes from a *different call* (using the same or different model) that reads the question + answer + self-confidence and scores them independently.

The **gap** (`self_conf − meta_conf`) is the diagnostic signal:
- Large positive gap = answerer over-confident, meta-judge calibrated downward
- Large negative gap = answerer was appropriately humble, meta-judge recognized the answer is fine
- Small gap (either direction) = both agree

You log all three (self, meta, gap) — *not* a single "fused" confidence. The downstream policy engine decides what threshold to apply on which signal.

**Ollama note:** for the judge call, you can use `llama3.2:3b` instead of `llama3.2` — the meta-confidence judgment is a calibration task that smaller models handle well, and the latency saving is significant when running all inference locally.

### 2. The rules-as-code policy engine

A `Rule` is pure Python:

```python
class Rule:
    name: str
    description: str
    applies_when: Callable[[Request, AnswerWithConfidence, MetaConfidence], bool]
    action: PolicyAction         # "allow" | "deny" | "review_required" | "sanitize"
    reasoning_template: str
```

The engine evaluates rules in priority order (the list order in the code), first match wins:

```python
RULES = [
    Rule("pii_in_input",
         applies_when=lambda req, ans, meta: contains_pii(req.query),
         action="deny",
         reasoning_template="..."),
    Rule("external_user_accessing_internal_data", ...),
    Rule("destructive_action_requires_human", ...),
    Rule("high_stakes_low_confidence", ...),
    Rule("default_allow", applies_when=lambda *_: True, action="allow", ...),
]
```

**Why first-match-wins:** simplest semantic. The team can reason about a rule by reading just the rules above it. Anything more elaborate (priority numbers, conflict resolution) is harder to debug under pressure.

**Why pure Python:** no DSL, no policy server, no YAML. Production swap-ins exist (Open Policy Agent + Rego, AWS Cedar) for cross-language reuse + admin UIs — but they have the *same shape*. Build the discipline first, swap to a real engine when you have ≥10 systems sharing the same policy.

### 3. The five rules in priority order

| # | Rule | Action | Why this priority |
|---|---|---|---|
| 1 | `pii_in_input` | **deny** | Cheapest to check (regex) + most dangerous to skip. Short-circuits the LLM call entirely — no PII enters the model's request logs. |
| 2 | `external_user_accessing_internal_data` | **deny** | RBAC enforcement. Cheap, deterministic. Must come before any confidence-based rule. |
| 3 | `destructive_action_requires_human` | **review** | Writes/deletes on non-public data require approval. Cheap check; cuts the risky path. |
| 4 | `high_stakes_low_confidence` | **review** | Medical/financial + meta_conf < 0.70 → human review. The confidence-dependent rule. |
| 5 | `default_allow` | **allow** | Fallback. Must always match (the `lambda *_: True`). |

**Priority insight:** cheap deterministic checks first, expensive LLM-dependent ones last. Same shape as Session 19's defense layers. Same shape as Session 10's guardrails. **Cheap-first ordering is universal.**

### 4. The pre-flight optimization

The PII-in-input rule has a special property — it can be checked *before* calling the LLM:

```python
def governed_pipeline(req):
    # Pre-flight — short-circuit if PII is in the input
    if contains_pii(req.query):
        # synthesize empty answer/confidence; jump straight to audit
        ...
        return audit, "[BLOCKED: PII detected]"

    # Otherwise run the full pipeline
    ans = answer_with_self_confidence(req)
    meta = meta_judge_confidence(req, ans)
    decision = evaluate_policy(req, ans, meta)
    ...
```

Saves the LLM call AND prevents the PII from being stored in the model provider's request logs. For Ollama this means saving a full inference pass — meaningful on slower hardware.

### 5. The audit entry schema

```python
class GovernanceAuditEntry(BaseModel):
    # identity / tracing
    timestamp, request_id, user_role, data_class, action_type
    # query
    query_hash, query_preview
    # models
    answer_model, judge_model
    # confidence
    self_confidence, meta_confidence, confidence_gap
    # policy
    policy_version, rule_fired, policy_action, policy_reasoning
    # outcome
    response_preview, escalation_path
```

Two design choices to note:
- **`query_hash` + `query_preview`** — not full query. The hash gives auditability without storing the full text indefinitely (GDPR data minimization). The preview is for debug-time human readability.
- **`policy_version`** — every rule change bumps the version. When a decision is questioned six months later, you can show exactly which rule set was in effect.

This is the artifact your SOC 2 / HIPAA / EU AI Act auditor will query. Design it for that audience first; for engineers second.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/32_governance_ollama.py
```

~30-45 seconds (5 scenarios × 2 LLM calls each ≈ 10 calls; scenario 2 short-circuits at pre-flight so only 8 LLM calls actually fire). No API cost — Ollama runs locally.

---

## Real output — the five scenarios

| # | Scenario | Self conf | Meta conf | Gap | Rule fired | Action |
|---|---|---|---|---|---|---|
| 1 | external/public — "What is LCEL?" | 0.92 | 0.88 | **+0.04** | default_allow | ALLOW |
| 2 | external/public — query contains SSN | 0.00 | 0.00 | 0.00 | pii_in_input (pre-flight) | **DENY** |
| 3 | external/financial — "Q3 revenue figures" | 0.10 | 0.92 | **−0.82** | external_user_accessing_internal_data | **DENY** |
| 4 | internal/medical — complex anticoagulation case | 0.82 | 0.78 | +0.04 | default_allow | ALLOW |
| 5 | internal/medical — "paracetamol = acetaminophen?" | 0.99 | 0.98 | +0.01 | default_allow | ALLOW |

**Summary:** 3 ALLOW, 2 DENY, 0 REVIEW. Average gap: −0.146 (skewed by scenario 3's −0.82).

### What scenario 3 teaches

Scenario 3 was the unexpectedly useful finding. The setup:
- External user asks for internal Q3 revenue figures
- The model **doesn't have** Q3 figures, so it correctly says "I don't have access to that data" — self-confidence: **0.10** (low, because the model is being honest about not knowing)
- The meta-judge reads the response and scores: **0.92** — because the *refusal* is correct and well-reasoned. There's nothing factually wrong with "I don't have access to that data."

That's a **−0.82 gap**. If we'd looked only at self-confidence (0.10) and triggered the `high_stakes_low_confidence` rule, we'd have escalated unnecessarily. The meta-judge correctly recognized this is an honest refusal, not a low-quality answer.

**The lesson:** "A refusal IS supported" applies here too. The faithfulness / confidence logic must understand that an honest "I don't have this data" is a high-quality response, not a low-confidence guess.

In this scenario the RBAC rule fired before the confidence rule even got a chance — but in a similar scenario without the RBAC trip, the confidence-based escalation would have been wrong.

### What scenario 4 teaches

Scenario 4 is the trickier teaching moment: a complex anticoagulation question (patient on warfarin, GI bleed history, new AF, eGFR 35) went through the policy and got **ALLOW** because both confidences cleared the 0.70 threshold.

Is that right? It depends on your risk posture:
- If 0.70 is your medical threshold, the policy is doing its job
- If you'd rather err on the side of human review for *any* complex medical question, set the medical threshold to 0.85 (or block all medical advice entirely)

**The rule is correct; the threshold is a policy decision.** This is where governance ties into product decisions — "what threshold for medical?" is a question for clinical leadership, not engineering. The rule-as-code makes the threshold visible and easy to change without a redeploy.

A more conservative policy would split `high_stakes_low_confidence` into per-data-class thresholds:

```python
THRESHOLDS = {"medical": 0.90, "financial": 0.80, "internal": 0.70}
Rule("high_stakes_low_confidence",
     applies_when=lambda req, ans, meta: (
         req.data_class in THRESHOLDS and
         meta.calibrated_confidence < THRESHOLDS[req.data_class]
     ),
     action="review_required", ...)
```

---

## Compliance mapping — how this satisfies the auditors

The harness prints a 10-row mapping table. Excerpt:

| Audit field(s) | Frameworks satisfied |
|---|---|
| `request_id, timestamp, query_hash` | SOC 2 CC7.2 (system monitoring), GDPR Art. 30 (records of processing) |
| `user_role` | SOC 2 CC6.1 (logical access), HIPAA §164.312(a)(1) (access control) |
| `data_class` | HIPAA §164.502 (uses + disclosures), GDPR Art. 9 (special categories) |
| `policy_version, rule_fired` | SOC 2 CC8.1 (change management), EU AI Act Art. 13 (transparency) |
| `policy_action, policy_reasoning` | EU AI Act Art. 14 (human oversight), NIST AI RMF GOVERN-1.1 |
| `self_confidence, meta_confidence` | EU AI Act Art. 15 (accuracy, robustness), NIST AI RMF MEASURE-2.x |
| `escalation_path` | HIPAA §164.530(c) (safeguards), SOC 2 CC9.x (risk mitigation) |
| `answer_model, judge_model` | EU AI Act Art. 11 (technical documentation), ISO 42001 §7 |
| `query_hash (not raw text)` | GDPR Art. 5 (data minimization), HIPAA §164.514 (de-identification) |
| `confidence_gap` | EU AI Act Art. 15 (accuracy monitoring), NIST AI RMF MEASURE-3.x |

When the auditor asks *"how do you ensure human oversight per EU AI Act Article 14?"*, you point at `policy_action` + `policy_reasoning` + `escalation_path` + the audit table query. Done.

The audit pass becomes mechanical because the *evidence* is structured.

---

## Production patterns

### When to swap to Open Policy Agent (OPA) / Cedar

Switch when:
- Multiple services share the policy (you don't want to copy-paste Python)
- Non-engineers (legal, compliance) need to edit rules
- You need an admin UI for policy CRUD
- Policies have hundreds of rules and a search UI helps
- Audit teams want a separate "review the policy" workflow

For ≤3 services and ≤20 rules, pure Python is fine. The shape (priority-ordered rules, first-match-wins, structured decision output) transfers directly.

### Per-data-class thresholds

The single 0.70 threshold for "high-stakes" data is a simplification. Production typically has:

```python
CONFIDENCE_THRESHOLDS = {
    "medical_advice":     0.90,    # very high bar
    "financial_advice":   0.85,
    "internal_data":      0.70,
    "summarization":      0.60,
    "public_qa":          0.50,
}
```

Each threshold reflects a *product* decision about acceptable risk × value trade-off. Engineering encodes; product / clinical / legal owns.

### Confidence drift monitoring

Per-day aggregates of `confidence_gap` per data-class are a key signal:
- If average gap grows over time → model becoming more over-confident → may need a model refresh or recalibrate
- If gap suddenly jumps → model changed (either model update or prompt drift)
- If gap goes negative → meta-judge becoming more lenient → check the meta-judge model

Alert when any aggregate moves > 2σ from the 30-day baseline.

### Human review queue ergonomics

When a rule fires `review_required`, the request goes to a queue. Queue management is its own product surface:

| Field | Purpose |
|---|---|
| `request_id` | Reviewer can pull the full audit entry |
| `data_class` | Routes to the right reviewer team |
| `confidence_gap` | High-gap items get priority (likely the most uncertain) |
| `escalation_path` | Which queue (`queue:medical_review`, etc.) |
| `query_preview` | Reviewer triage without loading full query |

A typical reviewer SLA: 15 minutes for medical, 4 hours for financial, 24 hours for non-urgent internal. Track p95 of `decision_time = response_time − queue_enter_time`.

### Privacy-preserving audit

`query_hash` is the privacy-respecting field. The full query is stored *separately* with shorter retention + PII scrubbing applied:

```
audit_log (long retention, structured, queryable)
    └── query_hash (sha256), query_preview (80 chars)

query_log (short retention, PII-scrubbed)
    └── raw text (90 days, then deleted per GDPR)
```

When a user issues a DSAR / right-to-erasure, you delete from `query_log` — the audit log entries (with hashes only) remain for compliance proof, but no PII survives.

### Versioning and policy evolution

```python
POLICY_VERSION = "policy-v1.0.0-2026-05-21"
```

Bump on every rule change. Audit entries are immutable; they reflect the policy that was in effect at request time. When a decision is questioned six months later, you can produce the exact rule set that applied.

For team workflows: policy changes are PR-reviewed like code. Compliance officer signs off. CI runs the demo scenarios against the new policy and fails the PR if expected behaviors regress (this is *eval for policy* — similar shape to Session 14).

---

## Try this

1. **Add a sixth rule for cross-tenant isolation.** New field on `Request`: `tenant_id`. New rule: "if response references any tenant ≠ request.tenant_id, deny." This is a real production rule for multi-tenant RAG.

2. **Build a per-data-class threshold map.** Replace the single 0.70 threshold with the dictionary from above. Re-run scenarios 4 + 5 — does scenario 4 (the complex anticoagulation question) now get sent to review at 0.78 < 0.90?

3. **Visualize the confidence calibration.** Run 20+ random requests. Plot self_confidence on x-axis, meta_confidence on y-axis. A well-calibrated pair sits on the diagonal. Where the points diverge tells you where one model is more reliable than the other.

4. **Wire up OPA.** Install `pip install opa-python-client`. Translate the 5 Python rules into Rego. Replace `evaluate_policy()` with a call to OPA's `data.governance.allow` query. Verify the same 5 scenarios produce the same decisions.

5. **Add a confidence drift alert.** Maintain a 7-day rolling average of `confidence_gap`. If today's average moves > 2σ from the rolling baseline, log a warning. Test by forcing one scenario's gap with a deliberately confusing question.

6. **Build an auditor query playbook.** Write SQL templates for each compliance framework's most common audit questions:
   - "Show me all denials for the last quarter" (SOC 2)
   - "Show me all decisions on medical_class data with escalation_path set" (HIPAA)
   - "Show me all requests where confidence_gap > 0.5" (EU AI Act robustness)

---

## Mental model

> **Confidence + policy + audit is the *minimum* contract that makes AI auditable.** Three coordinates. Each one cheap to add. Together they turn a stochastic LLM into a system a compliance officer can sign off on.

The key insight: **none of these layers prevent failures. They make failures *visible and accountable*.** Confidence flags low-quality outputs for review; policy gates make the trust boundary explicit; audit makes the decision trail recoverable. The combination is what an auditor — or a journalist, or a regulator — actually needs.

You can ship without governance. You cannot scale without it.

---

## FAQ

**Q: Why two confidence numbers? Isn't that twice the inference cost?**
With Ollama, two LLM calls means twice the local inference time. For cost-sensitive or latency-sensitive paths, use `llama3.2:3b` for the meta-judge call — it's faster and the confidence calibration task is well within a smaller model's capability. For production deployments with Ollama, sample (meta-judge 10% of requests, monitor drift) to reduce overhead at volume.

**Q: Won't the meta-judge have its own biases?**
Yes. Mitigations: (1) use a *different model* from the answerer when possible (e.g., `llama3.2` for generation, `llama3.2:3b` for judging), (2) periodically re-baseline the meta-judge against a human review panel, (3) for highest-stakes domains, use ensemble of 2-3 judges and vote.

**Q: Should the LLM be told its confidence is being scored?**
The self-confidence prompt explicitly says "Be honest." Whether saying that helps is a calibration question — measure it. Some teams report that prompting for confidence *plus* "what would lower your confidence" gives better-calibrated self-reports.

**Q: How do confidence scores interact with structured output?**
`with_structured_output(AnswerWithConfidence)` returns a Pydantic instance with `answer` + `confidence` + `reasoning` populated in one call. No extra LLM round-trip. Modern LangChain + Ollama make this clean.

**Q: What if my policy rules conflict?**
First-match-wins means you should order from *most restrictive* to *least restrictive*. Put `deny` rules first, `review_required` next, `allow` last. If two rules legitimately apply, the first one in the list wins. To make this clearer, name rules in priority order (`01_pii_in_input`, `02_rbac_external`, etc.) in production.

**Q: How do I unit-test policy rules?**
Each rule's `applies_when` is a pure function of `(req, ans, meta)`. Build a fixture matrix:

```python
def test_pii_in_input():
    req = Request(query="My SSN is 123-45-6789", ...)
    ans = ...; meta = ...
    decision = evaluate_policy(req, ans, meta)
    assert decision.rule_fired == "pii_in_input"
    assert decision.action == "deny"
```

Add one fixture per rule + an integration test that runs the demo scenarios and checks the expected outcomes. Run in CI on every PR that touches policy.

**Q: How is this different from Session 19's defense layers?**
Session 19's defenses are *per-request hardening* — block bad inputs, validate outputs, refuse dangerous responses. Session 20 is *governance over the whole interaction*: policy decision recording, confidence calibration, audit emission. They compose: Session 19's regex + LLM-validator happen inside Session 20's pipeline (as additional rules or as the `sanitize` action). Both at once for high-stakes systems.

**Q: How does this interact with eval (Session 14)?**
Eval measures quality on a fixed golden set. Governance measures every production request. The two should be coupled:
- Eval generates per-metric scores you can use as *priors* for confidence calibration
- Governance audit logs are the *source data* for the next eval refresh (find low-confidence requests, label them, add to golden set)

**Q: Who owns governance in an org?**
Typically a *trust & safety* or *AI governance* function reporting up to legal or risk. Engineering implements; the policy itself is owned by a cross-functional team (legal, security, product, clinical/financial domain experts). The *policy review cadence* (quarterly?) is owned by governance; the *technical implementation* by engineering.

**Q: How do I justify the cost to my team?**
Two numbers: (1) cost of an SOC 2 audit failure (six-figure consulting + delayed enterprise contracts), (2) cost of an AI-caused PR incident (varies, but recent precedents are seven figures + reputational damage). The governance plane costs near-zero at inference time with Ollama + a small engineering investment to set up. It pays for itself the first time it prevents one of those.

**Q: Is the rules-as-code approach AI-specific?**
No — it's a general access-control pattern. AI just adds the *confidence* signal as a new input dimension. The same engine pattern handles classical RBAC, feature flags, fraud rules. AI governance leverages the existing organizational discipline of rules-as-code, just with new inputs.

---

## Related

- **Previous:** [31 — Red-teaming & Compliance](31-red-teaming.md) — per-system harness
- **Next:** Session 21 — UX patterns (the user-facing half of trust: how the UI surfaces confidence, escalations, refusals — Track G finale)
- **Builds on:** [10 — Guardrails](10-guardrails.md) (input/output filtering, cheap-first ordering), [25 — Evaluation](25-evaluation.md) (LLM-as-judge pattern for confidence), [28 — Production Deploy + Observability](28-production-deploy.md) (audit log infrastructure), [31 — Red-teaming](31-red-teaming.md) (model card + attack catalog complement this policy plane)
- **Track G status:** ▶ 3/4 complete. Eval → Cost → Streaming → Deploy → Memory survey → Interview → Red-team → **Governance**. Next: UX (Session 21) closes Track G; then Track H (Verticals) or Track M (Claude Code Mastery).
