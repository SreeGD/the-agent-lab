"""Spec-Driven Development (SDD) — the rigorous workflow pattern.

Given a vague intent, this agent produces FOUR typed artifacts in order:

    INTENT  ──►  Spec  ──►  TaskList  ──►  Code  ──►  VerificationReport

Each phase uses `model.with_structured_output(...)` so the artifacts are
typed Pydantic objects, not free-form text. Phase gates enforce ordering —
you can't implement before tasks; you can't task before spec. Verification
at the end checks the implementation against the original acceptance criteria.

This is the opposite of vibe coding (Session 5) — slow start, dramatically
better outcomes for non-trivial work because every assumption is captured.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "claude-sonnet-4-6"
model = ChatAnthropic(model=MODEL, temperature=0)

HERE = Path(__file__).parent
GENERATED_FILE = HERE / "generated_wordcount.py"


# =====================================================================
# Typed artifacts — one Pydantic model per phase output
# =====================================================================

class AcceptanceCriterion(BaseModel):
    """One testable statement that must be true of the final artifact."""
    description: str = Field(description="Concrete, testable statement, e.g. 'CLI accepts --top N flag'")
    testable: bool = Field(description="Can this be mechanically verified?")


class Spec(BaseModel):
    """Phase 1 artifact: the specification document."""
    title: str
    description: str = Field(description="One-paragraph plain-English description of what's being built")
    inputs: list[str] = Field(description="What the user/system provides")
    outputs: list[str] = Field(description="What the artifact produces")
    functional_requirements: list[str] = Field(description="What the artifact MUST do")
    non_functional_requirements: list[str] = Field(
        description="Performance, error handling, code style requirements"
    )
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        description="Testable statements; the final artifact must satisfy ALL of these"
    )
    out_of_scope: list[str] = Field(description="What this artifact intentionally does NOT do")


class Task(BaseModel):
    """One subtask in the implementation plan."""
    description: str = Field(description="Imperative voice — 'Parse CLI args', 'Read input file'")
    done_when: str = Field(description="Concrete completion criterion for THIS task")


class TaskList(BaseModel):
    """Phase 2 artifact: ordered implementation plan."""
    tasks: list[Task] = Field(description="3-8 ordered subtasks that collectively satisfy the spec")


class Implementation(BaseModel):
    """Phase 3 artifact: the generated code."""
    code: str = Field(description="Complete, runnable Python program matching the spec")
    rationale: str = Field(description="One paragraph explaining design choices")


class CriterionResult(BaseModel):
    """Per-criterion verification outcome."""
    criterion: str = Field(description="The acceptance criterion being checked")
    passed: bool = Field(description="True if the implementation satisfies this criterion")
    evidence: str = Field(description="Quote from code or reasoning supporting the verdict")


class VerificationReport(BaseModel):
    """Phase 4 artifact: final verification of the implementation against the spec."""
    overall_passed: bool = Field(description="True only if ALL criteria passed")
    criterion_results: list[CriterionResult]
    notes: str = Field(description="Brief summary or follow-up actions")


# =====================================================================
# Phase prompts — one per phase
# =====================================================================

spec_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior software engineer practicing Spec-Driven Development. "
     "Given a vague user intent, produce a precise, complete specification. "
     "Make implicit assumptions EXPLICIT. Pick sensible defaults for "
     "ambiguous points and document them. Every acceptance criterion must be "
     "mechanically testable (a human could write a unit test for it)."),
    ("human",
     "User intent: {intent}\n\n"
     "Produce a complete Spec. Be specific. Pick reasonable defaults for "
     "ambiguities (case sensitivity, punctuation handling, file encoding, "
     "etc.) and list them as functional requirements. Aim for 4-7 acceptance "
     "criteria."),
])

task_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior engineer decomposing a spec into implementable tasks. "
     "Produce 3-8 ORDERED tasks. Each task should be focused (one concrete "
     "thing). The order should support sequential implementation — earlier "
     "tasks set up state that later tasks use. Each task's done_when must be "
     "concrete and verifiable."),
    ("human",
     "Spec:\n{spec_json}\n\n"
     "Produce the TaskList."),
])

implement_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior Python engineer. Given a spec and a task list, "
     "produce a single complete, runnable Python program that satisfies "
     "the spec. The program should:\n"
     "  - Use only standard library (no third-party deps)\n"
     "  - Include a `__main__` block\n"
     "  - Be production-quality: type hints, clear naming, edge-case handling\n"
     "  - Include a brief module-level docstring\n"
     "Match the architecture suggested by the task list."),
    ("human",
     "Spec:\n{spec_json}\n\n"
     "TaskList:\n{tasks_json}\n\n"
     "Generate the implementation. Return the complete Python source as the "
     "`code` field and a brief rationale."),
])

verify_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an objective code reviewer verifying an implementation against "
     "a spec. For each acceptance criterion, decide whether the implementation "
     "satisfies it. Cite a specific line/function from the code as evidence. "
     "Pass only if you can point to concrete evidence in the code. "
     "Mark overall_passed=true ONLY if all criteria pass."),
    ("human",
     "Spec:\n{spec_json}\n\n"
     "Implementation:\n```python\n{code}\n```\n\n"
     "Verify each acceptance criterion against the code. Return the typed "
     "VerificationReport."),
])

# Phases as Runnables — include_raw=True so we can grab usage_metadata
spec_phase = spec_prompt | model.with_structured_output(Spec, include_raw=True)
task_phase = task_prompt | model.with_structured_output(TaskList, include_raw=True)
impl_phase = implement_prompt | model.with_structured_output(Implementation, include_raw=True)
verify_phase = verify_prompt | model.with_structured_output(VerificationReport, include_raw=True)


# =====================================================================
# Metrics
# =====================================================================

@dataclass
class PhaseMetrics:
    name: str
    in_tok: int = 0
    out_tok: int = 0
    elapsed: float = 0.0

    @property
    def cost_usd(self) -> float:
        return (self.in_tok * 3 + self.out_tok * 15) / 1_000_000


@dataclass
class Run:
    phases: list[PhaseMetrics] = field(default_factory=list)

    def add(self, p: PhaseMetrics) -> None:
        self.phases.append(p)

    @property
    def total_in(self) -> int:
        return sum(p.in_tok for p in self.phases)

    @property
    def total_out(self) -> int:
        return sum(p.out_tok for p in self.phases)

    @property
    def total_cost(self) -> float:
        return sum(p.cost_usd for p in self.phases)

    @property
    def total_elapsed(self) -> float:
        return sum(p.elapsed for p in self.phases)


def absorb(name: str, raw: AIMessage, elapsed: float) -> PhaseMetrics:
    m = PhaseMetrics(name=name, elapsed=elapsed)
    if raw and raw.usage_metadata:
        m.in_tok = raw.usage_metadata.get("input_tokens", 0)
        m.out_tok = raw.usage_metadata.get("output_tokens", 0)
    return m


# =====================================================================
# The pipeline — phases run in order with explicit gates
# =====================================================================

INTENT = (
    "Build a Python CLI tool that counts word occurrences in a text file "
    "and prints the top N most common words."
)


def run_sdd(intent: str) -> tuple[Spec, TaskList, Implementation, VerificationReport, Run]:
    run = Run()

    # --- PHASE 1: CLARIFY ---
    print("\n" + "=" * 70)
    print("PHASE 1: CLARIFY  →  produce a Spec")
    print("=" * 70)
    t0 = time.perf_counter()
    result = spec_phase.invoke({"intent": intent})
    elapsed = time.perf_counter() - t0
    spec: Spec = result["parsed"]
    run.add(absorb("clarify", result["raw"], elapsed))

    print(f"\nTitle: {spec.title}")
    print(f"Description: {spec.description}")
    print(f"\nInputs:")
    for x in spec.inputs:
        print(f"  • {x}")
    print(f"\nOutputs:")
    for x in spec.outputs:
        print(f"  • {x}")
    print(f"\nAcceptance criteria ({len(spec.acceptance_criteria)}):")
    for c in spec.acceptance_criteria:
        print(f"  ✓ {c.description}")

    # --- PHASE 2: DECOMPOSE ---
    print("\n" + "=" * 70)
    print("PHASE 2: DECOMPOSE  →  produce a TaskList")
    print("=" * 70)
    t0 = time.perf_counter()
    result = task_phase.invoke({"spec_json": spec.model_dump_json()})
    elapsed = time.perf_counter() - t0
    tasks: TaskList = result["parsed"]
    run.add(absorb("decompose", result["raw"], elapsed))

    print(f"\nGenerated {len(tasks.tasks)} tasks:")
    for i, t in enumerate(tasks.tasks, 1):
        print(f"  {i}. {t.description}")
        print(f"     done when: {t.done_when}")

    # --- PHASE 3: IMPLEMENT ---
    print("\n" + "=" * 70)
    print("PHASE 3: IMPLEMENT  →  generate the Code")
    print("=" * 70)
    t0 = time.perf_counter()
    result = impl_phase.invoke({
        "spec_json": spec.model_dump_json(),
        "tasks_json": tasks.model_dump_json(),
    })
    elapsed = time.perf_counter() - t0
    impl: Implementation = result["parsed"]
    run.add(absorb("implement", result["raw"], elapsed))

    GENERATED_FILE.write_text(impl.code)
    print(f"\nWrote {len(impl.code)} chars to {GENERATED_FILE.name}")
    print(f"\nRationale: {impl.rationale}")
    print(f"\nCode preview (first 600 chars):")
    print(impl.code[:600])
    print("..." if len(impl.code) > 600 else "")

    # --- PHASE 4: VERIFY ---
    print("\n" + "=" * 70)
    print("PHASE 4: VERIFY  →  produce a VerificationReport")
    print("=" * 70)
    t0 = time.perf_counter()
    result = verify_phase.invoke({
        "spec_json": spec.model_dump_json(),
        "code": impl.code,
    })
    elapsed = time.perf_counter() - t0
    report: VerificationReport = result["parsed"]
    run.add(absorb("verify", result["raw"], elapsed))

    print(f"\nOverall: {'✅ PASS' if report.overall_passed else '❌ FAIL'}")
    print(f"\nPer-criterion verdicts:")
    for r in report.criterion_results:
        mark = "✓" if r.passed else "✗"
        print(f"  {mark} {r.criterion}")
        print(f"     evidence: {r.evidence[:150]}{'...' if len(r.evidence) > 150 else ''}")
    print(f"\nNotes: {report.notes}")

    return spec, tasks, impl, report, run


# =====================================================================
# Run + report
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SPEC-DRIVEN DEVELOPMENT (SDD) — Sessions 4")
    print("=" * 70)
    print(f"INTENT: {INTENT}")

    spec, tasks, impl, report, run = run_sdd(INTENT)

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'phase':<12} {'in':>6} {'out':>6} {'time':>6} {'cost':>10}")
    print("-" * 50)
    for p in run.phases:
        print(f"{p.name:<12} {p.in_tok:>6} {p.out_tok:>6} {p.elapsed:>5.1f}s ${p.cost_usd:>9.6f}")
    print("-" * 50)
    print(f"{'TOTAL':<12} {run.total_in:>6} {run.total_out:>6} "
          f"{run.total_elapsed:>5.1f}s ${run.total_cost:>9.6f}")

    print(f"\nArtifacts:")
    print(f"  📄 generated_wordcount.py — {len(impl.code)} chars")
    print(f"  📋 spec — {len(spec.acceptance_criteria)} acceptance criteria")
    print(f"  📋 tasks — {len(tasks.tasks)} subtasks")
    print(f"  ✅ verification — overall_passed={report.overall_passed}")
    print(f"\n  Run the generated tool:  python {GENERATED_FILE.name} --file NOTES.md --top 5")
