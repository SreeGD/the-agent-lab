# Requires: ollama serve + ollama pull llama3.2
"""AI Product & UX Audit — should this be AI, and if so, what UX patterns?

Most AI features ship with the wrong UX shape. Deterministic problems
forced into LLMs. No confidence surfacing. No edit path. No escalation.
Vague "something went wrong" failures. The product feels haunted instead
of magical.

This tool runs an opinionated audit on a proposed AI feature and returns:

  • Whether the feature should be AI at all (or rules / DSL / lookup)
  • The right AI scope (full / assisted / HITL / suggestion-only)
  • Which UX patterns are MANDATORY (10-pattern catalog)
  • Trust calibration messaging (what to set user expectations to)
  • Failure UX per failure mode (what user sees + what app does)
  • Risk register (privacy / accuracy / cost / safety)
  • Concrete recommendations

Same structured-output pattern as Sessions 18 (system design) and 20
(governance). The four artifacts together — design helper + red-team +
governance + UX audit — form a Track G "AI feature kit" you run on any
proposal before it ships.
"""

from typing import Literal

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "llama3.2"
model = ChatOllama(model=MODEL, temperature=0)


# =====================================================================
# The UX pattern catalog — 10 patterns the auditor draws from
# =====================================================================

UX_PATTERN_CATALOG = """
10 UX patterns for AI features. Each has a "when" clause — using a
pattern outside its when-clause adds friction without trust gain.

1. CONFIDENCE_DISPLAY
   Show numerical or visual confidence next to the AI output.
   WHEN: high-stakes outputs (medical, financial, legal, irreversible)
   NOT: trivial tasks (autocomplete, low-impact suggestions)

2. CITATIONS_SOURCES
   Show which source documents grounded the answer (page numbers, URLs).
   WHEN: factual / knowledge-retrieval features (RAG)
   NOT: creative writing, ideation, code generation from scratch

3. EDITABLE_OUTPUT
   The AI output is a draft; the user can edit before applying.
   WHEN: the AI output IS the final artifact (email draft, code, doc)
   NOT: pure answer-retrieval (chatbot Q&A)

4. ALTERNATIVES_REGENERATE
   Show 2-3 alternatives, or a regenerate button.
   WHEN: multiple valid answers exist (titles, summaries, code variants)
   NOT: single-truth questions (math answers, factual lookups)

5. UNDO
   Reverse the most recent AI action.
   WHEN: AI takes any state-changing action (file edit, send email, db write)
   NOT: read-only outputs

6. STREAMING_FEEDBACK
   Tokens appear as they're generated; status indicator for tool calls.
   WHEN: any LLM call > 1 second
   NOT: sub-second responses, batch operations

7. ESCALATION_TO_HUMAN
   Clear path for user to hand off to a real person.
   WHEN: high-stakes domains (support, medical, legal); user is stuck
   NOT: low-stakes utility tools where no human equivalent exists

8. HONEST_REFUSAL
   Model says "I don't know" when grounding is insufficient.
   WHEN: factual / safety-critical features (always)
   NOT: creative tasks where any output is acceptable

9. SUGGESTION_NOT_ACTION
   AI proposes; user approves before execution.
   WHEN: actions with non-trivial cost or irreversibility (send email,
         run SQL on prod, delete files)
   NOT: pure information retrieval, draft generation in safe contexts

10. PROGRESSIVE_DISCLOSURE
    Show short summary first; user clicks to see detail/reasoning.
    WHEN: complex outputs (long analyses, multi-step reasoning chains)
    NOT: short outputs that fit on one screen
"""


# =====================================================================
# Schemas
# =====================================================================

AIScope = Literal[
    "full_ai",            # AI handles end-to-end, fully autonomously
    "ai_assisted",        # AI does most of the work, human reviews
    "human_in_the_loop",  # Human approves AI's structured decisions
    "suggestion_only",    # AI suggests; human always chooses to apply
    "not_ai",             # Should be rules / DSL / classical algorithm
]


class UXPattern(BaseModel):
    name: Literal[
        "CONFIDENCE_DISPLAY", "CITATIONS_SOURCES", "EDITABLE_OUTPUT",
        "ALTERNATIVES_REGENERATE", "UNDO", "STREAMING_FEEDBACK",
        "ESCALATION_TO_HUMAN", "HONEST_REFUSAL", "SUGGESTION_NOT_ACTION",
        "PROGRESSIVE_DISCLOSURE",
    ]
    why: str = Field(description="Why this pattern is mandatory for THIS feature.")
    how: str = Field(description="Concrete implementation note for the UI.")


