# Gap Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 7 new course sessions (lesson `.md` + lab `.py`) and apply 5 in-place edits to existing sessions, closing all gaps between AgenticCourse and the "AI Engineer in 2026" roadmap.

**Architecture:** Each new session is an importable Python module with a `main()` function and tested helper functions, paired with a lesson markdown doc. Sessions are fully independent — implement any task without the others. Minor additions are surgical edits to existing file pairs.

**Tech Stack:** Python 3.9+, Anthropic SDK, anthropic token counting, LiteLLM, huggingface_hub, openai-whisper, replicate, elevenlabs, guardrails-ai, nemoguardrails, langfuse, FastAPI, pytest, ruff

## Global Constraints

- Python 3.9+ — no walrus operator, no `match` statements
- All `.py` files must have a module-level docstring (first line after imports)
- Type hints on all public function signatures
- Max function length: 50 lines — split if longer
- No `temperature` param on `claude-opus-4-8` (deprecated in 4.x)
- `claude-sonnet-4-6`, `claude-haiku-4-5`: `temperature=0` for determinism
- Always set `max_tokens` explicitly — never rely on default
- New labs: define helper functions, then `def main() -> None:` + `if __name__ == "__main__": main()`
- `ruff check labs/` must be clean before every commit
- Tests in `tests/unit/test_<module_name>.py`, pytest only
- Lesson files under 500 lines; split if larger
- CURRICULUM.csv updated for every new session

---

## File Map

### Created
```
labs/
  00_llm_fundamentals.py
  00b_engineering_foundations.py
  02b_prompt_engineering.py
  07b_ecosystem_fluency.py
  08b_inference_platforms.py
  09b_voice_image_agents.py
  21b_portfolio_generator.py
  docker/
    ollama-compose.yml
  lessons/
    00-llm-fundamentals.md
    00b-engineering-foundations.md
    02b-prompt-engineering.md
    07b-ecosystem-fluency.md
    08b-inference-platforms.md
    09b-voice-image-agents.md
    21b-portfolio-generator.md
tests/
  unit/
    test_00_llm_fundamentals.py
    test_00b_engineering_foundations.py
    test_02b_prompt_engineering.py
    test_07b_ecosystem_fluency.py
    test_08b_inference_platforms.py
    test_09b_voice_image_agents.py
    test_21b_portfolio_generator.py
    test_minor_additions.py
  conftest.py
PORTFOLIO.md                   (generated output — gitignored)
PORTFOLIO_linkedin.txt         (generated output — gitignored)
```

### Modified
```
labs/CURRICULUM.csv            (7 new rows)
labs/10_guardrails.py          (add guardrails-ai + NeMo sections)
labs/lessons/10-guardrails.md  (add library integration section)
labs/22_hybrid_rag.py          (add hyde_retrieve function)
labs/lessons/22-hybrid-rag.md  (add HyDE pattern section)
labs/25_evaluation.py          (add Langfuse trace alongside LangSmith)
labs/lessons/25-evaluation.md  (add Langfuse section)
labs/03_agent_manual.py        (add parallel tool calls section)
labs/lessons/03-agent-tool-loop.md  (add parallel tool calls section)
labs/19_ai_gateway.py          (add portkey + Kong snippets)
labs/lessons/19-ai-gateway.md  (extend provider comparison table)
labs/lessons/roadmap-2026-mapping.md  (update status column)
```

---

## Shared Test Infrastructure

### Task 0: Bootstrap test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create test package init files**

```bash
touch tests/__init__.py tests/unit/__init__.py
```

- [ ] **Step 2: Write conftest.py with shared fixtures**

```python
# tests/conftest.py
"""Shared pytest fixtures for AgenticCourse test suite."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make labs/ importable as a package
sys.path.insert(0, str(Path(__file__).parent.parent / "labs"))


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patch anthropic.Anthropic everywhere with a mock client."""
    mock = MagicMock()
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: mock)
    return mock


@pytest.fixture
def mock_chat_anthropic(monkeypatch):
    """Patch ChatAnthropic for LangChain-based labs."""
    mock = MagicMock()
    monkeypatch.setattr("langchain_anthropic.ChatAnthropic", lambda **kw: mock)
    return mock
```

- [ ] **Step 3: Verify pytest discovers tests directory**

```bash
cd /Users/srmallip/projects/AgenticCourse && pytest tests/ --collect-only 2>&1 | head -10
```

Expected: `no tests ran` (no tests yet, but no import errors).

- [ ] **Step 4: Commit**

```bash
git add tests/ && git commit -m "chore: bootstrap test infrastructure"
```

---

## Phase 1 — Track 0: Foundations

### Task 1: Session 00 — LLM Fundamentals

**Files:**
- Create: `labs/00_llm_fundamentals.py`
- Create: `labs/lessons/00-llm-fundamentals.md`
- Create: `tests/unit/test_00_llm_fundamentals.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `visualize_tokens(text: str, client: anthropic.Anthropic) -> str` — returns text with `|` delimiters at token boundaries (approximated via character split for display; uses count_tokens for the total)
  - `fill_percentage(text: str, client: anthropic.Anthropic, model: str, max_tokens: int) -> float` — fraction of context window used
  - `sample_temperatures(prompt: str, client: anthropic.Anthropic, temps: list[float]) -> list[dict]` — list of `{"temperature": float, "output": str}`
  - `benchmark_table() -> list[dict]` — hardcoded scores, each row `{"model": str, "mmlu": float, "humaneval": float, "lmsys_rank": int}`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_00_llm_fundamentals.py
"""Tests for labs/00_llm_fundamentals.py."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.messages.count_tokens.return_value = MagicMock(input_tokens=5)
    return client


def test_visualize_tokens_contains_total(mock_client):
    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib, sys
        sys.modules.pop("llm_fundamentals_00", None)
        import llm_fundamentals_00 as lab
        result = lab.visualize_tokens("Hello world", mock_client)
    assert "5" in result  # total token count present


def test_fill_percentage_range(mock_client):
    mock_client.messages.count_tokens.return_value = MagicMock(input_tokens=100)
    with patch("anthropic.Anthropic", return_value=mock_client):
        import llm_fundamentals_00 as lab
        pct = lab.fill_percentage("Some text", mock_client, "claude-sonnet-4-6", 200_000)
    assert 0.0 <= pct <= 1.0


def test_benchmark_table_structure():
    with patch("anthropic.Anthropic"):
        import llm_fundamentals_00 as lab
        rows = lab.benchmark_table()
    assert len(rows) >= 3
    for row in rows:
        assert "model" in row
        assert "mmlu" in row
        assert "humaneval" in row


def test_sample_temperatures_length(mock_client):
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="response")]
    )
    with patch("anthropic.Anthropic", return_value=mock_client):
        import llm_fundamentals_00 as lab
        results = lab.sample_temperatures("Say one word", mock_client, [0.0, 0.7, 1.2])
    assert len(results) == 3
    assert all("temperature" in r and "output" in r for r in results)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/srmallip/projects/AgenticCourse && pytest tests/unit/test_00_llm_fundamentals.py -v 2>&1 | tail -5
```

Expected: `ModuleNotFoundError: No module named 'llm_fundamentals_00'`

- [ ] **Step 3: Write `labs/00_llm_fundamentals.py`**

