"""System Design Interview Helper — turn a brief into a full design doc.

Senior interviews ask: "Design <LLM system X>. You have 45 minutes."
The signal isn't "do you know LangChain" — it's: do you ask the right
requirement-clarifying questions, draw the right boxes, defend the right
trade-offs under pushback?

This file is a runnable interview-prep tool. Pass a one-line problem
statement (e.g., "Design a customer-support chatbot for a fintech with
10M users"). It uses Claude with structured output to produce:

  - Requirements clarification (the 8 questions you SHOULD ask, answered
    with the most likely interviewer position for THIS scenario)
  - Architecture (ASCII diagram + component descriptions)
  - Data-flow narrative
  - Trade-offs (3-5 named decisions with options + recommendation)
  - Capacity estimates (rough scale math you should defend on the spot)
  - Risk register (likelihood × impact + mitigation)
  - Likely interviewer follow-ups (so you can pre-arm yourself)

The demo runs three classic scenarios end-to-end. Use it on your own
problem statements to drill before a real interview.
"""

from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "claude-sonnet-4-6"
model = ChatAnthropic(model=MODEL, temperature=0)


# =====================================================================
# The 8-question framework — the FIRST thing you do in any interview
# =====================================================================

THE_8_QUESTIONS = [
    "Scale: QPS, MAU, tokens/day? Peak vs steady?",
    "Latency target: TTFT, p95 end-to-end? Sync vs streaming UX?",
    "Quality bar: acceptable error rate, hallucination tolerance, eval framework?",
    "Cost ceiling: monthly budget? Per-call cost target?",
    "Multi-tenancy: single vs multi-tenant? Tenant isolation requirements?",
    "Safety + compliance: PII, HIPAA, SOC2, regulated industry constraints?",
    "Existing infrastructure: what must I reuse (auth, DB, deploy platform)?",
    "Build vs buy: which capabilities are differentiating vs commodity?",
]


# =====================================================================
# Structured output schemas — what a design doc actually contains
# =====================================================================

class TradeOff(BaseModel):
    name: str = Field(description="The decision under consideration, e.g. 'Embedding model selection'.")
    options: list[str] = Field(description="2-3 candidate approaches.")
    recommendation: str = Field(description="Which option to choose for THIS scenario.")
    reasoning: str = Field(description="One-paragraph justification including the constraint that drives it.")


class CapacityEstimate(BaseModel):
    metric: str = Field(description="What's being estimated, e.g. 'monthly API cost'.")
    value: str = Field(description="The estimate with units, e.g. '$50K/mo at 100M tokens/day'.")
    assumptions: str = Field(description="The assumptions you're making — interviewer will probe these.")


class Risk(BaseModel):
    risk: str = Field(description="What could go wrong.")
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str = Field(description="Concrete engineering action that reduces likelihood OR impact.")


class SystemDesign(BaseModel):
    one_line_summary: str = Field(description="A single sentence describing what you're building and for whom.")
    requirements_clarifications: list[str] = Field(
        description="The 8 requirement questions answered with the MOST LIKELY interviewer position "
                    "for this specific scenario. One bullet per question, prefix the answer with the question topic."
    )
    architecture_ascii: str = Field(
        description="A multi-line ASCII diagram of the system, ~10-15 lines. "
                    "Use boxes [name], arrows -->, and labels for components. "
                    "Show the request flow left-to-right or top-to-bottom."
    )
    component_descriptions: list[str] = Field(
        description="One short line per component shown in the diagram, format: 'name: role'."
    )
    data_flow_narrative: str = Field(
        description="3-5 sentences walking through what happens to a single request from arrival to response."
    )
    trade_offs: list[TradeOff] = Field(description="3-5 key design decisions with their options.")
    capacity_estimates: list[CapacityEstimate] = Field(
        description="3-5 capacity numbers you should be ready to defend: QPS, tokens/day, monthly cost, p95 latency, storage."
    )
    risks: list[Risk] = Field(description="3-5 risks with likelihood/impact ratings and mitigations.")
    likely_followups: list[str] = Field(
        description="5-7 follow-up questions a sharp interviewer is likely to ask. Phrase as questions."
    )


# =====================================================================
# The design generator
# =====================================================================

SYSTEM_DESIGN_PROMPT = """You are an experienced AI systems architect helping a candidate prepare
for a senior+ system design interview.

The candidate gives you a problem statement. You return a STRUCTURED design
document covering:
  - clarifying requirement questions (answered with realistic assumptions for this scenario)
  - architecture diagram (ASCII)
  - component descriptions
  - data flow
  - trade-offs (3-5 named decisions with options + recommendation)
  - capacity estimates (defendable scale numbers with assumptions)
  - risk register (likelihood/impact/mitigation)
  - likely interviewer follow-up questions

Style: senior IC voice. Specific numbers, not hand-waving. Cite real models
(claude-sonnet-4-6, claude-haiku-4-5), real services (Anthropic, Pinecone,
Datadog, Fly, AWS), real algorithms (BM25 + RRF, CRAG). If a trade-off has
a clear best answer for the scenario, recommend it explicitly — don't hedge.

Each capacity estimate MUST include a back-of-envelope number with units AND
the assumptions behind it (e.g. 'avg 5 messages/MAU/day × 500 tokens × 10M
MAU = 25B tokens/month'). The interviewer WILL ask 'where did that number
come from'."""