class FailureMode(BaseModel):
    mode: Literal[
        "confident_wrong",  # the most dangerous — high confidence on wrong answer
        "refuses_unnecessarily",
        "slow_response",
        "inconsistent_outputs",
        "off_topic_drift",
        "tool_failure",     # underlying tool/API call failed
        "rate_limited",
    ]
    user_sees: str = Field(description="What the UI shows the user when this happens.")
    app_action: str = Field(description="What the application does internally (retry, escalate, log).")


class Risk(BaseModel):
    risk: str
    severity: Literal["low", "medium", "high"]
    mitigation: str


class UXAudit(BaseModel):
    one_line_summary: str = Field(description="Single sentence describing what's being audited.")
    should_be_ai: Literal[
        "yes_full_ai", "yes_assisted", "yes_with_human_approval",
        "probably_rules", "no_not_ai",
    ]
    should_be_ai_reasoning: str = Field(description="Why this verdict — what makes it AI-fit or not.")
    ai_scope: AIScope
    required_ux_patterns: list[UXPattern] = Field(description="3-6 mandatory patterns for this feature.")
    trust_calibration: list[str] = Field(
        description="3-5 specific messages / disclaimers / behaviors that calibrate user expectations. "
                    "e.g., 'Show \"AI-generated, please verify\" badge on every output.'"
    )
    failure_ux: list[FailureMode] = Field(description="3-5 failure modes + the UI handling for each.")
    risks: list[Risk] = Field(description="3-5 product risks beyond just engineering.")
    recommendations: list[str] = Field(
        description="3-5 concrete next-step actions for the team. Specific (not 'consider X'); "
                    "e.g., 'Add confidence chip below every reply; threshold at 0.7 for auto-send'."
    )
    rollout_guidance: str = Field(
        description="One paragraph on how to ROLL OUT this feature safely: shadow mode, "
                    "percentage rollout, kill switch, success metrics."
    )


# =====================================================================
# Auditor
# =====================================================================

AUDIT_SYSTEM = f"""You are a senior AI product reviewer. The team will hand you a
proposed AI feature; you produce a STRUCTURED audit covering:

  - Whether the feature should be AI at all (rules / DSL / lookup might be better)
  - The right AI scope (full / assisted / HITL / suggestion-only)
  - 3-6 MANDATORY UX patterns drawn from the catalog below
  - Trust calibration messages (specific UI text or behaviors)
  - 3-5 failure modes + the UI handling for each
  - 3-5 product risks (privacy, accuracy, cost, safety)
  - 3-5 concrete recommendations (specific, not 'consider X')
  - Rollout guidance (shadow → percentage → full, with kill switch)

Style: opinionated. Pick ONE recommendation per question. If the feature
should NOT be AI, say so directly — *"deterministic problem, use rules"*
saves the team months. If the feature is AI but the proposed scope is
wrong, say so. Don't hedge.

The UX pattern catalog (each pattern has a WHEN clause — using it outside
the when-clause adds friction without trust gain):

{UX_PATTERN_CATALOG}

When listing required_ux_patterns, only include patterns whose WHEN clause
fits THIS specific feature. Don't include all 10 by default."""


def audit_feature(feature_description: str) -> UXAudit:
    auditor = model.with_structured_output(UXAudit)
    return auditor.invoke([
        SystemMessage(AUDIT_SYSTEM),
        HumanMessage(f"FEATURE PROPOSAL:\n{feature_description}"),
    ])


# =====================================================================
# Rendering
# =====================================================================