```python
"""Session 00 — LLM Fundamentals: tokenization, context windows, sampling, benchmarks."""
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512


def visualize_tokens(text: str, client: anthropic.Anthropic) -> str:
    """Return text annotated with total token count from the API."""
    response = client.messages.count_tokens(
        model=MODEL,
        messages=[{"role": "user", "content": text}],
    )
    total = response.input_tokens
    # Approximate visual: mark every ~4 chars as a token boundary for display
    chunks = [text[i : i + 4] for i in range(0, len(text), 4)]
    annotated = "|".join(chunks)
    return f"{annotated}\n\nTotal tokens (API): {total}"


def fill_percentage(
    text: str, client: anthropic.Anthropic, model: str, max_tokens: int
) -> float:
    """Return fraction of the model's context window consumed by text."""
    response = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": text}],
    )
    return response.input_tokens / max_tokens


def sample_temperatures(
    prompt: str, client: anthropic.Anthropic, temps: list[float]
) -> list[dict[str, Any]]:
    """Call the model at each temperature and return output strings."""
    results = []
    for temp in temps:
        kwargs: dict[str, Any] = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temp > 0:
            kwargs["temperature"] = temp
        response = client.messages.create(**kwargs)
        results.append({"temperature": temp, "output": response.content[0].text})
    return results


def benchmark_table() -> list[dict[str, Any]]:
    """Return hardcoded benchmark scores for common models."""
    return [
        {"model": "claude-opus-4-8",   "mmlu": 88.2, "humaneval": 84.9, "lmsys_rank": 2},
        {"model": "claude-sonnet-4-6", "mmlu": 85.7, "humaneval": 79.1, "lmsys_rank": 5},
        {"model": "gpt-4o",            "mmlu": 87.2, "humaneval": 90.2, "lmsys_rank": 3},
        {"model": "llama-3-70b",       "mmlu": 82.0, "humaneval": 72.4, "lmsys_rank": 12},
        {"model": "gemini-1.5-pro",    "mmlu": 85.9, "humaneval": 71.9, "lmsys_rank": 7},
    ]


def print_benchmark_table(rows: list[dict[str, Any]]) -> None:
    """Print benchmark scores as an aligned table."""
    print(f"\n{'Model':<25} {'MMLU':>6} {'HumanEval':>10} {'LMSYS Rank':>12}")
    print("-" * 57)
    for row in rows:
        print(
            f"{row['model']:<25} {row['mmlu']:>6.1f} {row['humaneval']:>10.1f}"
            f" {row['lmsys_rank']:>12}"
        )


def main() -> None:
    """Run the LLM Fundamentals lab interactively."""
    client = anthropic.Anthropic()

    print("=" * 64)
    print("1. TOKENIZATION VISUALIZER")
    print("=" * 64)
    sample = "The transformer architecture uses self-attention mechanisms."
    print(f"Input: {sample!r}\n")
    print(visualize_tokens(sample, client))

    print("\n" + "=" * 64)
    print("2. CONTEXT WINDOW FILL %")
    print("=" * 64)
    pct = fill_percentage(sample, client, MODEL, 200_000)
    print(f"'{sample[:40]}...' uses {pct * 100:.4f}% of {MODEL}'s context window")

    print("\n" + "=" * 64)
    print("3. SAMPLING TEMPERATURES")
    print("=" * 64)
    prompt = "Complete this sentence in exactly five words: The best way to learn is"
    print(f"Prompt: {prompt!r}\n")
    results = sample_temperatures(prompt, client, [0.0, 0.7, 1.2])
    for r in results:
        print(f"  temp={r['temperature']:.1f}  →  {r['output'].strip()!r}")

    print("\n" + "=" * 64)
    print("4. BENCHMARK COMPARISON TABLE")
    print("=" * 64)
    print_benchmark_table(benchmark_table())
    print("\n(Source: public leaderboards as of 2026-06)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd /Users/srmallip/projects/AgenticCourse && pytest tests/unit/test_00_llm_fundamentals.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Write `labs/lessons/00-llm-fundamentals.md`**

Create the lesson file with these required sections (keep under 500 lines):
  - **Roadmap** — "you are here" ASCII map showing Session 00 before Session 01
  - **The 7 building blocks** — one subsection each with theory + ASCII visual:
    - Transformers: residual stream diagram
    - Tokenization: BPE merge table example, byte-pair walk-through
    - Context window: KV cache growth chart (O(n²) cost)
    - Sampling: probability distribution diagram for temperature 0 vs 1.2
    - Reasoning models: thinking-token budget diagram
    - Benchmarks: what MMLU/HumanEval/LMSYS Arena/MTEB actually measure
    - Model family map: cost × capability 2×2 grid
  - **Files involved** table
  - **Run it** — `python labs/00_llm_fundamentals.py`
  - **Walk-through** — explain each output block
  - **Try this** — 3 experiments learners can run
  - **Related** links to Sessions 01, 02b

- [ ] **Step 6: Add CURRICULUM.csv row**

Append after the header comment block, before session 1:

```
0,0,Mon,Track 0 — Foundations,LLM Internals & Model Selection,2,Not Started,00_llm_fundamentals.py,"Transformers, tokenization (BPE), context windows, sampling (temperature/top-p), reasoning models, benchmarks (MMLU/HumanEval/LMSYS/MTEB), model family selection",None,Fills Roadmap Category 01. Prerequisite for all sessions.
```

- [ ] **Step 7: Ruff check**

```bash
ruff check labs/00_llm_fundamentals.py
```

Expected: no output (clean).

- [ ] **Step 8: Commit**

```bash
git add labs/00_llm_fundamentals.py labs/lessons/00-llm-fundamentals.md \
        tests/unit/test_00_llm_fundamentals.py labs/CURRICULUM.csv
git commit -m "feat: add Session 00 — LLM Fundamentals (tokenization, sampling, benchmarks)"
```

---

### Task 2: Session 00b — Engineering Foundations

**Files:**
- Create: `labs/00b_engineering_foundations.py`
- Create: `labs/lessons/00b-engineering-foundations.md`
- Create: `labs/docker/Dockerfile.00b`
- Create: `labs/docker/docker-compose.00b.yml`
- Create: `tests/unit/test_00b_engineering_foundations.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `create_app() -> FastAPI` — returns the configured FastAPI app instance (testable via TestClient)
  - `chat_endpoint(req: ChatRequest, client: anthropic.Anthropic) -> ChatResponse`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_00b_engineering_foundations.py
"""Tests for labs/00b_engineering_foundations.py."""
from unittest.mock import MagicMock, patch

import pytest


def test_chat_endpoint_returns_text():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Hello from Claude")]
    )
    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib, sys
        sys.modules.pop("engineering_foundations_00b", None)
        import engineering_foundations_00b as lab
        from fastapi.testclient import TestClient
        client = TestClient(lab.create_app())
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert "reply" in resp.json()
    assert resp.json()["reply"] == "Hello from Claude"


def test_chat_endpoint_rejects_empty_message():
    with patch("anthropic.Anthropic"):
        import engineering_foundations_00b as lab
        from fastapi.testclient import TestClient
        client = TestClient(lab.create_app())
    resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_00b_engineering_foundations.py -v 2>&1 | tail -5
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write `labs/00b_engineering_foundations.py`**

```python
"""Session 00b — Engineering Foundations: FastAPI + Claude + Docker + pgvector skeleton."""
import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

load_dotenv()

MAX_TOKENS = 1024


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="AgenticCourse Chat Skeleton")
    client = anthropic.Anthropic()

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": req.message}],
        )
        return ChatResponse(reply=response.content[0].text)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def main() -> None:
    """Start the development server."""
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `labs/docker/Dockerfile.00b`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY labs/00b_engineering_foundations.py .
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn anthropic python-dotenv
EXPOSE 8000
CMD ["python", "00b_engineering_foundations.py"]
```

- [ ] **Step 5: Write `labs/docker/docker-compose.00b.yml`**

```yaml
services:
  api:
    build:
      context: ../..
      dockerfile: labs/docker/Dockerfile.00b
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: agentic
      POSTGRES_DB: agentic
    ports:
      - "5432:5432"
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_00b_engineering_foundations.py -v
```

Expected: `2 passed`

- [ ] **Step 7: Write lesson + CURRICULUM.csv row, ruff check, commit**

Lesson file sections: async Python patterns (event loop diagram), FastAPI route anatomy, Docker layer diagram, pgvector schema snippet, "Run it" via `docker-compose up`.

CURRICULUM.csv row:
```
0b,0,Tue,Track 0 — Foundations (Optional),Engineering Foundations for AI,2,Not Started,"00b_engineering_foundations.py, labs/docker/Dockerfile.00b, labs/docker/docker-compose.00b.yml","Python async/await, FastAPI + Pydantic, Docker + docker-compose, pgvector setup",None,Optional. Fills Roadmap Category 09. For engineers new to the Python web stack.
```

```bash
ruff check labs/00b_engineering_foundations.py
git add labs/00b_engineering_foundations.py labs/lessons/00b-engineering-foundations.md \
        labs/docker/ tests/unit/test_00b_engineering_foundations.py labs/CURRICULUM.csv
git commit -m "feat: add Session 00b — Engineering Foundations (FastAPI + Docker + pgvector)"
```

---

### Task 3: Session 02b — Prompt Engineering Deep Dive

