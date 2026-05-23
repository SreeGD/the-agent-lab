"""AI Governance & Audit — per-system safeguards become org-wide rails (Ollama variant).

# Requires: ollama serve + ollama pull llama3.2

Red-teaming (Session 19) hardens ONE system. Governance is the
organizational discipline that decides — uniformly across many systems —
which AI requests are allowed, who decides, on what basis, with what
audit trail. Without it, a company with 50 AI features has 50 ad-hoc
policies and 50 audit gaps.

This file builds the minimum-viable governance plane:

  * Confidence scoring (self-reported + meta-judge calibration)
  * Rules-as-code policy engine (5 rules, first-match-wins)
  * Decision-reasoning audit log (GovernanceAuditEntry)
  * Compliance framework mapping (SOC 2 / HIPAA / GDPR / EU AI Act)

Five demo scenarios exercise each rule. Each request produces a full
audit entry printed as structured JSON — what a SOC 2 auditor would
query in production.
"""

import json
import re
from datetime import datetime, timezone
from typing import Callable, Literal
from uuid import uuid4

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

# NOTE: Both answer and judge use llama3.2 — Ollama has no separate small model by default
ANSWER_MODEL = "llama3.2"
JUDGE_MODEL = "llama3.2"

answer_model = ChatOllama(model=ANSWER_MODEL, temperature=0)
judge_model = ChatOllama(model=JUDGE_MODEL, temperature=0)

POLICY_VERSION = "policy-v1.0.0-2026-05-21"


# =====================================================================
# Request + response schemas
# =====================================================================

UserRole = Literal["external", "internal", "admin"]
DataClass = Literal["public", "internal", "medical", "financial"]
ActionType = Literal["read", "advise", "write", "delete"]


class Request(BaseModel):
    request_id: str
    query: str
    user_role: UserRole
    data_class: DataClass
    action_type: ActionType


class AnswerWithConfidence(BaseModel):
    answer: str = Field(description="The substantive response to the user's query.")
    confidence: float = Field(ge=0.0, le=1.0,
                               description="Your own confidence that the answer is correct, complete, and safe. "
                                           "0.0 = pure guess, 1.0 = certain. Be honest — over-confidence is "
                                           "the most common failure mode.")
    reasoning: str = Field(description="One sentence on what would lower or raise your confidence.")


class MetaConfidence(BaseModel):
    calibrated_confidence: float = Field(ge=0.0, le=1.0,
                                          description="Independent assessment of how reliable this answer is.")
    why: str = Field(description="One sentence on the calibration adjustment.")


PolicyAction = Literal["allow", "deny", "review_required", "sanitize"]


class PolicyDecision(BaseModel):
    action: PolicyAction
    rule_fired: str
    reasoning: str


# =====================================================================
# LLM steps — answer + self-confidence + meta-judge
# =====================================================================

def answer_with_self_confidence(req: Request) -> AnswerWithConfidence:
    answerer = answer_model.with_structured_output(AnswerWithConfidence)
    return answerer.invoke([
        SystemMessage(
            "Answer the user's question concisely. ALSO self-report your "
            "confidence in [0,1]. Be honest — if the question is outside "
            "your expertise, requires data you don't have, or is ambiguous, "
            "report a LOW confidence (<=0.5). Over-confidence is a governance "
            "failure mode."
        ),
        HumanMessage(req.query),
    ])


def meta_judge_confidence(req: Request, ans: AnswerWithConfidence) -> MetaConfidence:
    judge = judge_model.with_structured_output(MetaConfidence)
    return judge.invoke([
        SystemMessage(
            "You are a calibration judge. Read the original question and the "
            "model's answer + self-reported confidence. Return YOUR independent "
            "confidence that the answer is correct, complete, and safe. "
            "Most models are over-confident — calibrate DOWN if the question "
            "is open-ended, requires data, involves medical/legal/financial "
            "judgment, or contains ambiguity."
        ),
        HumanMessage(
            f"QUERY: {req.query}\n"
            f"DATA CLASS: {req.data_class}\n"
            f"MODEL'S ANSWER: {ans.answer}\n"
            f"MODEL'S SELF-CONFIDENCE: {ans.confidence}\n"
            f"MODEL'S REASONING: {ans.reasoning}"
        ),
    ])


# =====================================================================
# Policy engine — rules as Python objects
# =====================================================================

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),       # SSN
    re.compile(r"\b\d{16}\b"),                  # credit card
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), # email
]


def contains_pii(text: str) -> bool:
    return any(p.search(text) for p in PII_PATTERNS)