def render(audit: UXAudit) -> str:
    out: list[str] = []
    out.append("=" * 70)
    out.append(audit.one_line_summary)
    out.append("=" * 70)

    out.append(f"\n## Should this be AI?")
    out.append(f"  Verdict: {audit.should_be_ai.upper()}")
    out.append(f"  AI scope: {audit.ai_scope}")
    out.append(f"  Reasoning: {audit.should_be_ai_reasoning}")

    out.append(f"\n## Required UX patterns ({len(audit.required_ux_patterns)})\n")
    for p in audit.required_ux_patterns:
        out.append(f"  ▸ {p.name}")
        out.append(f"      why: {p.why}")
        out.append(f"      how: {p.how}")
        out.append("")

    out.append(f"## Trust calibration\n")
    for tc in audit.trust_calibration:
        out.append(f"  • {tc}")

    out.append(f"\n## Failure UX per mode\n")
    for fm in audit.failure_ux:
        out.append(f"  ▸ {fm.mode}")
        out.append(f"      user sees: {fm.user_sees}")
        out.append(f"      app does:  {fm.app_action}")
        out.append("")

    out.append(f"## Risks\n")
    for r in audit.risks:
        out.append(f"  [{r.severity.upper():<6}] {r.risk}")
        out.append(f"            mitigation: {r.mitigation}")
        out.append("")

    out.append(f"## Concrete recommendations\n")
    for rec in audit.recommendations:
        out.append(f"  → {rec}")

    out.append(f"\n## Rollout guidance\n")
    out.append(f"  {audit.rollout_guidance}")

    return "\n".join(out)


# =====================================================================
# Demo features — one per AI-fit category
# =====================================================================

DEMO_FEATURES = [
    "AI suggests a reply to customer support emails; a human agent reviews and sends. "
    "Goal: reduce time-to-first-response. Currently agents spend ~3 min drafting; want under 1 min.",

    "AI auto-categorizes incoming support tickets by topic (billing, technical, account, abuse). "
    "Output is a single tag; downstream routing depends on it. 10K tickets/day.",

    "AI summarizes a user's monthly bank statement into a 3-sentence overview ('You spent $X on Y, "
    "saved $Z, your largest unusual charge was W'). Shown on the home screen of a banking app.",

    "AI generates a SQL query from a natural-language analytics question typed by a non-engineer. "
    "The query runs against the company's data warehouse. Used by ~50 internal analysts daily.",
]


def print_pattern_catalog():
    print("=" * 70)
    print("UX PATTERN CATALOG (10 patterns, with WHEN clauses)")
    print("=" * 70)
    print(UX_PATTERN_CATALOG)


if __name__ == "__main__":
    print_pattern_catalog()

    for i, feature in enumerate(DEMO_FEATURES, 1):
        print("\n" + "█" * 70)
        print(f"FEATURE {i}")
        print("█" * 70)
        print(f"  Proposal: {feature}\n")
        audit = audit_feature(feature)
        print(render(audit))

    print("\n" + "=" * 70)
    print("THE TRACK G AI FEATURE KIT")
    print("=" * 70)
    print(
        "  Run a proposal through all four Track G tools before it ships:\n\n"
        "    Session 18  →  System design helper      (architecture + capacity math)\n"
        "    Session 19  →  Red-team harness          (attack catalog + defense layers)\n"
        "    Session 20  →  Governance auditor        (confidence + policy + audit)\n"
        "    Session 21  →  UX audit helper           (THIS — should-be-AI + patterns)\n\n"
        "  Combined output: complete architecture + attack/defense map + governance\n"
        "  policy + UX shape. Hand that bundle to leadership / legal / design and you\n"
        "  have an end-to-end pre-flight that costs ~$0.30 and ~3 minutes — vs months\n"
        "  of meetings to surface the same questions.\n\n"
        "  The discipline these tools encode is the difference between a feature that\n"
        "  ships smoothly and one that ships, then breaks, then gets pulled, then\n"
        "  gets rebuilt the right way."
    )

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • Four feature proposals went through a single audit pipeline.\n"
        "  • Each produced: AI-fit verdict, scope, 3-6 mandatory UX patterns,\n"
        "    trust calibration messages, failure UX per mode, risk register,\n"
        "    concrete recommendations, rollout guidance.\n\n"
        "  • The auditor refuses to hedge — picks ONE scope, ONE recommendation\n"
        "    per question. That's the senior-product signal: a clear opinion\n"
        "    backed by the constraint that drove it.\n\n"
        "  • The 10 UX patterns each have a WHEN clause. The audit only\n"
        "    includes patterns whose WHEN fits the feature — not all 10 by\n"
        "    default. Pattern-without-when adds friction; pattern-when-needed\n"
        "    builds trust.\n\n"
        "  • Failure UX is the half most teams skip. Confident-wrong is the\n"
        "    worst because users CAN'T self-correct. The audit forces a\n"
        "    explicit user-facing handling for each failure mode.\n\n"
        "  • Rollout guidance turns 'launch the feature' into 'shadow ->\n"
        "    1%% -> 10%% -> full, with metrics and a kill switch'. Same\n"
        "    discipline as classical feature flags, applied to AI."
    )
