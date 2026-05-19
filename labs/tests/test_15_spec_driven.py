"""Unit tests for SDD — the Pydantic schemas that gate each phase.

These tests verify that the typed artifacts (Spec, TaskList, Implementation,
VerificationReport) reject malformed inputs at the boundary and accept
well-formed ones. The actual LLM calls in SDD are out of scope here.
"""

from typing import Literal

import pytest
from pydantic import BaseModel, Field, ValidationError


# Replicate the Pydantic schemas from 15_spec_driven.py — keep imports cheap.
# (Importing the lab file would also import langchain + anthropic at module load.)

class AcceptanceCriterion(BaseModel):
    description: str = Field(description="Concrete, testable statement")
    testable: bool


class Spec(BaseModel):
    title: str
    description: str
    inputs: list[str]
    outputs: list[str]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    out_of_scope: list[str]


class Task(BaseModel):
    description: str
    done_when: str


class TaskList(BaseModel):
    tasks: list[Task]


class Implementation(BaseModel):
    code: str
    rationale: str


class CriterionResult(BaseModel):
    criterion: str
    passed: bool
    evidence: str


class VerificationReport(BaseModel):
    overall_passed: bool
    criterion_results: list[CriterionResult]
    notes: str


# ─── Spec validation ──────────────────────────────────────────────────

class TestSpec:
    def test_well_formed_spec(self):
        spec = Spec(
            title="Word counter",
            description="Counts words.",
            inputs=["file path"],
            outputs=["top-N table"],
            functional_requirements=["accept CLI args"],
            non_functional_requirements=["stream-process for large files"],
            acceptance_criteria=[
                AcceptanceCriterion(description="exits 0 on success", testable=True),
            ],
            out_of_scope=["multi-language support"],
        )
        assert spec.title == "Word counter"
        assert len(spec.acceptance_criteria) == 1

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Spec(title="Missing fields")  # type: ignore[call-arg]

    def test_acceptance_criteria_must_be_list(self):
        with pytest.raises(ValidationError):
            Spec(
                title="x", description="x",
                inputs=[], outputs=[],
                functional_requirements=[], non_functional_requirements=[],
                acceptance_criteria="not-a-list",  # type: ignore[arg-type]
                out_of_scope=[],
            )


# ─── TaskList validation ──────────────────────────────────────────────

class TestTaskList:
    def test_well_formed(self):
        tasks = TaskList(tasks=[
            Task(description="parse args", done_when="argparse runs"),
            Task(description="read file", done_when="file is read"),
        ])
        assert len(tasks.tasks) == 2

    def test_empty_list_is_valid(self):
        # An empty TaskList is valid — the planner may decide nothing needs to be done
        tasks = TaskList(tasks=[])
        assert tasks.tasks == []


# ─── Task ─────────────────────────────────────────────────────────────

class TestTask:
    def test_both_fields_required(self):
        with pytest.raises(ValidationError):
            Task(description="only description")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            Task(done_when="only done_when")  # type: ignore[call-arg]


# ─── VerificationReport ───────────────────────────────────────────────

class TestVerificationReport:
    def test_all_pass_report(self):
        report = VerificationReport(
            overall_passed=True,
            criterion_results=[
                CriterionResult(criterion="exits 0", passed=True, evidence="sys.exit(0) at line 30"),
                CriterionResult(criterion="handles --top", passed=True, evidence="argparse with --top"),
            ],
            notes="All good.",
        )
        assert report.overall_passed
        assert all(r.passed for r in report.criterion_results)

    def test_mixed_results(self):
        report = VerificationReport(
            overall_passed=False,
            criterion_results=[
                CriterionResult(criterion="A", passed=True, evidence="..."),
                CriterionResult(criterion="B", passed=False, evidence="missing"),
            ],
            notes="One criterion failed.",
        )
        assert not report.overall_passed
        passed = [r for r in report.criterion_results if r.passed]
        failed = [r for r in report.criterion_results if not r.passed]
        assert len(passed) == 1 and len(failed) == 1