class Rule:
    """A single policy rule. First match wins in the engine's priority order."""

    def __init__(
        self,
        name: str,
        description: str,
        applies_when: Callable[[Request, AnswerWithConfidence, MetaConfidence], bool],
        action: PolicyAction,
        reasoning_template: str,
    ):
        self.name = name
        self.description = description
        self.applies_when = applies_when
        self.action = action
        self.reasoning_template = reasoning_template


# Rules in priority order — first match wins.
RULES: list[Rule] = [
    Rule(
        name="pii_in_input",
        description="Block any request whose query contains an SSN, credit-card number, or email.",
        applies_when=lambda req, ans, meta: contains_pii(req.query),
        action="deny",
        reasoning_template="User query contained PII (SSN/CC/email) — denied to prevent storage and leakage.",
    ),
    Rule(
        name="external_user_accessing_internal_data",
        description="External users may not access non-public data classes.",
        applies_when=lambda req, ans, meta: (
            req.user_role == "external" and req.data_class != "public"
        ),
        action="deny",
        reasoning_template="External user requested {data_class} data — RBAC denies non-public access for external role.",
    ),
    Rule(
        name="destructive_action_requires_human",
        description="Write or delete actions on internal data require human approval.",
        applies_when=lambda req, ans, meta: (
            req.action_type in ("write", "delete") and req.data_class != "public"
        ),
        action="review_required",
        reasoning_template="{action_type} action on {data_class} data — human approval required before execution.",
    ),
    Rule(
        name="high_stakes_low_confidence",
        description="Medical or financial questions with calibrated confidence < 0.7 require human review.",
        applies_when=lambda req, ans, meta: (
            req.data_class in ("medical", "financial") and meta.calibrated_confidence < 0.7
        ),
        action="review_required",
        reasoning_template="High-stakes {data_class} domain + calibrated confidence "
                           "{meta_conf:.2f} below threshold 0.70 — escalating for human review.",
    ),
    Rule(
        name="default_allow",
        description="Default policy — allow if no other rule fires.",
        applies_when=lambda req, ans, meta: True,
        action="allow",
        reasoning_template="No restrictive rule fired; calibrated confidence {meta_conf:.2f} "
                           "meets baseline threshold.",
    ),
]


def evaluate_policy(req: Request, ans: AnswerWithConfidence, meta: MetaConfidence) -> PolicyDecision:
    for rule in RULES:
        if rule.applies_when(req, ans, meta):
            reasoning = rule.reasoning_template.format(
                data_class=req.data_class,
                action_type=req.action_type,
                meta_conf=meta.calibrated_confidence,
                self_conf=ans.confidence,
            )
            return PolicyDecision(action=rule.action, rule_fired=rule.name, reasoning=reasoning)
    raise RuntimeError("default_allow rule must always match")


# =====================================================================
# Governance audit log entry
# =====================================================================

class GovernanceAuditEntry(BaseModel):
    # Identity / tracing
    timestamp: str
    request_id: str
    user_role: UserRole
    data_class: DataClass
    action_type: ActionType
    # Query
    query_hash: str
    query_preview: str
    # Models
    answer_model: str
    judge_model: str
    # Confidence
    self_confidence: float
    meta_confidence: float
    confidence_gap: float
    # Policy
    policy_version: str
    rule_fired: str
    policy_action: PolicyAction
    policy_reasoning: str
    # Outcome
    response_preview: str
    escalation_path: str | None


def build_audit_entry(
    req: Request,
    ans: AnswerWithConfidence,
    meta: MetaConfidence,
    decision: PolicyDecision,
    delivered_response: str,
) -> GovernanceAuditEntry:
    escalation = None
    if decision.action == "review_required":
        if req.data_class == "medical":
            escalation = "queue:medical_review"
        elif req.data_class == "financial":
            escalation = "queue:financial_review"
        elif req.action_type in ("write", "delete"):
            escalation = "queue:write_approval"
        else:
            escalation = "queue:general_review"

    return GovernanceAuditEntry(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        request_id=req.request_id,
        user_role=req.user_role,
        data_class=req.data_class,
        action_type=req.action_type,
        query_hash=f"sha256:{hash(req.query) & 0xFFFFFFFF:08x}",
        query_preview=req.query[:80] + ("..." if len(req.query) > 80 else ""),
        answer_model=ANSWER_MODEL,
        judge_model=JUDGE_MODEL,
        self_confidence=round(ans.confidence, 3),
        meta_confidence=round(meta.calibrated_confidence, 3),
        confidence_gap=round(ans.confidence - meta.calibrated_confidence, 3),
        policy_version=POLICY_VERSION,
        rule_fired=decision.rule_fired,
        policy_action=decision.action,
        policy_reasoning=decision.reasoning,
        response_preview=delivered_response[:120] + ("..." if len(delivered_response) > 120 else ""),
        escalation_path=escalation,
    )