def design_system(problem: str, max_retries: int = 3) -> SystemDesign:
    designer = model.with_structured_output(SystemDesign)
    last_err = None
    for attempt in range(max_retries):
        try:
            return designer.invoke([
                SystemMessage(SYSTEM_DESIGN_PROMPT),
                HumanMessage(f"PROBLEM STATEMENT:\n{problem}"),
            ])
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"  (transient error on attempt {attempt + 1}: {type(e).__name__}, retrying...)")
    raise last_err


# =====================================================================
# Rendering — turn the structured design into a readable doc
# =====================================================================

def render(design: SystemDesign) -> str:
    out: list[str] = []
    out.append("=" * 70)
    out.append(design.one_line_summary)
    out.append("=" * 70)

    out.append("\n## Requirements clarifications (the 8 questions, answered)\n")
    for r in design.requirements_clarifications:
        out.append(f"  • {r}")

    out.append("\n## Architecture\n")
    out.append(design.architecture_ascii)

    out.append("\n  Components:")
    for c in design.component_descriptions:
        out.append(f"    • {c}")

    out.append("\n## Data flow\n")
    out.append(f"  {design.data_flow_narrative}")

    out.append("\n## Trade-offs\n")
    for t in design.trade_offs:
        out.append(f"  ▸ {t.name}")
        out.append(f"      options: {' | '.join(t.options)}")
        out.append(f"      RECOMMEND: {t.recommendation}")
        out.append(f"      because: {t.reasoning}")
        out.append("")

    out.append("## Capacity estimates (defend each one)\n")
    for c in design.capacity_estimates:
        out.append(f"  ▸ {c.metric}: {c.value}")
        out.append(f"      assumes: {c.assumptions}")
        out.append("")

    out.append("## Risk register\n")
    out.append(f"  {'risk':<60} {'L':>3} {'I':>3}  mitigation")
    out.append(f"  {'-'*60} {'-':>3} {'-':>3}  {'-'*40}")
    for r in design.risks:
        out.append(f"  {r.risk[:58]:<60} {r.likelihood[0].upper():>3} {r.impact[0].upper():>3}  {r.mitigation[:50]}")

    out.append("\n## Likely interviewer follow-ups (pre-arm yourself)\n")
    for q in design.likely_followups:
        out.append(f"  ? {q}")

    return "\n".join(out)


# =====================================================================
# Demo — three classic interview scenarios
# =====================================================================

DEMO_SCENARIOS = [
    "Design a customer-support chatbot for a fintech with 10M monthly active users. "
    "Users ask about transactions, account issues, fraud disputes. The bot must escalate "
    "complex cases to a human agent.",

    "Design a multi-tenant RAG-as-a-service platform. 1000 enterprise customers each upload "
    "their own document corpus (avg 100K docs per tenant) and query against it. Strict tenant "
    "isolation required.",

    "Design an LLM-powered code-review bot that runs inside a company's CI pipeline. "
    "It reviews PRs, comments on issues, and can suggest fixes. ~5000 PRs per day across "
    "200 repositories.",

    "Design an AI coding assistant agent platform like Claude Code / Cursor / "
    "Windsurf — a CLI-and-IDE tool that runs locally on a developer's machine, "
    "can read and edit files, execute shell commands with human approval gates, "
    "call external tools (web search, GitHub, MCP servers), and maintain "
    "conversational + project state across sessions. Targeted at professional "
    "engineers; ~100K DAU now, expanding to ~1M. Free tier + paid pro tier. "
    "Must work offline-friendly for code reading; LLM calls always remote.",
]


def print_8_questions():
    print("=" * 70)
    print("THE 8 QUESTIONS — ask these in the FIRST 5 minutes of any interview")
    print("=" * 70)
    for i, q in enumerate(THE_8_QUESTIONS, 1):
        print(f"  {i}. {q}")
    print()


if __name__ == "__main__":
    print_8_questions()

    for i, problem in enumerate(DEMO_SCENARIOS, 1):
        print("\n" + "█" * 70)
        print(f"SCENARIO {i}")
        print("█" * 70)
        print(f"  Problem: {problem}\n")

        design = design_system(problem)
        print(render(design))

    print("\n\n" + "=" * 70)
    print("HOW TO USE THIS TOOL")
    print("=" * 70)
    print(
        "  • Practice mode: pick a problem from your target company's interview\n"
        "    loop (or generate one — 'Design an X for Y users'). Try to produce\n"
        "    YOUR OWN design first. Then run this tool and diff. Where it pushed\n"
        "    further than you did is your study list.\n\n"
        "  • Calibration mode: pick a problem you've already solved at work.\n"
        "    Compare the tool's design to what you actually shipped. Where the\n"
        "    tool went different is either a missed alternative (worth knowing)\n"
        "    or a context-specific reason it wouldn't work in your env (worth\n"
        "    being able to articulate).\n\n"
        "  • Pressure mode: read each likely_followup aloud and answer in 30s.\n"
        "    If you can't, that's a study item. Real interviews ARE that fast.\n\n"
        "  • Cost: ~$0.03 per scenario at sonnet-4-6 with this prompt. Hammer it.\n"
        "    Forty scenarios = $1.20 = cheapest interview prep in history."
    )
