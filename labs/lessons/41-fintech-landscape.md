# 41 — FinTech AI Landscape & Regulation (Session 28)

> **Finance is the most regulated, most explainability-demanding, most adversarially-targeted AI vertical.** A wrong output doesn't just lose money — it violates securities law, triggers regulatory action, or enables fraud. This session maps the regulatory landscape and technical constraints for AI in financial services.

---

## Roadmap — where this lesson sits

```
═══════ TRACK J: FINANCE ═══════

  ▶ Session 28: FINTECH AI LANDSCAPE  ◄ HERE
    Session 29: Reference Arch — Fraud + Customer Support
    Session 30: Case Study — Investment Research Assistant

  Prerequisites: Sessions 18–21
```

---

## Files involved

| File | Role |
|---|---|
| `fintech/landscape.md` | Sub-vertical taxonomy + use case map |
| `fintech/regulatory_map.md` | Regulation → technical requirement mapping |

---

## Sub-vertical taxonomy

| Sub-vertical | Examples | Primary AI use cases |
|---|---|---|
| **Retail banking** | Checking accounts, mortgages | Customer support, fraud detection, document AI |
| **Wealth management** | Investment advice, portfolio management | Research, recommendations, compliance |
| **Insurance** | Underwriting, claims | Risk scoring, claims processing, fraud |
| **Payments** | Card networks, UPI, wallets | Fraud detection, dispute resolution |
| **Lending** | Credit scoring, loan origination | Underwriting, collections |
| **Capital markets** | Trading, research, settlement | Sentiment analysis, regulatory filing AI |
| **RegTech** | AML, KYC, compliance monitoring | Document extraction, transaction monitoring |

Pick one sub-vertical and go deep — the regulatory and technical constraints differ significantly.

---

## Regulatory landscape

### US Regulations

| Regulation | Scope | Key AI constraint |
|---|---|---|
| **SEC Regulation Best Interest** | Investment advice | AI recommendations must serve client's best interest; no undisclosed conflicts |
| **FINRA rules** | Broker-dealers | All communications (including AI outputs) are subject to supervision and archiving |
| **SOX (Sarbanes-Oxley)** | Public companies | Financial reporting AI must have auditability and internal controls |
| **FCRA** | Credit reporting | AI credit decisions must be explainable; adverse action notices required |
| **BSA/AML** | All financial institutions | AI transaction monitoring must produce SAR (Suspicious Activity Reports) |
| **PCI DSS** | Card data | Payment card data cannot be sent to third-party LLMs unencrypted |

### India Regulations

| Regulation | Scope | Key AI constraint |
|---|---|---|
| **RBI Guidelines on Digital Lending** | NBFCs, fintechs | Credit algorithm must be explainable; no prohibited data sources |
| **SEBI SCORES** | Investment advisors | AI advice must be registered; no unregistered investment advice |
| **IRDAI** | Insurance | AI underwriting models must be approved; bias testing required |
| **DPDP Act 2023** | All | Financial data is sensitive; explicit consent for AI processing |

### EU Regulations

| Regulation | AI implication |
|---|---|
| **MiFID II** | Investment research AI must be disclosed as AI-generated |
| **EU AI Act** | Credit scoring = high-risk AI system (mandatory conformity assessment) |
| **GDPR** | Right not to be subject to automated credit decisions |
| **PSD2** | Open banking APIs must be available; AI can build on them |

---

## The explainability constraint

Unlike healthcare (where "consult a clinician" is acceptable), finance has a legal right-to-explanation for automated decisions:

**FCRA (US):** If an AI denies credit, the applicant must receive a specific, human-readable explanation of the principal reasons — "the model said no" is not compliant.

**EU AI Act (high-risk AI):** Credit scoring AI must provide meaningful information about the logic involved in automated decisions.

**RBI Digital Lending (India):** The credit algorithm must be explainable to regulators; black-box models require additional justification.

Technical implication: any model used for credit, insurance, or investment decisions must produce **local explanations** (per-decision, not just global feature importance).

