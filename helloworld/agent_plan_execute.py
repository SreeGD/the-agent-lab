"""Plan-and-Execute pattern — planner emits a typed Plan, executor runs
each step in order, aggregator combines the results into a final answer.

Three distinct LLM roles with different system prompts:
  - Planner   : decomposes the task into 3-5 ordered subtasks (typed via Pydantic)
  - Executor  : runs ONE subtask at a time, with prior step results as context
  - Aggregator: synthesizes the step results into a coherent final answer

Unlike Reflection, the call count is essentially fixed (1 + N + 1) and there's
no self-correction loop — the plan is committed upfront and executed linearly.
"""

from dataclasses import dataclass
from time import perf_counter

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "claude-sonnet-4-6"

TASK = (
    "Write a 3-paragraph technical explainer about prompt caching for a "
    "senior backend engineer. Cover: (a) the mechanism (KV cache, prefill "
    "skip), (b) why it's cheaper, (c) one production gotcha. Be specific "
    "and concise — no filler."
)


# =====================================================================
# Typed plan — the planner must output a structured Plan, not free-form text.
# This is the key reliability trick: planner can't waffle; either it produces
# a valid Plan or it fails at Pydantic validation.
# =====================================================================

class Step(BaseModel):
    """One ordered subtask in the plan."""
    description: str = Field(description="Clear, concrete subtask. Imperative voice.")
    rationale: str = Field(description="Why this step is needed for the overall task.")


class Plan(BaseModel):
    """Ordered list of 3-5 subtasks. Each step produces a concrete artifact."""
    steps: list[Step] = Field(description="3-5 ordered subtasks")


model = ChatAnthropic(model=MODEL, temperature=0)

# include_raw=True keeps the underlying AIMessage so we can grab usage_metadata
planner_pipe = model.with_structured_output(Plan, include_raw=True)


# =====================================================================
# Executor + aggregator prompts. Different system prompts again.
# =====================================================================

executor_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a focused technical executor. Complete EXACTLY the step you "
     "are given — no more, no less. Output the deliverable for this step "
     "(text, bullets, or whatever the step calls for). Stay tight; the "
     "aggregator will combine your output with the others."),
    ("human",
     "Overall task: {task}\n\n"
     "Prior step results (for context):\n{prior_context}\n\n"
     "Current step: {step}\n"
     "Why this step matters: {rationale}\n\n"
     "Execute this step. Output ONLY the step's deliverable."),
])

aggregator_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a synthesizer. Combine prior step results into a polished, "
     "coherent final answer that meets the original task. Smooth out any "
     "duplication. The final output should read as one piece — not as "
     "stitched-together sections."),
    ("human",
     "Original task: {task}\n\n"
     "Step results:\n{step_results}\n\n"
     "Produce the final answer."),
])

executor_pipe = executor_prompt | model
aggregator_pipe = aggregator_prompt | model


# =====================================================================
# Metrics
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
        return (self.input_tokens * 3 + self.output_tokens * 15) / 1_000_000


# =====================================================================
# Three stages
# =====================================================================

def run_plan_execute() -> tuple[str, Metrics, Plan]:
    metrics = Metrics()

    # --- STAGE 1: PLAN ---
    print("\n=== STAGE 1: PLAN ===")
    planner_result = planner_pipe.invoke([
        SystemMessage(
            "Decompose the task into 3-5 ordered subtasks. Each step must "
            "produce a concrete artifact. Steps should be independent enough "
            "that an executor can run them with only the prior step's output "
            "as context."
        ),
        HumanMessage(f"Task: {TASK}"),
    ])
    metrics.absorb(planner_result["raw"])
    plan: Plan = planner_result["parsed"]

    print(f"[planner] produced {len(plan.steps)} steps:")
    for i, step in enumerate(plan.steps, 1):
        print(f"  {i}. {step.description}")
        print(f"     why: {step.rationale}")

    # --- STAGE 2: EXECUTE ---
    print("\n=== STAGE 2: EXECUTE ===")
    step_results: list[str] = []

    for i, step in enumerate(plan.steps, 1):
        prior = "\n\n".join(f"Step {j} result:\n{r}" for j, r in enumerate(step_results, 1))
        exec_msg = executor_pipe.invoke({
            "task": TASK,
            "prior_context": prior or "(no prior steps)",
            "step": step.description,
            "rationale": step.rationale,
        })
        metrics.absorb(exec_msg)
        step_results.append(exec_msg.content)
        preview = exec_msg.content[:90].replace("\n", " ")
        print(f"  [step {i}] {preview}...")

    # --- STAGE 3: AGGREGATE ---
    print("\n=== STAGE 3: AGGREGATE ===")
    combined = "\n\n".join(
        f"--- Step {i} ({plan.steps[i-1].description[:50]}...) ---\n{r}"
        for i, r in enumerate(step_results, 1)
    )
    agg_msg = aggregator_pipe.invoke({"task": TASK, "step_results": combined})
    metrics.absorb(agg_msg)
    print("[aggregator] produced final answer")

    return agg_msg.content, metrics, plan


# =====================================================================
# Run + report
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PLAN-AND-EXECUTE agent — planner + executor + aggregator")
    print("=" * 70)
    print(f"task: {TASK}")

    t0 = perf_counter()
    final_answer, metrics, plan = run_plan_execute()
    elapsed = perf_counter() - t0

    print("\n" + "=" * 70)
    print("FINAL ANSWER")
    print("=" * 70)
    print(final_answer)

    print("\n" + "=" * 70)
    print("METRICS")
    print("=" * 70)
    print(f"  plan_steps    : {len(plan.steps)}")
    print(f"  llm_calls     : {metrics.llm_calls}  (= 1 plan + {len(plan.steps)} exec + 1 agg)")
    print(f"  input_tokens  : {metrics.input_tokens}")
    print(f"  output_tokens : {metrics.output_tokens}")
    print(f"  wall_clock    : {elapsed:.2f}s")
    print(f"  cost_usd      : ${metrics.cost_usd():.6f}")