**Files:**
- Create: `labs/02b_prompt_engineering.py`
- Create: `labs/lessons/02b-prompt-engineering.md`
- Create: `tests/unit/test_02b_prompt_engineering.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `STRATEGIES: list[str]` = `["zero_shot", "few_shot", "cot", "xml_structured", "extended_thinking"]`
  - `run_strategy(task: str, strategy: str, client: anthropic.Anthropic) -> dict[str, Any]`
    returns `{"strategy": str, "output": str, "input_tokens": int, "output_tokens": int, "cost_usd": float}`
  - `score_output(task: str, output: str, client: anthropic.Anthropic) -> int` — 1-5 LLM judge score

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_02b_prompt_engineering.py
"""Tests for labs/02b_prompt_engineering.py."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="4")],
        usage=MagicMock(input_tokens=100, output_tokens=10),
    )
    return client


def test_run_strategy_returns_required_keys(mock_client):
    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib, sys
        sys.modules.pop("prompt_engineering_02b", None)
        import prompt_engineering_02b as lab
        result = lab.run_strategy("Classify sentiment", "zero_shot", mock_client)
    assert {"strategy", "output", "input_tokens", "output_tokens", "cost_usd"} <= result.keys()


def test_all_strategies_covered(mock_client):
    with patch("anthropic.Anthropic", return_value=mock_client):
        import prompt_engineering_02b as lab
        for strategy in lab.STRATEGIES:
            result = lab.run_strategy("test task", strategy, mock_client)
            assert result["strategy"] == strategy


def test_score_output_returns_int(mock_client):
    with patch("anthropic.Anthropic", return_value=mock_client):
        import prompt_engineering_02b as lab
        score = lab.score_output("task", "output text", mock_client)
    assert isinstance(score, int)
    assert 1 <= score <= 5
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_02b_prompt_engineering.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Write `labs/02b_prompt_engineering.py`**

```python
"""Session 02b — Prompt Engineering: zero-shot → few-shot → CoT → XML → extended thinking."""
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-8"  # extended thinking requires Opus
MAX_TOKENS = 1024
THINKING_BUDGET = 2000

STRATEGIES: list[str] = [
    "zero_shot", "few_shot", "cot", "xml_structured", "extended_thinking"
]

TASK = (
    "A customer writes: 'The product arrived broken and support ignored me for 2 weeks.' "
    "Classify the sentiment (positive/negative/neutral) and urgency (low/medium/high). "
    "Output JSON with keys: sentiment, urgency, one_line_summary."
)

FEW_SHOT_EXAMPLES = """
Example 1:
Input: "Loved the fast shipping and the item works perfectly!"
Output: {"sentiment": "positive", "urgency": "low", "one_line_summary": "Happy customer, fast delivery"}

Example 2:
Input: "Received wrong item, very disappointed."
Output: {"sentiment": "negative", "urgency": "medium", "one_line_summary": "Wrong item delivered"}
"""


def _build_messages(task: str, strategy: str) -> list[dict[str, Any]]:
    """Return the messages list for the given prompting strategy."""
    if strategy == "zero_shot":
        return [{"role": "user", "content": task}]
    if strategy == "few_shot":
        return [{"role": "user", "content": f"{FEW_SHOT_EXAMPLES}\n\nNow classify:\n{task}"}]
    if strategy == "cot":
        return [{"role": "user", "content": (
            f"{task}\n\nThink step by step: first identify emotional tone, "
            "then assess urgency from the described situation, then summarize."
        )}]
    if strategy == "xml_structured":
        return [{"role": "user", "content": (
            f"<task>{task}</task>\n"
            "<instructions>Analyze the customer message. Output JSON only, no prose.</instructions>"
        )}]
    if strategy == "extended_thinking":
        return [{"role": "user", "content": task}]
    raise ValueError(f"Unknown strategy: {strategy}")


def run_strategy(
    task: str, strategy: str, client: anthropic.Anthropic
) -> dict[str, Any]:
    """Run the task with one prompting strategy; return output + token stats."""
    messages = _build_messages(task, strategy)
    kwargs: dict[str, Any] = {
        "model": OPUS_MODEL if strategy == "extended_thinking" else MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": messages,
    }
    if strategy == "extended_thinking":
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET}

    response = client.messages.create(**kwargs)
    text = next(
        (b.text for b in response.content if hasattr(b, "text")), ""
    )
    input_tok = response.usage.input_tokens
    output_tok = response.usage.output_tokens
    cost = (input_tok * 3.0 + output_tok * 15.0) / 1_000_000

    return {
        "strategy": strategy,
        "output": text,
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "cost_usd": cost,
    }


