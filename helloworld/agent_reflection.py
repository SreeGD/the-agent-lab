"""Reflection pattern — writer + critic loop.

The writer drafts an answer. A separate critic reviews it against explicit
criteria. If the critic finds issues, it returns specific feedback and the
writer revises. Loop until the critic responds with 'APPROVED' or the
iteration budget is exhausted.

The two LLM calls per iteration (writer + critic) use different system
prompts to keep them honest — the critic isn't just rubber-stamping its
own work.
"""

from dataclasses import dataclass
from time import perf_counter

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 4

TASK = (
    "Write a 3-paragraph technical explainer about prompt caching for a "
    "senior backend engineer. Cover: (a) the mechanism (KV cache, prefill "
    "skip), (b) why it's cheaper, (c) one production gotcha. Be specific "
    "and concise — no filler."
)


# =====================================================================
# Two prompts: writer drafts, critic reviews. DIFFERENT system prompts
# so the same model wears two distinct hats — important to keep them
# from rubber-stamping each other.
# =====================================================================

writer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior technical writer who produces concise, accurate "
     "explanations for engineers. Your audience: a senior backend engineer "
     "who knows systems and networking but is newer to LLM internals. "
     "Output exactly 3 paragraphs. Avoid filler ('this is important', "
     "'in summary', etc.). Use specific terms (KV cache, prefill, TTL) "
     "rather than vague ones."),
    ("human",
     "Task: {task}\n\n"
     "Previous draft (empty on first iteration):\n{prior_draft}\n\n"
     "Critic feedback (empty on first iteration):\n{feedback}\n\n"
     "Write a draft (or revise the prior one to address the feedback)."),
])

critic_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a strict technical reviewer. Your job is to find specific, "
     "concrete improvements. Evaluate against these criteria:\n"
     "  (1) Accuracy: every technical claim must be correct\n"
     "  (2) Specificity: avoid vague language; use real numbers/terms\n"
     "  (3) Completeness: covers mechanism + cost + gotcha\n"
     "  (4) Density: exactly 3 paragraphs, no filler\n"
     "\n"
     "If the draft meets ALL criteria, respond with EXACTLY one word: APPROVED\n"
     "Otherwise, list 1-3 specific improvements, one per line, prefixed "
     "with '- '. Do NOT rewrite the draft yourself — point out issues only."),
    ("human", "Task: {task}\n\nDraft:\n{draft}\n\nReview."),
])

model = ChatAnthropic(model=MODEL, temperature=0)

# Pipe to AIMessage (no StrOutputParser) so we can capture usage_metadata.
writer_pipe = writer_prompt | model
critic_pipe = critic_prompt | model


# =====================================================================
# Metrics tracking
# =====================================================================

@dataclass
class Metrics:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def absorb(self, ai: AIMessage) -> None:
        self.llm_calls += 1
        if ai.usage_metadata:
            self.input_tokens += ai.usage_metadata.get("input_tokens", 0)
            self.output_tokens += ai.usage_metadata.get("output_tokens", 0)

    def cost_usd(self) -> float:
        # Sonnet 4.6: $3 / 1M input, $15 / 1M output
        return (self.input_tokens * 3 + self.output_tokens * 15) / 1_000_000


# =====================================================================
# The reflection loop
# =====================================================================

def run_reflection() -> tuple[str, Metrics, int]:
    metrics = Metrics()
    draft, feedback = "", ""

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n=== ITERATION {iteration} ===")

        # --- WRITE ---
        writer_msg = writer_pipe.invoke(
            {"task": TASK, "prior_draft": draft, "feedback": feedback}
        )
        metrics.absorb(writer_msg)
        draft = writer_msg.content
        print(f"[writer]    drafted ({len(draft)} chars)")

        # --- CRITIQUE ---
        critic_msg = critic_pipe.invoke({"task": TASK, "draft": draft})
        metrics.absorb(critic_msg)
        feedback = critic_msg.content.strip()
        print(f"[critic]    {feedback[:200]}{'...' if len(feedback) > 200 else ''}")

        # --- DECIDE ---
        if feedback.upper().startswith("APPROVED"):
            print(f"\n>>> approved on iteration {iteration}")
            return draft, metrics, iteration

    print(f"\n>>> iteration budget ({MAX_ITERATIONS}) exhausted")
    return draft, metrics, MAX_ITERATIONS


# =====================================================================
# Run + report
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("REFLECTION agent — writer + critic loop")
    print("=" * 70)
    print(f"task: {TASK}")
    print(f"max iterations: {MAX_ITERATIONS}")

    t0 = perf_counter()
    final_draft, metrics, iterations = run_reflection()
    elapsed = perf_counter() - t0

    print("\n" + "=" * 70)
    print("FINAL DRAFT")
    print("=" * 70)
    print(final_draft)

    print("\n" + "=" * 70)
    print("METRICS")
    print("=" * 70)
    print(f"  iterations    : {iterations}")
    print(f"  llm_calls     : {metrics.llm_calls}")
    print(f"  input_tokens  : {metrics.input_tokens}")
    print(f"  output_tokens : {metrics.output_tokens}")
    print(f"  wall_clock    : {elapsed:.2f}s")
    print(f"  cost_usd      : ${metrics.cost_usd():.6f}")
