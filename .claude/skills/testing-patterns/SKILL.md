---
name: testing-patterns
description: Use when writing tests, debugging failing tests, designing test suites, or deciding what to test in Python code. Provides pytest patterns, fixture design, LLM output testing strategy, and coverage guidance for LangChain/LangGraph code.
---

# Testing Patterns (AgenticCourse)

## LLM output testing — test structure, not wording
```python
def test_resume_tailor_returns_required_sections(jd_fixture, resume_fixture):
    result = tailor_resume(jd_fixture, resume_fixture)
    assert "Experience" in result        # section exists
    assert len(result.split("\n")) > 10  # non-trivial content
    # Never: assert "Python" in result   — LLM wording is non-deterministic
```

## LangGraph graph testing — test input→output contract
```python
def test_farm_planner_produces_plan(mock_llm):
    state = {"profile": SAMPLE_PROFILE, "plan": None}
    result = graph.invoke(state)
    assert result["plan"] is not None
    assert "crop" in result["plan"]
```

## Fixture patterns
```python
@pytest.fixture
def sample_jd():
    return Path("tests/fixtures/software_engineer_jd.txt").read_text()

@pytest.fixture
def mock_llm(monkeypatch):
    monkeypatch.setattr("labs.module.llm", FakeLLM(response="test output"))
```

## Edge cases that always need a test
- Empty string / empty list input
- None input where not expected
- Single-item list (not just multi-item)
- Maximum length / boundary input