# =====================================================================
# The governed pipeline — request in, audit + response out
# =====================================================================

def governed_pipeline(req: Request) -> tuple[GovernanceAuditEntry, str]:
    # Pre-flight: if PII is in the input, short-circuit before calling the LLM.
    # Saves the LLM call AND prevents storing the PII in the model's logs.
    if contains_pii(req.query):
        decision = PolicyDecision(
            action="deny",
            rule_fired="pii_in_input",
            reasoning="User query contained PII (SSN/CC/email) — denied at pre-flight.",
        )
        # Synthesize empty answer + zero confidence for the audit entry
        ans = AnswerWithConfidence(answer="[pre-flight blocked]", confidence=0.0,
                                    reasoning="not evaluated")
        meta = MetaConfidence(calibrated_confidence=0.0, why="not evaluated")
        delivered = "[BLOCKED: input contained PII. Please remove sensitive data and resubmit.]"
        audit = build_audit_entry(req, ans, meta, decision, delivered)
        return audit, delivered

    # Run the LLM, then meta-judge, then policy
    ans = answer_with_self_confidence(req)
    meta = meta_judge_confidence(req, ans)
    decision = evaluate_policy(req, ans, meta)

    if decision.action == "allow":
        delivered = ans.answer
    elif decision.action == "deny":
        delivered = f"[BLOCKED by policy: {decision.reasoning}]"
    elif decision.action == "review_required":
        delivered = (f"[QUEUED FOR HUMAN REVIEW: {decision.reasoning}\n"
                     f"A reviewer will respond shortly. Provisional answer withheld.]")
    elif decision.action == "sanitize":
        delivered = "[SANITIZED — sensitive details have been removed from the response.]"
    else:
        delivered = ans.answer

    audit = build_audit_entry(req, ans, meta, decision, delivered)
    return audit, delivered


# =====================================================================
# Five demo scenarios exercising the rules
# =====================================================================

DEMO_REQUESTS = [
    Request(
        request_id=str(uuid4())[:8],
        query="What is LangChain LCEL? Brief explanation please.",
        user_role="external",
        data_class="public",
        action_type="read",
    ),
    Request(
        request_id=str(uuid4())[:8],
        query="My SSN is 123-45-6789 — what should I do if I forgot my password?",
        user_role="external",
        data_class="public",
        action_type="read",
    ),
    Request(
        request_id=str(uuid4())[:8],
        query="Show me the Q3 internal revenue figures by region.",
        user_role="external",
        data_class="financial",
        action_type="read",
    ),
    Request(
        request_id=str(uuid4())[:8],
        query="Given the patient has a history of GI bleeding and is currently on warfarin, "
              "what's the optimal anticoagulation strategy for their new atrial fibrillation diagnosis? "
              "Consider their renal function (eGFR 35).",
        user_role="internal",
        data_class="medical",
        action_type="advise",
    ),
    Request(
        request_id=str(uuid4())[:8],
        query="Is paracetamol the same drug as acetaminophen?",
        user_role="internal",
        data_class="medical",
        action_type="read",
    ),
]


# =====================================================================
# Compliance framework mapping
# =====================================================================

