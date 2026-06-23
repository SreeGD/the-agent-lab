# 42 — Reference Arch: Fraud Detection + Customer Support (Session 29)

> **The hybrid architecture that financial AI actually uses in production: deterministic rules for known fraud patterns, LLM for nuanced judgment, with hard guardrails and tool-call gating between every layer.** No LLM-only fraud system has shipped at scale. The hybrid is why.

---

## Roadmap — where this lesson sits

```
═══════ TRACK J: FINANCE ═══════

  ✓ Session 28: FinTech AI Landscape & Regulation
  ▶ Session 29: REFERENCE ARCH — FRAUD + SUPPORT  ◄ HERE
    Session 30: Case Study — Investment Research Assistant
```

---

## Files involved

| File | Role |
|---|---|
| `fintech/fraud_support_architecture.md` | Architecture document + design decisions |

---

## Why hybrid: deterministic + LLM

Pure rule systems:
- **Fast** (microsecond latency for card fraud)
- **Explainable** (rule X fired because condition Y)
- **Brittle** (novel fraud patterns bypass rules)

Pure LLM systems:
- **Flexible** (handles novel patterns, nuanced language)
- **Slow** (1-3 seconds; too slow for card authorisation)
- **Opaque** (hard to explain to regulators)

The hybrid uses each where it belongs:

```
  Transaction arrives
         │
  ┌──────▼───────────────────────┐
  │  LAYER 1: Velocity rules     │  ← Microseconds; always on
  │  (>3 cards same merchant,    │    Deterministic; explainable
  │   transaction in new country │    Kills 80% of fraud
  │   within 1h, etc.)           │
  └──────┬───────────────────────┘
         │ Passes rules
  ┌──────▼───────────────────────┐
  │  LAYER 2: ML risk score      │  ← Milliseconds
  │  (gradient boosted tree;     │    Structured feature vector
  │   not an LLM)                │    Score: 0.0–1.0
  └──────┬───────────────────────┘
         │ Score 0.3–0.7 (grey zone)
  ┌──────▼───────────────────────┐
  │  LAYER 3: LLM review         │  ← Seconds; async
  │  (explain the pattern,       │    For edge cases and disputes
  │   check against known        │    Not on the critical auth path
  │   fraud narratives)          │
  └──────┬───────────────────────┘
         │
  ┌──────▼───────────────────────┐
  │  LAYER 4: Human review       │  ← Minutes to hours
  │  (analyst reviews LLM        │    For high-value disputes
  │   recommendation)            │    Mandatory for SAR filing
  └──────────────────────────────┘
```

**Key constraint:** The LLM is NEVER on the card authorisation critical path. Card auth must complete in < 100ms. LLMs add seconds. LLM review is always async.

---

## Fraud detection: structured feature pipeline

```python
from pydantic import BaseModel
from datetime import datetime

class TransactionFeatures(BaseModel):
    # Transaction
    amount: float
    merchant_category_code: str
    merchant_country: str
    is_card_present: bool
    channel: str              # "web" | "mobile" | "atm" | "pos"

    # Velocity (computed from history)
    txn_count_1h: int
    txn_count_24h: int
    unique_merchants_24h: int
    amount_24h: float

    # Behavioural
    is_new_merchant: bool
    distance_from_last_txn_km: float | None
    time_since_last_txn_minutes: float | None
    is_new_country: bool

    # Device / network
    device_fingerprint_match: bool
    ip_country_matches_card_country: bool

class FraudScore(BaseModel):
    transaction_id: str
    risk_score: float         # 0.0–1.0
    risk_tier: str            # "low" | "medium" | "high" | "block"
    triggered_rules: list[str]
    model_version: str
    latency_ms: int
```

---

## LLM for dispute resolution (async)

When a customer disputes a transaction, the LLM helps the analyst:

```python
DISPUTE_ANALYSIS_PROMPT = """You are a fraud analyst assistant.

Analyse this disputed transaction and provide:
1. A plain-language explanation of why it was flagged
2. The 3 most likely explanations (fraud vs. legitimate)
3. What additional information would resolve the uncertainty
4. Your recommendation: investigate further / close as fraud / close as legitimate

Transaction data:
{transaction_json}

Customer's dispute statement:
{customer_statement}

Recent transaction history (last 30 days):
{transaction_history}

Return structured analysis only. Do not make a final fraud determination —
that requires a human analyst.
"""

class DisputeAnalysis(BaseModel):
    flag_explanation: str
    possible_explanations: list[str]    # ranked by likelihood
    additional_info_needed: list[str]
    analyst_recommendation: str         # "investigate" | "close_fraud" | "close_legitimate"
    confidence: float
    requires_human_review: bool = True  # always true
```