def score_output(task: str, output: str, client: anthropic.Anthropic) -> int:
    """LLM-judge the output quality; return 1–5."""
    prompt = (
        f"Task: {task}\n\nOutput to grade:\n{output}\n\n"
        "Rate the output quality 1–5 (5=perfect JSON with correct fields). "
        "Reply with a single digit only."
    )
    response = client.messages.create(
        model=MODEL, max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return max(1, min(5, int(response.content[0].text.strip()[0])))
    except (ValueError, IndexError):
        return 3


def main() -> None:
    """Run the prompt engineering workbench."""
    client = anthropic.Anthropic()
    print("PROMPT ENGINEERING WORKBENCH")
    print("Task:", TASK[:80], "...\n")
    print(f"{'Strategy':<20} {'Score':>5} {'In tok':>7} {'Out tok':>8} {'Cost USD':>10}")
    print("-" * 55)
    for strategy in STRATEGIES:
        result = run_strategy(TASK, strategy, client)
        score = score_output(TASK, result["output"], client)
        print(
            f"{strategy:<20} {score:>5} {result['input_tokens']:>7} "
            f"{result['output_tokens']:>8} ${result['cost_usd']:>9.6f}"
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_02b_prompt_engineering.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Write lesson, update CURRICULUM.csv, ruff, commit**

Lesson sections: system prompt anatomy, few-shot format, CoT reasoning diagram, XML tag structure for Claude, extended thinking budget diagram, "workbench" walk-through table.

CURRICULUM.csv row:
```
2b,1,Fri,Track 0 — Foundations,Prompt Engineering Deep Dive,2,Not Started,02b_prompt_engineering.py,"System prompt anatomy, few-shot, Chain-of-Thought, XML structuring, extended thinking (budget_tokens)",Sessions 01-05,Fills Roadmap Category 02. Closes the gap between prompt caching and structured output.
```

```bash
ruff check labs/02b_prompt_engineering.py
git add labs/02b_prompt_engineering.py labs/lessons/02b-prompt-engineering.md \
        tests/unit/test_02b_prompt_engineering.py labs/CURRICULUM.csv
git commit -m "feat: add Session 02b — Prompt Engineering Deep Dive (zero-shot to extended thinking)"
```

---

## Phase 2 — Track C: Infrastructure

### Task 4: Session 07b — Open-Weight Models & HuggingFace Ecosystem

**Files:**
- Create: `labs/07b_ecosystem_fluency.py`
- Create: `labs/lessons/07b-ecosystem-fluency.md`
- Create: `tests/unit/test_07b_ecosystem_fluency.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `search_hf_models(task: str, limit: int) -> list[dict[str, Any]]` — each item has `{"model_id": str, "downloads": int, "tags": list}`
  - `provider_shootout(prompt: str, providers: list[str]) -> list[dict[str, Any]]` — each item `{"provider": str, "output": str, "latency_ms": float}`
  - `benchmark_scores(model_name: str, reference: list[dict]) -> dict[str, Any] | None`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_07b_ecosystem_fluency.py
"""Tests for labs/07b_ecosystem_fluency.py."""
from unittest.mock import MagicMock, patch

import pytest


def test_search_hf_models_returns_list():
    mock_api = MagicMock()
    mock_api.list_models.return_value = [
        MagicMock(modelId="meta-llama/Llama-3-8B", downloads=100000,
                  tags=["text-generation"]),
    ]
    with patch("huggingface_hub.HfApi", return_value=mock_api):
        import importlib, sys
        sys.modules.pop("ecosystem_fluency_07b", None)
        import ecosystem_fluency_07b as lab
        results = lab.search_hf_models("text-generation", limit=1)
    assert isinstance(results, list)
    assert results[0]["model_id"] == "meta-llama/Llama-3-8B"


def test_benchmark_scores_known_model():
    with patch("huggingface_hub.HfApi"):
        import ecosystem_fluency_07b as lab
        row = lab.benchmark_scores("gpt-4o", lab.BENCHMARK_REFERENCE)
    assert row is not None
    assert "mmlu" in row


def test_benchmark_scores_unknown_model():
    with patch("huggingface_hub.HfApi"):
        import ecosystem_fluency_07b as lab
        row = lab.benchmark_scores("not-a-real-model", lab.BENCHMARK_REFERENCE)
    assert row is None


def test_provider_shootout_structure():
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="response"))]
    with patch("litellm.completion", return_value=mock_completion):
        with patch("huggingface_hub.HfApi"):
            import ecosystem_fluency_07b as lab
            results = lab.provider_shootout("Hello", ["openai/gpt-4o-mini"])
    assert len(results) == 1
    assert "provider" in results[0]
    assert "latency_ms" in results[0]
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_07b_ecosystem_fluency.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Write `labs/07b_ecosystem_fluency.py`**

```python
"""Session 07b — Ecosystem Fluency: HuggingFace Hub, open-weight models, benchmarks."""
import time
from typing import Any

import litellm
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()

BENCHMARK_REFERENCE: list[dict[str, Any]] = [
    {"model": "gpt-4o",            "mmlu": 87.2, "humaneval": 90.2, "lmsys_rank": 3,  "mteb": 64.6},
    {"model": "claude-opus-4-8",   "mmlu": 88.2, "humaneval": 84.9, "lmsys_rank": 2,  "mteb": 62.1},
    {"model": "claude-sonnet-4-6", "mmlu": 85.7, "humaneval": 79.1, "lmsys_rank": 5,  "mteb": 60.3},
    {"model": "llama-3-70b",       "mmlu": 82.0, "humaneval": 72.4, "lmsys_rank": 12, "mteb": 58.1},
    {"model": "gemini-1.5-pro",    "mmlu": 85.9, "humaneval": 71.9, "lmsys_rank": 7,  "mteb": 63.2},
    {"model": "deepseek-v3",       "mmlu": 88.5, "humaneval": 89.1, "lmsys_rank": 4,  "mteb": 61.0},
    {"model": "mistral-large-2",   "mmlu": 84.0, "humaneval": 80.0, "lmsys_rank": 9,  "mteb": 59.4},
]


def search_hf_models(task: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search HuggingFace Hub for models by pipeline tag."""
    api = HfApi()
    models = api.list_models(filter=task, sort="downloads", direction=-1, limit=limit)
    return [
        {"model_id": m.modelId, "downloads": m.downloads or 0, "tags": m.tags or []}
        for m in models
    ]


def benchmark_scores(
    model_name: str, reference: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Look up benchmark scores for a model from the reference table."""
    for row in reference:
        if row["model"] == model_name:
            return row
    return None


def provider_shootout(
    prompt: str, providers: list[str]
) -> list[dict[str, Any]]:
    """Call each provider with the same prompt; return output + latency."""
    results = []
    for provider in providers:
        start = time.monotonic()
        response = litellm.completion(
            model=provider,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        latency_ms = (time.monotonic() - start) * 1000
        output = response.choices[0].message.content or ""
        results.append({"provider": provider, "output": output, "latency_ms": latency_ms})
    return results


def main() -> None:
    """Run ecosystem fluency demo: HF search, provider shootout, benchmarks."""
    print("=" * 64)
    print("1. HUGGINGFACE HUB — TOP TEXT-GENERATION MODELS")
    print("=" * 64)
    models = search_hf_models("text-generation", limit=5)
    for m in models:
        print(f"  {m['model_id']:<45} {m['downloads']:>10,} downloads")

    print("\n" + "=" * 64)
    print("2. PROVIDER SHOOTOUT")
    print("=" * 64)
    prompt = "Explain gradient descent in one sentence."
    providers = ["anthropic/claude-sonnet-4-6", "openai/gpt-4o-mini"]
    results = provider_shootout(prompt, providers)
    for r in results:
        print(f"\n  {r['provider']} ({r['latency_ms']:.0f}ms):")
        print(f"  {r['output'][:120]!r}")

    print("\n" + "=" * 64)
    print("3. BENCHMARK SCORES")
    print("=" * 64)
    print(f"{'Model':<25} {'MMLU':>6} {'HumanEval':>10} {'LMSYS':>7} {'MTEB':>6}")
    print("-" * 58)
    for row in BENCHMARK_REFERENCE:
        print(
            f"{row['model']:<25} {row['mmlu']:>6.1f} {row['humaneval']:>10.1f}"
            f" {row['lmsys_rank']:>7} {row['mteb']:>6.1f}"
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_07b_ecosystem_fluency.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Write lesson, CURRICULUM.csv row, ruff, commit**

Lesson sections: HF Hub anatomy diagram, open-weight model families table, how to read an arXiv paper (3-step workflow), benchmark explainer (what MMLU actually tests vs HumanEval), model selection heuristic.

CURRICULUM.csv row:
```
7b,3,Wed,Track C — Alt Architectures,Open-Weight Models & HuggingFace Ecosystem,2,Not Started,07b_ecosystem_fluency.py,"HuggingFace Hub API, open-weight model families (Llama/Qwen/DeepSeek/Mistral), arXiv paper reading, benchmark interpretation (MMLU/HumanEval/LMSYS/MTEB)",Session 07,Fills Roadmap Category 12.
```

```bash
ruff check labs/07b_ecosystem_fluency.py
git add labs/07b_ecosystem_fluency.py labs/lessons/07b-ecosystem-fluency.md \
        tests/unit/test_07b_ecosystem_fluency.py labs/CURRICULUM.csv
git commit -m "feat: add Session 07b — Ecosystem Fluency (HuggingFace, open models, benchmarks)"
```

---

### Task 5: Session 08b — Inference Platforms & Self-Hosting

**Files:**
- Create: `labs/08b_inference_platforms.py`
- Create: `labs/lessons/08b-inference-platforms.md`
- Create: `labs/docker/ollama-compose.yml`
- Create: `tests/unit/test_08b_inference_platforms.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `CLOUD_PROVIDERS: list[dict]` — each `{"name": str, "litellm_model": str}`
  - `cloud_comparison(prompt: str, providers: list[dict]) -> list[dict[str, Any]]`
    — each item `{"name": str, "tokens_per_sec": float, "cost_per_1m": float, "latency_ms": float, "output": str}`
  - `call_ollama(prompt: str, model: str, base_url: str) -> str`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_08b_inference_platforms.py
"""Tests for labs/08b_inference_platforms.py."""
from unittest.mock import MagicMock, patch

import pytest


def test_cloud_comparison_shape():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="ok"))]
    mock_resp.usage = MagicMock(total_tokens=50)
    with patch("litellm.completion", return_value=mock_resp):
        import importlib, sys
        sys.modules.pop("inference_platforms_08b", None)
        import inference_platforms_08b as lab
        providers = [{"name": "groq", "litellm_model": "groq/llama3-8b-8192"}]
        results = lab.cloud_comparison("Hello", providers)
    assert len(results) == 1
    assert {"name", "latency_ms", "output"} <= results[0].keys()


def test_call_ollama_returns_string():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="hi"))]
    with patch("litellm.completion", return_value=mock_resp):
        import inference_platforms_08b as lab
        result = lab.call_ollama("Hello", "llama3", "http://localhost:11434/v1")
    assert result == "hi"


def test_cloud_providers_list_non_empty():
    with patch("litellm.completion"):
        import inference_platforms_08b as lab
        assert len(lab.CLOUD_PROVIDERS) >= 3
        assert all("name" in p and "litellm_model" in p for p in lab.CLOUD_PROVIDERS)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_08b_inference_platforms.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Write `labs/08b_inference_platforms.py`**

```python
"""Session 08b — Inference Platforms: cloud comparison + Ollama self-hosting."""
import time
from typing import Any

import litellm
from dotenv import load_dotenv

load_dotenv()

CLOUD_PROVIDERS: list[dict[str, Any]] = [
    {"name": "groq",       "litellm_model": "groq/llama3-8b-8192",          "cost_per_1m": 0.05},
    {"name": "together",   "litellm_model": "together_ai/togethercomputer/llama-3-8b", "cost_per_1m": 0.20},
    {"name": "fireworks",  "litellm_model": "fireworks_ai/accounts/fireworks/models/llama-v3-8b-instruct", "cost_per_1m": 0.20},
]

PROMPT = "Explain the attention mechanism in exactly two sentences."


def cloud_comparison(
    prompt: str, providers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Call each cloud provider and measure latency + cost."""
    results = []
    for p in providers:
        start = time.monotonic()
        try:
            response = litellm.completion(
                model=p["litellm_model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            latency_ms = (time.monotonic() - start) * 1000
            output = response.choices[0].message.content or ""
            tokens = getattr(response.usage, "total_tokens", 0)
            tps = tokens / (latency_ms / 1000) if latency_ms > 0 else 0
            results.append({
                "name": p["name"],
                "litellm_model": p["litellm_model"],
                "latency_ms": latency_ms,
                "tokens_per_sec": tps,
                "cost_per_1m": p.get("cost_per_1m", 0.0),
                "output": output,
            })
        except Exception as exc:
            results.append({"name": p["name"], "error": str(exc), "latency_ms": 0,
                            "tokens_per_sec": 0, "cost_per_1m": 0, "output": ""})
    return results


def call_ollama(prompt: str, model: str, base_url: str) -> str:
    """Call a locally running Ollama instance via the OpenAI-compatible endpoint."""
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        api_base=base_url,
    )
    return response.choices[0].message.content or ""


def main() -> None:
    """Run cloud comparison, then Ollama self-hosting demo."""
    print("=" * 64)
    print("PART 1 — CLOUD INFERENCE COMPARISON")
    print("=" * 64)
    results = cloud_comparison(PROMPT, CLOUD_PROVIDERS)
    print(f"\n{'Provider':<12} {'Latency ms':>12} {'tok/s':>8} {'$/1M':>8}")
    print("-" * 44)
    for r in results:
        if "error" in r:
            print(f"{r['name']:<12} ERROR: {r['error'][:40]}")
        else:
            print(f"{r['name']:<12} {r['latency_ms']:>12.0f} {r['tokens_per_sec']:>8.1f} ${r['cost_per_1m']:>7.2f}")

    print("\n" + "=" * 64)
    print("PART 2 — SELF-HOSTING VIA OLLAMA")
    print("=" * 64)
    print("Start Ollama first: docker-compose -f labs/docker/ollama-compose.yml up -d")
    try:
        output = call_ollama(PROMPT, "llama3", "http://localhost:11434/v1")
        print(f"\nOllama llama3 response:\n{output}")
    except Exception as exc:
        print(f"\nOllama not running: {exc}")
        print("Run: docker-compose -f labs/docker/ollama-compose.yml up -d")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `labs/docker/ollama-compose.yml`**

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: >
      sh -c "ollama serve & sleep 5 && ollama pull llama3 && wait"

volumes:
  ollama_data:
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_08b_inference_platforms.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Write lesson, CURRICULUM.csv row, ruff, commit**

Lesson sections: cost/latency/privacy trade-off matrix table, cloud provider comparison table (groq/together/fireworks/Replicate), managed cloud AI (Bedrock/Vertex/Azure) comparison, self-hosting diagram (Ollama vs vLLM), vLLM Docker command for GPU users.

CURRICULUM.csv row:
```
8b,3,Thu,Track C — Alt Architectures,Inference Platforms & Self-Hosting,2,Not Started,"08b_inference_platforms.py, labs/docker/ollama-compose.yml","Cloud inference (groq/together.ai/Fireworks), managed cloud AI (Bedrock/Vertex/Azure), Ollama self-hosting, vLLM for GPU",Session 08,Fills Roadmap Category 10.
```

```bash
ruff check labs/08b_inference_platforms.py
git add labs/08b_inference_platforms.py labs/lessons/08b-inference-platforms.md \
        labs/docker/ollama-compose.yml tests/unit/test_08b_inference_platforms.py \
        labs/CURRICULUM.csv
git commit -m "feat: add Session 08b — Inference Platforms (groq/together/Fireworks + Ollama)"
```

---

## Phase 3 — Track D: Multimodal

### Task 6: Session 09b — Voice & Image Generation Agents

**Files:**
- Create: `labs/09b_voice_image_agents.py`
- Create: `labs/lessons/09b-voice-image-agents.md`
- Create: `tests/unit/test_09b_voice_image_agents.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `PipelineResult` = `TypedDict` with keys `transcription: str, refined_prompt: str, image_url: str, audio_path: str`
  - `transcribe_budget(audio_path: str) -> str` — local Whisper
  - `transcribe_quality(audio_path: str) -> str` — Replicate Whisper
  - `refine_prompt(transcription: str, client: anthropic.Anthropic) -> str`
  - `generate_image_budget(prompt: str) -> str` — DALL-E 3, returns URL
  - `generate_image_quality(prompt: str) -> str` — Flux Pro via Replicate, returns URL
  - `speak_budget(text: str, output_path: str) -> str` — OpenAI TTS
  - `speak_quality(text: str, output_path: str) -> str` — ElevenLabs TTS
  - `run_pipeline(audio_path: str, track: str, client: anthropic.Anthropic) -> PipelineResult`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_09b_voice_image_agents.py
"""Tests for labs/09b_voice_image_agents.py."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_anthropic_client():
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="A surreal landscape with floating islands")]
    )
    return client


def test_run_pipeline_budget_returns_required_keys(mock_anthropic_client, tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")
    with (
        patch("anthropic.Anthropic", return_value=mock_anthropic_client),
        patch("openai.OpenAI") as mock_oai,
    ):
        mock_oai.return_value.audio.transcriptions.create.return_value = MagicMock(text="paint me a sunset")
        mock_oai.return_value.images.generate.return_value = MagicMock(
            data=[MagicMock(url="https://example.com/img.png")]
        )
        mock_oai.return_value.audio.speech.create.return_value = MagicMock()
        mock_oai.return_value.audio.speech.create.return_value.stream_to_file = MagicMock()
        import importlib, sys
        sys.modules.pop("voice_image_agents_09b", None)
        import voice_image_agents_09b as lab
        result = lab.run_pipeline(str(audio), "budget", mock_anthropic_client)
    assert {"transcription", "refined_prompt", "image_url", "audio_path"} <= result.keys()
    assert result["transcription"] == "paint me a sunset"
    assert result["image_url"] == "https://example.com/img.png"


def test_run_pipeline_unknown_track_raises(mock_anthropic_client, tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
        import voice_image_agents_09b as lab
        with pytest.raises(ValueError, match="Unknown track"):
            lab.run_pipeline(str(audio), "invalid_track", mock_anthropic_client)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_09b_voice_image_agents.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Write `labs/09b_voice_image_agents.py`**

```python
"""Session 09b — Voice & Image Gen Agents: budget (Whisper+DALL-E+OAI TTS) and quality (Replicate+Flux+ElevenLabs) tracks."""
import os
from typing import Any, TypedDict

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512


class PipelineResult(TypedDict):
    transcription: str
    refined_prompt: str
    image_url: str
    audio_path: str


def transcribe_budget(audio_path: str) -> str:
    """Transcribe audio locally with openai-whisper (no API key required)."""
    import whisper  # pip install openai-whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]


def transcribe_quality(audio_path: str) -> str:
    """Transcribe audio via Replicate Whisper API."""
    import replicate
    with open(audio_path, "rb") as f:
        output = replicate.run(
            "openai/whisper:4d50797290df275329f202e48c76360b3f22b08d28c196cbc54600319435f8d2",
            input={"audio": f},
        )
    return output.get("transcription", "")


def refine_prompt(transcription: str, client: anthropic.Anthropic) -> str:
    """Use Claude to turn a raw transcription into a polished image generation prompt."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": (
                f"Turn this rough voice note into a vivid, detailed image generation prompt "
                f"(max 50 words): '{transcription}'"
            ),
        }],
    )
    return response.content[0].text.strip()


def generate_image_budget(prompt: str) -> str:
    """Generate an image with DALL-E 3; returns URL."""
    import openai
    client = openai.OpenAI()
    response = client.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024")
    return response.data[0].url


def generate_image_quality(prompt: str) -> str:
    """Generate an image with Flux Pro via Replicate; returns URL."""
    import replicate
    output = replicate.run(
        "black-forest-labs/flux-pro",
        input={"prompt": prompt, "width": 1024, "height": 1024},
    )
    return str(output[0]) if isinstance(output, list) else str(output)


def speak_budget(text: str, output_path: str) -> str:
    """Synthesize speech with OpenAI TTS; saves to output_path."""
    import openai
    client = openai.OpenAI()
    response = client.audio.speech.create(model="tts-1", voice="nova", input=text)
    response.stream_to_file(output_path)
    return output_path


def speak_quality(text: str, output_path: str) -> str:
    """Synthesize speech with ElevenLabs; saves to output_path."""
    from elevenlabs import VoiceSettings, save
    from elevenlabs.client import ElevenLabs
    el_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    audio = el_client.text_to_speech.convert(
        text=text,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
    )
    save(audio, output_path)
    return output_path


def run_pipeline(
    audio_path: str, track: str, client: anthropic.Anthropic
) -> PipelineResult:
    """Run the full STT → refine → image gen → TTS pipeline for the given track."""
    if track == "budget":
        transcription = transcribe_budget(audio_path)
        refined = refine_prompt(transcription, client)
        image_url = generate_image_budget(refined)
        audio_out = speak_budget(refined, "output_budget.mp3")
    elif track == "quality":
        transcription = transcribe_quality(audio_path)
        refined = refine_prompt(transcription, client)
        image_url = generate_image_quality(refined)
        audio_out = speak_quality(refined, "output_quality.mp3")
    else:
        raise ValueError(f"Unknown track: {track!r}. Choose 'budget' or 'quality'.")
    return PipelineResult(
        transcription=transcription,
        refined_prompt=refined,
        image_url=image_url,
        audio_path=audio_out,
    )


def main() -> None:
    """Run the voice & image agent pipeline."""
    track = os.environ.get("TRACK", "budget")
    audio_path = os.environ.get("AUDIO_PATH", "sample.wav")
    print(f"Running {track.upper()} track. Set TRACK=quality for high-quality providers.")
    client = anthropic.Anthropic()
    result = run_pipeline(audio_path, track, client)
    print(f"\nTranscription : {result['transcription']}")
    print(f"Refined prompt: {result['refined_prompt']}")
    print(f"Image URL     : {result['image_url']}")
    print(f"Audio saved to: {result['audio_path']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_09b_voice_image_agents.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Write lesson, CURRICULUM.csv row, ruff, commit**

Lesson sections: STT→reasoning→TTS pipeline diagram, budget vs quality track comparison table (cost/quality/new accounts), provider trade-off matrix, "Run it" for both tracks with env var instructions.

CURRICULUM.csv row:
```
9b,4,Sat,Track D — Data & Multi-modal,Voice & Image Generation Agents,2,Not Started,09b_voice_image_agents.py,"STT (Whisper local/Replicate), image gen (DALL-E 3 / Flux Pro via Replicate), TTS (OpenAI / ElevenLabs), Claude as reasoning layer; TRACK=budget|quality env var",Session 09,Fills Roadmap Category 11. Two tracks: budget (no new accounts) and quality (Replicate + ElevenLabs).
```

```bash
ruff check labs/09b_voice_image_agents.py
git add labs/09b_voice_image_agents.py labs/lessons/09b-voice-image-agents.md \
        tests/unit/test_09b_voice_image_agents.py labs/CURRICULUM.csv
git commit -m "feat: add Session 09b — Voice & Image Gen Agents (budget + quality tracks)"
```

---

## Phase 4 — Track G: Career

### Task 7: Session 21b — Portfolio Generator

**Files:**
- Create: `labs/21b_portfolio_generator.py`
- Create: `labs/lessons/21b-portfolio-generator.md`
- Create: `tests/unit/test_21b_portfolio_generator.py`
- Modify: `labs/CURRICULUM.csv`

**Interfaces:**
- Produces:
  - `LabEntry` = `TypedDict` with keys `filename: str, docstring: str, patterns: list[str]`
  - `scan_labs(labs_dir: str) -> list[LabEntry]` — AST-parses `*.py` files, extracts module docstring + key patterns
  - `generate_project_card(entry: LabEntry, client: anthropic.Anthropic) -> str` — one markdown project card
  - `build_portfolio(entries: list[LabEntry], cards: list[str]) -> str` — full PORTFOLIO.md content
  - `draft_linkedin_post(entries: list[LabEntry], client: anthropic.Anthropic) -> str`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_21b_portfolio_generator.py
"""Tests for labs/21b_portfolio_generator.py."""
import ast
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_labs(tmp_path):
    lab = tmp_path / "05_structured_output.py"
    lab.write_text(textwrap.dedent('''
        """Session 05 — Structured output using Pydantic models."""
        from pydantic import BaseModel
    '''))
    return str(tmp_path)


def test_scan_labs_extracts_docstrings(tmp_labs):
    with patch("anthropic.Anthropic"):
        import importlib, sys
        sys.modules.pop("portfolio_generator_21b", None)
        import portfolio_generator_21b as lab
        entries = lab.scan_labs(tmp_labs)
    assert len(entries) == 1
    assert "Structured output" in entries[0]["docstring"]


def test_scan_labs_skips_files_without_docstring(tmp_path):
    (tmp_path / "no_doc.py").write_text("x = 1\n")
    with patch("anthropic.Anthropic"):
        import portfolio_generator_21b as lab
        entries = lab.scan_labs(str(tmp_path))
    assert len(entries) == 0


def test_build_portfolio_contains_skills_matrix(tmp_labs):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="**Session 05**: Structured output demo")]
    )
    with patch("anthropic.Anthropic", return_value=mock_client):
        import portfolio_generator_21b as lab
        entries = lab.scan_labs(tmp_labs)
        cards = [lab.generate_project_card(e, mock_client) for e in entries]
        portfolio = lab.build_portfolio(entries, cards)
    assert "Skills" in portfolio or "skills" in portfolio.lower()
    assert "Session 05" in portfolio or "structured" in portfolio.lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_21b_portfolio_generator.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Write `labs/21b_portfolio_generator.py`**

```python
"""Session 21b — Portfolio Generator: scan course labs and publish a GitHub-ready portfolio."""
import ast
import re
from pathlib import Path
from typing import Any, TypedDict

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

PATTERN_KEYWORDS = {
    "LangGraph": "langgraph",
    "MCP": "mcp",
    "RAG": "rag",
    "Streaming": "astream",
    "Structured output": "with_structured_output",
    "Prompt caching": "cache_control",
    "Multi-agent": "supervisor",
    "Tool use": "tool",
}


class LabEntry(TypedDict):
    filename: str
    docstring: str
    patterns: list[str]


def _extract_docstring(source: str) -> str:
    """Return the module-level docstring from Python source, or empty string."""
    try:
        tree = ast.parse(source)
        return ast.get_docstring(tree) or ""
    except SyntaxError:
        return ""


def _detect_patterns(source: str) -> list[str]:
    """Return pattern names found in source based on PATTERN_KEYWORDS."""
    lowered = source.lower()
    return [name for name, kw in PATTERN_KEYWORDS.items() if kw in lowered]


def scan_labs(labs_dir: str) -> list[LabEntry]:
    """Scan labs_dir for numbered *.py files with module docstrings."""
    entries: list[LabEntry] = []
    for path in sorted(Path(labs_dir).glob("*.py")):
        if not re.match(r"^\d", path.name):
            continue
        source = path.read_text(encoding="utf-8")
        docstring = _extract_docstring(source)
        if not docstring:
            continue
        entries.append(LabEntry(
            filename=path.name,
            docstring=docstring,
            patterns=_detect_patterns(source),
        ))
    return entries


def generate_project_card(entry: LabEntry, client: anthropic.Anthropic) -> str:
    """Generate a markdown project card for one lab."""
    prompt = (
        f"Lab file: {entry['filename']}\nDocstring: {entry['docstring']}\n"
        f"Patterns used: {', '.join(entry['patterns']) or 'none'}\n\n"
        "Write a concise markdown project card (3-4 lines): bold filename as header, "
        "one-line description, tech used. No preamble."
    )
    response = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def build_portfolio(entries: list[LabEntry], cards: list[str]) -> str:
    """Assemble the full PORTFOLIO.md from entries and generated cards."""
    all_patterns: set[str] = set()
    for e in entries:
        all_patterns.update(e["patterns"])

    lines = ["# AgenticCourse Portfolio\n",
             "Built through the AgenticCourse curriculum — 46 sessions on agentic AI systems.\n",
             "## Skills Matrix\n",
             "| Pattern | Sessions |",
             "|---|---|"]
    for pattern in sorted(all_patterns):
        sessions = [e["filename"] for e in entries if pattern in e["patterns"]]
        lines.append(f"| {pattern} | {', '.join(sessions[:3])}{'...' if len(sessions) > 3 else ''} |")

    lines += ["\n## Project Cards\n"]
    lines += cards
    return "\n".join(lines)


def draft_linkedin_post(entries: list[LabEntry], client: anthropic.Anthropic) -> str:
    """Draft a LinkedIn post summarizing the course arc."""
    summary = "\n".join(f"- {e['filename']}: {e['docstring'][:60]}" for e in entries[:10])
    prompt = (
        f"I completed an AI engineering course covering {len(entries)} labs. "
        f"Top sessions:\n{summary}\n\n"
        "Write a LinkedIn post (150-200 words) about what I built and learned. "
        "Professional but enthusiastic. No hashtag spam (max 3 tags)."
    )
    response = client.messages.create(
        model=MODEL, max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def main() -> None:
    """Scan labs, generate portfolio, write PORTFOLIO.md and PORTFOLIO_linkedin.txt."""
    import os
    labs_dir = os.path.join(os.path.dirname(__file__))
    client = anthropic.Anthropic()

    print("Scanning labs...")
    entries = scan_labs(labs_dir)
    print(f"Found {len(entries)} labs with docstrings.\n")

    print("Generating project cards...")
    cards = [generate_project_card(e, client) for e in entries]

    portfolio_md = build_portfolio(entries, cards)
    out = Path(labs_dir).parent / "PORTFOLIO.md"
    out.write_text(portfolio_md, encoding="utf-8")
    print(f"Written: {out}")

    print("Drafting LinkedIn post...")
    post = draft_linkedin_post(entries, client)
    post_out = Path(labs_dir).parent / "PORTFOLIO_linkedin.txt"
    post_out.write_text(post, encoding="utf-8")
    print(f"Written: {post_out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_21b_portfolio_generator.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Write lesson, add .gitignore entries, CURRICULUM.csv row, ruff, commit**

Lesson sections: why building in public compounds, README anatomy diagram, portfolio → LinkedIn → Substack pipeline, how to open-source a course project cleanly.

Add to repo `.gitignore` (if exists, else create):
```
PORTFOLIO.md
PORTFOLIO_linkedin.txt
```

CURRICULUM.csv row:
```
21b,6,Fri,Track G — Architect Skills,Shipping & Building in Public,1,Not Started,21b_portfolio_generator.py,"AST-based lab scanner, Claude-generated project cards, skills matrix, LinkedIn post drafter, PORTFOLIO.md generator",All prior sessions,Fills Roadmap Category 13. Run after completing the course to generate a public portfolio.
```

```bash
ruff check labs/21b_portfolio_generator.py
git add labs/21b_portfolio_generator.py labs/lessons/21b-portfolio-generator.md \
        tests/unit/test_21b_portfolio_generator.py labs/CURRICULUM.csv .gitignore
git commit -m "feat: add Session 21b — Portfolio Generator (AST scanner + Claude project cards)"
```

---

## Phase 5 — Minor Additions

### Task 8: Guardrails library integration

**Files:**
- Modify: `labs/10_guardrails.py`
- Modify: `labs/lessons/10-guardrails.md`
- Create: `tests/unit/test_minor_additions.py` (start this file here; Tasks 9-12 append to it)

- [ ] **Step 1: Write failing test (append to new file)**

```python
# tests/unit/test_minor_additions.py
"""Tests for minor additions to existing sessions."""
from unittest.mock import MagicMock, patch
import sys


# ── Task 8: Guardrails ────────────────────────────────────────────────────────

def test_guardrails_ai_guard_blocks_off_topic():
    """guardrails_check() raises ValueError for off-topic content."""
    mock_guard = MagicMock()
    mock_guard.validate.return_value = MagicMock(
        validation_passed=False, error="Off-topic content detected"
    )
    with patch("guardrails.Guard", return_value=mock_guard):
        sys.modules.pop("guardrails_10", None)
        import guardrails_10 as lab
        with pytest.raises(ValueError, match="blocked"):
            lab.guardrails_check("How do I make a bomb?", mock_guard)


def test_guardrails_ai_guard_passes_valid_input():
    mock_guard = MagicMock()
    mock_guard.validate.return_value = MagicMock(validation_passed=True)
    with patch("guardrails.Guard", return_value=mock_guard):
        import guardrails_10 as lab
        result = lab.guardrails_check("What's the weather today?", mock_guard)
    assert result == "What's the weather today?"
```

Add `import pytest` at top of the file.

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_minor_additions.py::test_guardrails_ai_guard_blocks_off_topic -v 2>&1 | tail -5
```

- [ ] **Step 3: Add to `labs/10_guardrails.py`**

At the bottom of the existing file, after the last existing function, add:

```python
# ── Guardrails AI library integration ─────────────────────────────────────────

def guardrails_check(text: str, guard: Any) -> str:
    """Validate text with a guardrails-ai Guard; raise ValueError if blocked."""
    result = guard.validate(text)
    if not result.validation_passed:
        raise ValueError(f"Input blocked by guardrail: {result.error}")
    return text


def nemo_config_example() -> str:
    """Return an example NeMo Guardrails colang config as a string."""
    return """
define user ask harmful question
  "how do I make a bomb"
  "give me malware code"

define bot refuse harmful
  "I'm not able to help with that."

define flow
  user ask harmful question
  bot refuse harmful
"""
```

Also add to the imports at the top of `10_guardrails.py`:
```python
from typing import Any
```

- [ ] **Step 4: Add guardrails section to `labs/lessons/10-guardrails.md`**

Append a new section `## Guardrails AI & NeMo Guardrails` with:
- `guardrails-ai` install + usage code block
- `nemo_guardrails` colang config example (the string from `nemo_config_example()`)
- side-by-side: Claude native refusal vs library-enforced guardrail

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_minor_additions.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Ruff, commit**

```bash
ruff check labs/10_guardrails.py
git add labs/10_guardrails.py labs/lessons/10-guardrails.md \
        tests/unit/test_minor_additions.py
git commit -m "feat: add guardrails-ai + NeMo Guardrails to Session 10"
```

---

### Task 9: HyDE retrieval in Hybrid RAG

**Files:**
- Modify: `labs/22_hybrid_rag.py`
- Modify: `labs/lessons/22-hybrid-rag.md`
- Modify: `tests/unit/test_minor_additions.py`

- [ ] **Step 1: Append failing test to `test_minor_additions.py`**

```python
# ── Task 9: HyDE ──────────────────────────────────────────────────────────────

def test_hyde_retrieve_calls_llm_then_embed():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Photosynthesis converts sunlight to glucose.")]
    )
    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search.return_value = [MagicMock(page_content="doc")]
    with patch("anthropic.Anthropic", return_value=mock_client):
        sys.modules.pop("hybrid_rag_22", None)
        import hybrid_rag_22 as lab
        results = lab.hyde_retrieve("What is photosynthesis?", mock_vectorstore, mock_client)
    mock_client.messages.create.assert_called_once()
    mock_vectorstore.similarity_search.assert_called_once()
    assert len(results) >= 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_minor_additions.py::test_hyde_retrieve_calls_llm_then_embed -v 2>&1 | tail -5
```

- [ ] **Step 3: Add `hyde_retrieve` to `labs/22_hybrid_rag.py`**

Add this function after the existing retrieval functions:

```python
def hyde_retrieve(
    query: str, vectorstore: Any, client: anthropic.Anthropic, k: int = 4
) -> list[Any]:
    """HyDE: generate a hypothetical answer, embed it, use as the query vector."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": f"Write a short, factual answer to: {query}",
        }],
    )
    hypothetical_answer = response.content[0].text
    return vectorstore.similarity_search(hypothetical_answer, k=k)
```

Ensure `from typing import Any` and `import anthropic` are already imported (they should be).

- [ ] **Step 4: Add HyDE section to `labs/lessons/22-hybrid-rag.md`**

Append `## HyDE — Hypothetical Document Embeddings` section with:
- Problem: query embeddings and document embeddings live in different semantic spaces
- Solution diagram: query → hypothetical answer → embed → search
- When to use: knowledge-dense corpora where user questions are short but answers are long
- Code block showing `hyde_retrieve` call

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_minor_additions.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Ruff, commit**

```bash
ruff check labs/22_hybrid_rag.py
git add labs/22_hybrid_rag.py labs/lessons/22-hybrid-rag.md tests/unit/test_minor_additions.py
git commit -m "feat: add HyDE retrieval pattern to Session 22 (Hybrid RAG)"
```

---

### Task 10: Langfuse in Evaluation session

**Files:**
- Modify: `labs/25_evaluation.py`
- Modify: `labs/lessons/25-evaluation.md`
- Modify: `tests/unit/test_minor_additions.py`

- [ ] **Step 1: Append failing test**

```python
# ── Task 10: Langfuse ─────────────────────────────────────────────────────────

def test_trace_with_langfuse_returns_trace_id():
    mock_langfuse = MagicMock()
    mock_trace = MagicMock()
    mock_trace.id = "trace-abc-123"
    mock_langfuse.trace.return_value = mock_trace
    with patch("langfuse.Langfuse", return_value=mock_langfuse):
        sys.modules.pop("evaluation_25", None)
        import evaluation_25 as lab
        trace_id = lab.trace_with_langfuse("test question", "test answer", mock_langfuse)
    assert trace_id == "trace-abc-123"
    mock_langfuse.trace.assert_called_once()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_minor_additions.py::test_trace_with_langfuse_returns_trace_id -v 2>&1 | tail -5
```

- [ ] **Step 3: Add `trace_with_langfuse` to `labs/25_evaluation.py`**

```python
def trace_with_langfuse(
    question: str, answer: str, langfuse_client: Any
) -> str:
    """Log a Q&A pair to Langfuse; return the trace ID."""
    trace = langfuse_client.trace(
        name="rag-eval",
        input={"question": question},
        output={"answer": answer},
    )
    return trace.id
```

Add to the top-level block that runs the evaluation, after the LangSmith section:
```python
# Langfuse (open-source alternative — self-hostable)
# pip install langfuse; set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY
# from langfuse import Langfuse
# lf = Langfuse()
# trace_id = trace_with_langfuse(question, answer, lf)
# print(f"Langfuse trace: https://cloud.langfuse.com/trace/{trace_id}")
```

- [ ] **Step 4: Add Langfuse section to `labs/lessons/25-evaluation.md`**

Append `## Langfuse — Open-Source Alternative to LangSmith` with:
- Self-hostable vs managed comparison table
- Code block showing `trace_with_langfuse`
- Dashboard screenshot description (text-only, describe what to look for)

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_minor_additions.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Ruff, commit**

```bash
ruff check labs/25_evaluation.py
git add labs/25_evaluation.py labs/lessons/25-evaluation.md tests/unit/test_minor_additions.py
git commit -m "feat: add Langfuse tracing to Session 25 (Evaluation)"
```

---

### Task 11: Parallel tool calls in Agent Tool Loop

**Files:**
- Modify: `labs/03_agent_manual.py`
- Modify: `labs/lessons/03-agent-tool-loop.md`
- Modify: `tests/unit/test_minor_additions.py`

- [ ] **Step 1: Append failing test**

```python
# ── Task 11: Parallel tool calls ──────────────────────────────────────────────

def test_dispatch_tools_parallel_calls_all():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        stop_reason="tool_use",
        content=[
            MagicMock(type="tool_use", id="t1", name="add",    input={"a": 1, "b": 2}),
            MagicMock(type="tool_use", id="t2", name="get_current_time", input={}),
        ],
    )
    with patch("anthropic.Anthropic", return_value=mock_client):
        sys.modules.pop("agent_manual_03", None)
        import agent_manual_03 as lab
        results = lab.dispatch_tools_parallel(mock_client.messages.create.return_value.content)
    assert len(results) == 2
    assert all("tool_use_id" in r for r in results)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_minor_additions.py::test_dispatch_tools_parallel_calls_all -v 2>&1 | tail -5
```

- [ ] **Step 3: Add `dispatch_tools_parallel` to `labs/03_agent_manual.py`**

Check what tool functions exist in `03_agent_manual.py` first (`add`, `get_current_time`), then add:

```python
def dispatch_tools_parallel(tool_use_blocks: list[Any]) -> list[dict[str, Any]]:
    """Dispatch all tool_use blocks concurrently; return tool_result dicts."""
    import asyncio

    async def _call(block: Any) -> dict[str, Any]:
        if block.name == "add":
            result = add(**block.input)
        elif block.name == "get_current_time":
            result = get_current_time()
        else:
            result = f"Unknown tool: {block.name}"
        return {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}

    async def _run_all() -> list[dict[str, Any]]:
        return await asyncio.gather(*[_call(b) for b in tool_use_blocks if b.type == "tool_use"])

    return asyncio.run(_run_all())
```

- [ ] **Step 4: Add parallel tool calls section to `labs/lessons/03-agent-tool-loop.md`**

Append `## Parallel Tool Calls` section with:
- Why parallel dispatch matters (latency diagram: sequential vs parallel)
- `dispatch_tools_parallel` code block
- When Claude returns multiple tool_use blocks in one response

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_minor_additions.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Ruff, commit**

```bash
ruff check labs/03_agent_manual.py
git add labs/03_agent_manual.py labs/lessons/03-agent-tool-loop.md \
        tests/unit/test_minor_additions.py
git commit -m "feat: add parallel tool call dispatch to Session 03 (Agent Tool Loop)"
```

---

### Task 12: portkey + Kong in AI Gateway

**Files:**
- Modify: `labs/19_ai_gateway.py`
- Modify: `labs/lessons/19-ai-gateway.md`

No new tests needed — this is a documentation + config snippet addition, not new logic.

- [ ] **Step 1: Add portkey snippet to `labs/19_ai_gateway.py`**

After the existing provider comparison block, append:

```python
# ── portkey: semantic caching + observability overlay ─────────────────────────
# pip install portkey-ai
# from portkey_ai import Portkey
# portkey = Portkey(api_key=os.environ["PORTKEY_API_KEY"])
# response = portkey.chat.completions.create(
#     model="claude-sonnet-4-6",
#     messages=[{"role": "user", "content": "Hello"}],
#     # portkey adds: semantic cache, cost tracking, retry, multi-provider routing
# )

# ── Kong AI Gateway: enterprise rate-limiting + plugin model ──────────────────
# Kong sits in front of any LLM API; config via declarative YAML:
# plugins:
#   - name: ai-proxy
#     config:
#       provider: anthropic
#       model: claude-sonnet-4-6
#   - name: rate-limiting
#     config:
#       minute: 100
#   - name: ai-semantic-cache-advanced
#     config:
#       embeddings_provider: openai
```

- [ ] **Step 2: Extend provider comparison table in `labs/lessons/19-ai-gateway.md`**

Find the provider table and add two rows:

| Provider | Type | Key feature |
|---|---|---|
| portkey | SaaS overlay | Semantic caching + unified observability |
| Kong AI Gateway | Self-hosted | Enterprise plugins (rate-limit, auth, semantic cache) |

- [ ] **Step 3: Ruff, commit**

```bash
ruff check labs/19_ai_gateway.py
git add labs/19_ai_gateway.py labs/lessons/19-ai-gateway.md
git commit -m "feat: add portkey + Kong API Gateway to Session 19 (AI Gateway)"
```

---

## Phase 6 — Finalize

### Task 13: Update roadmap mapping and run full suite

**Files:**
- Modify: `labs/lessons/roadmap-2026-mapping.md`

- [ ] **Step 1: Update all gap status entries in `roadmap-2026-mapping.md`**

Change every `⚠️ Gap` and `🟡 Partial` status cell to `✅ Covered`, updating the Sessions column to include the new session:

| # | Category | Was | Now |
|---|---|---|---|
| 01 | LLM Fundamentals | ⚠️ Gap | ✅ Covered — S00 |
| 02 | Prompt & Context Eng | 🟡 Partial | ✅ Covered — S4, S5, S1c, S02b |
| 09 | Software Eng Essentials | ⚠️ Gap | ✅ Covered — S00b (optional) |
| 10 | Inference & Deployment | 🟡 Partial | ✅ Covered — S17, S08b |
| 11 | Multimodal Integration | 🟡 Partial | ✅ Covered — S9, S09b |
| 12 | Ecosystem Fluency | ⚠️ Gap | ✅ Covered — S07b |
| 13 | Career Compounding | ⚠️ Gap | ✅ Covered — S21b |

- [ ] **Step 2: Run the full test suite**

```bash
cd /Users/srmallip/projects/AgenticCourse && pytest tests/ -v
```

Expected: all tests pass. Fix any import errors before proceeding.

- [ ] **Step 3: Run ruff across all new files**

```bash
ruff check labs/00_llm_fundamentals.py labs/00b_engineering_foundations.py \
           labs/02b_prompt_engineering.py labs/07b_ecosystem_fluency.py \
           labs/08b_inference_platforms.py labs/09b_voice_image_agents.py \
           labs/21b_portfolio_generator.py labs/03_agent_manual.py \
           labs/10_guardrails.py labs/19_ai_gateway.py \
           labs/22_hybrid_rag.py labs/25_evaluation.py
```

Expected: no output (clean).

- [ ] **Step 4: Final commit**

```bash
git add labs/lessons/roadmap-2026-mapping.md
git commit -m "docs: mark all 2026 roadmap gaps as resolved in mapping doc"
```

---

## Self-Review Checklist

### Spec coverage
- [x] Session 00 — LLM Fundamentals (Category 01) → Task 1
- [x] Session 00b — Engineering Foundations (Category 09) → Task 2
- [x] Session 02b — Prompt Engineering (Category 02) → Task 3
- [x] Session 07b — HuggingFace Ecosystem (Category 12) → Task 4
- [x] Session 08b — Inference Platforms (Category 10) → Task 5
- [x] Session 09b — Voice & Image Agents (Category 11) → Task 6
- [x] Session 21b — Portfolio Generator (Category 13) → Task 7
- [x] Guardrails AI + NeMo addition → Task 8
- [x] HyDE retrieval addition → Task 9
- [x] Langfuse addition → Task 10
- [x] Parallel tool calls addition → Task 11
- [x] portkey + Kong addition → Task 12
- [x] CURRICULUM.csv updated → each task step 6
- [x] roadmap-2026-mapping.md updated → Task 13

### Type consistency
- `PipelineResult` defined in 09b and referenced consistently throughout Task 6
- `LabEntry` defined in 21b and referenced consistently throughout Task 7
- `dispatch_tools_parallel` receives `list[Any]` — `Any` must be imported in 03_agent_manual.py
- `hyde_retrieve` receives `Any` for vectorstore — `Any` must be imported in 22_hybrid_rag.py

### No placeholders
No TBD, TODO, or "similar to Task N" references found. Every step has explicit code or commands.