```python
from pydantic import BaseModel

class CreditDecision(BaseModel):
    approved: bool
    credit_limit: int | None
    interest_rate: float | None
    # Adverse action reasons (FCRA required)
    adverse_action_reasons: list[str] | None  # ["High debt-to-income ratio", "Short credit history"]
    # Model explanation
    top_positive_factors: list[tuple[str, float]]  # [("On-time payments", 0.35), ...]
    top_negative_factors: list[tuple[str, float]]
    model_version: str
    decision_timestamp: str
```

---

## AI advice liability

Financial advice given by AI sits in a regulatory grey zone:

```
Not regulated as investment advice:
  • "Here is historical performance data for HDFC Bank"
  • "Here are three ETFs that track the Nifty 50"
  • "Dollar-cost averaging is a common investment strategy"

Potentially regulated as investment advice:
  • "You should buy HDFC Bank stock"
  • "Based on your risk profile, I recommend this portfolio"
  • "This is a good time to invest in real estate"

Clearly regulated:
  • Discretionary portfolio management
  • Personalised securities recommendations
  • Managed accounts
```

**Safe harbour design:** Frame AI outputs as information and education, not recommendations. Add disclaimers. Ensure the human advisor (not the AI) makes the final recommendation to the client.

---

## PCI DSS: no card data to LLMs

Payment card data (PAN, CVV, expiry) must never be sent to a third-party LLM via API:

```python
import re

# PAN pattern (Luhn-valid 13-19 digit numbers)
PAN_PATTERN = re.compile(r'\b(?:\d[ -]?){13,19}\b')
CVV_PATTERN = re.compile(r'\b\d{3,4}\b')

def sanitise_payment_data(text: str) -> str:
    text = PAN_PATTERN.sub("[CARD_NUMBER_REDACTED]", text)
    return text

# Always sanitise before any LLM call in payment contexts
def safe_llm_call(prompt: str) -> str:
    clean_prompt = sanitise_payment_data(prompt)
    return llm.invoke(clean_prompt)
```

---

## AML / transaction monitoring

Anti-money laundering is a major AI use case in finance — and a major compliance risk if the AI misses suspicious transactions:

```python
class SuspiciousActivityReport(BaseModel):
    transaction_id: str
    suspicion_type: str          # "structuring" | "layering" | "smurfing" | ...
    risk_score: float            # 0.0–1.0
    pattern_detected: str        # human-readable description
    supporting_transactions: list[str]
    analyst_review_required: bool = True   # always true for SARs
    auto_file_to_fincen: bool = False      # only after human review
```

AML AI must have a human in the loop before filing a SAR. The AI flags; the human decides. This is both regulatory and ethical — false positives harm legitimate customers.

---

## Try this

1. **Regulatory mapping** — pick one sub-vertical (e.g., lending). List every regulation that applies in your target market (US, India, or EU). For each, identify the specific AI constraint it creates.

2. **Explainability prototype** — build a simple credit scoring model (even a logistic regression on synthetic data). Implement SHAP values. Generate an adverse action notice from the SHAP output. Is it human-readable?

3. **PII/PCI audit** — take 20 sample customer service queries from a banking scenario. Run them through Presidio + the PAN sanitiser. Measure what percentage contained sensitive data that would have reached the LLM unprotected.

4. **Advice vs. information** — take 10 AI outputs from a financial chatbot. Classify each as "information" or "investment advice" under SEC Regulation Best Interest. Would any require a registered investment advisor?

5. **AML pattern design** — design a transaction monitoring system that flags "structuring" (breaking large transactions into smaller ones to avoid reporting thresholds). What patterns does the AI need to detect? What's the false positive rate you'd accept?

---

## Mental model in one line

> **FinTech AI is constrained by explainability (credit decisions must give reasons), advice liability (AI cannot give personalised investment advice without registration), PCI DSS (no card data to LLMs), and AML (human in the loop before any regulatory filing) — pick your sub-vertical first, then map its specific regulatory stack.**

---

## Related

- **Next:** [Session 29 — Reference Arch: Fraud + Customer Support](42-fraud-support.md)
- **Governance + audit:** [Session 20 — AI Governance & Audit](32-governance.md)
- **Red-teaming for finance:** [Session 19 — Red-teaming & Compliance](31-red-teaming.md)
- **Document AI for financial documents:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Curriculum tracker:** Session 28 of 46 — Track J