---

## Customer support: tool-call gating

AI customer support in banking is dangerous without strict tool-call gating. Every action that changes account state must be behind an authorisation check:

```python
SAFE_TOOLS = [
    "get_account_balance",
    "get_transaction_history",
    "get_branch_locations",
    "explain_product_features",
]

GATED_TOOLS = [
    "initiate_transfer",         # requires 2FA verification first
    "update_contact_details",    # requires identity verification
    "block_card",                # requires customer confirmation
    "dispute_transaction",       # requires case creation
]

def get_tools_for_session(auth_level: str) -> list[str]:
    if auth_level == "verified":
        return SAFE_TOOLS + GATED_TOOLS
    return SAFE_TOOLS  # unauthenticated: read-only only

# Middleware: intercept tool calls and verify auth before execution
async def gated_tool_call(tool_name: str, args: dict, session: CustomerSession) -> dict:
    if tool_name in GATED_TOOLS:
        if not session.is_2fa_verified:
            return {"error": "This action requires additional verification. "
                             "Please complete OTP verification first."}
        # Log every gated action for compliance
        audit_log.append({
            "tool": tool_name,
            "customer_id": session.customer_pseudonym,
            "timestamp": utcnow(),
            "args_hash": hash_args(args),
        })
    return await execute_tool(tool_name, args)
```

---

## Real-time guardrails

Financial customer support AI must never:
- Give investment advice without disclaimers
- Promise outcomes ("your loan will be approved")
- Reveal another customer's information
- Bypass authentication for account changes

```python
FINANCIAL_GUARDRAILS = [
    {
        "pattern": r"(will be approved|guaranteed|definitely|certain to)",
        "response": "I can't guarantee specific outcomes. A specialist "
                    "can review your application and give you accurate information.",
    },
    {
        "pattern": r"(should i invest|buy.*stock|sell.*shares|portfolio recommendation)",
        "response": "For personalised investment advice, please speak with one "
                    "of our registered financial advisors. I can share general "
                    "information about our investment products.",
    },
]

def apply_guardrails(response: str) -> str:
    for guardrail in FINANCIAL_GUARDRAILS:
        if re.search(guardrail["pattern"], response, re.I):
            return guardrail["response"]
    return response
```

---

## Try this

1. **Velocity rule engine** — implement 5 velocity rules (transaction count in 1h, new country, amount spike, etc.). Run them against a synthetic transaction log. Measure false positive rate (legitimate transactions blocked) vs. fraud catch rate.

2. **LLM dispute analysis** — generate 5 synthetic dispute scenarios (some fraudulent, some legitimate). Run the dispute analysis prompt. Evaluate: does the LLM's recommendation match the ground truth? Does it correctly say "requires human review"?

3. **Tool-call gating simulation** — build the gated tool framework. Simulate a conversation where a user tries to initiate a transfer without 2FA. Verify the gate blocks the call. Then complete 2FA and verify the call proceeds.

4. **Guardrail coverage** — take 20 sample customer queries that could elicit problematic responses (investment advice, outcome guarantees, etc.). Run the guardrail checker. What percentage does it catch? What does it miss?

5. **Hybrid latency profile** — measure the latency of each layer: rule engine (microseconds), ML score (milliseconds), LLM review (seconds). Build a decision matrix: at what ML score do you invoke the LLM? Justify the threshold.

---

## Mental model in one line

> **Financial AI fraud + support is a four-layer hybrid: deterministic velocity rules (always on, microseconds) → ML risk score (milliseconds) → LLM async review (seconds, never on auth path) → human analyst (minutes, mandatory for regulatory actions) — with tool-call gating and output guardrails at every layer.**

---

## Related

- **Previous:** [Session 28 — FinTech AI Landscape](41-fintech-landscape.md)
- **Next:** [Session 30 — Case Study: Investment Research Assistant](43-investment-research.md)
- **Guardrails foundation:** [Session 10 — Guardrails](10-guardrails.md)
- **HITL patterns:** [Session 10 — Custom LangGraph + HITL](21-custom-langgraph.md)
- **Governance + audit:** [Session 20 — AI Governance & Audit](32-governance.md)
- **Curriculum tracker:** Session 29 of 46 — Track J