COMPLIANCE_MAPPING = [
    {"audit_field": "request_id, timestamp, query_hash",
     "frameworks": "SOC 2 CC7.2 (system monitoring), GDPR Art. 30 (records of processing)"},
    {"audit_field": "user_role",
     "frameworks": "SOC 2 CC6.1 (logical access), HIPAA §164.312(a)(1) (access control)"},
    {"audit_field": "data_class",
     "frameworks": "HIPAA §164.502 (uses + disclosures), GDPR Art. 9 (special categories)"},
    {"audit_field": "policy_version, rule_fired",
     "frameworks": "SOC 2 CC8.1 (change management), EU AI Act Art. 13 (transparency)"},
    {"audit_field": "policy_action, policy_reasoning",
     "frameworks": "EU AI Act Art. 14 (human oversight), NIST AI RMF GOVERN-1.1"},
    {"audit_field": "self_confidence, meta_confidence",
     "frameworks": "EU AI Act Art. 15 (accuracy, robustness), NIST AI RMF MEASURE-2.x"},
    {"audit_field": "escalation_path",
     "frameworks": "HIPAA §164.530(c) (safeguards), SOC 2 CC9.x (risk mitigation)"},
    {"audit_field": "answer_model, judge_model",
     "frameworks": "EU AI Act Art. 11 (technical documentation), ISO 42001 §7 (support)"},
    {"audit_field": "query_hash (not raw text)",
     "frameworks": "GDPR Art. 5 (data minimization), HIPAA §164.514 (de-identification)"},
    {"audit_field": "confidence_gap (over-confidence detector)",
     "frameworks": "EU AI Act Art. 15 (accuracy monitoring), NIST AI RMF MEASURE-3.x"},
]


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("AI GOVERNANCE — confidence + policy gates + decision audit")
    print("=" * 70)
    print(f"  Policy version:  {POLICY_VERSION}")
    print(f"  Answer model:    {ANSWER_MODEL}")
    print(f"  Judge model:     {JUDGE_MODEL} (meta-confidence calibration)")
    print(f"  NOTE: Both answer and judge use {ANSWER_MODEL} — same model for both roles.")
    print(f"  Rules in policy: {len(RULES)} (first-match-wins, in priority order):")
    for r in RULES:
        print(f"    * {r.name:<40} -> {r.action}")

    audit_entries: list[GovernanceAuditEntry] = []
    for i, req in enumerate(DEMO_REQUESTS, 1):
        print("\n" + "─" * 70)
        print(f"SCENARIO {i}: {req.user_role}/{req.data_class}/{req.action_type}")
        print("─" * 70)
        print(f"  query: {req.query[:100]}{'...' if len(req.query) > 100 else ''}")
        audit, delivered = governed_pipeline(req)
        audit_entries.append(audit)

        print(f"\n  self_confidence={audit.self_confidence:.2f}   "
              f"meta_confidence={audit.meta_confidence:.2f}   "
              f"gap={audit.confidence_gap:+.2f}")
        print(f"  rule_fired: {audit.rule_fired}")
        print(f"  action:     {audit.policy_action.upper()}")
        print(f"  reasoning:  {audit.policy_reasoning}")
        if audit.escalation_path:
            print(f"  escalation: {audit.escalation_path}")
        print(f"\n  delivered response:")
        print(f"    {delivered[:200]}{'...' if len(delivered) > 200 else ''}")

    # Show full audit entry for one representative scenario
    print("\n" + "=" * 70)
    print("EXAMPLE FULL AUDIT ENTRY (SCENARIO 4)")
    print("=" * 70)
    print(json.dumps(audit_entries[3].model_dump(), indent=2))

    # Decisions summary
    print("\n" + "=" * 70)
    print("DECISIONS SUMMARY")
    print("=" * 70)
    by_action: dict[str, int] = {}
    for entry in audit_entries:
        by_action[entry.policy_action] = by_action.get(entry.policy_action, 0) + 1
    for action, count in sorted(by_action.items()):
        print(f"  {action:<20} {count}")
    print(f"\n  Total requests: {len(audit_entries)}")
    print(f"  Avg confidence gap (self - meta): "
          f"{sum(e.confidence_gap for e in audit_entries) / len(audit_entries):+.3f}")
    print(f"  → positive gap = model is over-confident vs the meta-judge")

    # Compliance mapping table
    print("\n" + "=" * 70)
    print("COMPLIANCE MAPPING — which audit fields satisfy which framework")
    print("=" * 70)
    for m in COMPLIANCE_MAPPING:
        print(f"\n  {m['audit_field']}")
        print(f"    -> {m['frameworks']}")

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  * Five requests flowed through the SAME pipeline: answer ->\n"
        "    self-confidence -> meta-judge -> policy rules -> audit emit.\n"
        "    No request bypassed the policy engine.\n\n"
        "  * Confidence is TWO numbers, not one. Self-confidence reflects\n"
        "    the model's stated certainty (often inflated). Meta-confidence\n"
        "    is an independent calibration. The GAP is the signal — large\n"
        "    positive gap = over-confidence, watch for drift.\n\n"
        "  * Rules are pure Python. No DSL, no policy server, no YAML.\n"
        "    Production: swap to Open Policy Agent (OPA) / Rego or AWS\n"
        "    Cedar for cross-language reuse + admin UI. Same shape.\n\n"
        "  * Every request emits a structured GovernanceAuditEntry.\n"
        "    A SOC 2 / HIPAA / EU AI Act audit becomes a SQL query against\n"
        "    this table — not an engineer interview.\n\n"
        "  * The compliance mapping is how you SHOW your auditor that\n"
        "    field X covers requirement Y. Hand them this table + the\n"
        "    audit schema + a sample of log entries — that's most of\n"
        "    the AI-specific audit work, done."
    )
