# OpenAI + Ollama Lesson Variants — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create fully standalone OpenAI (`gpt-4o`) and Ollama (`llama3.2`) variants for all 30 provider-agnostic lessons in AgenticCourse.

**Architecture:** Each variant is a complete, self-contained file — no imports from the Anthropic original. Code files live in `labs/openai/` and `labs/ollama/`; lesson docs live in `labs/lessons/openai/` and `labs/lessons/ollama/`. Existing files are untouched.

**Tech Stack:** Python, LangChain (`langchain_openai`, `langchain_ollama`), OpenAI SDK (`openai`), LiteLLM, LangGraph, LangChain HuggingFace embeddings.

---

## Provider swap reference

Every code file uses one or more of these substitutions. Memorize this table — it's referenced in every task below.

| What | Anthropic original | OpenAI variant | Ollama variant |
|---|---|---|---|
| LangChain import | `from langchain_anthropic import ChatAnthropic` | `from langchain_openai import ChatOpenAI` | `from langchain_ollama import ChatOllama` |
| LangChain class | `ChatAnthropic(` | `ChatOpenAI(` | `ChatOllama(` |
| Main model string | `"claude-sonnet-4-6"` | `"gpt-4o"` | `"llama3.2"` |
| Small/judge model | `"claude-haiku-4-5-20251001"` | `"gpt-4o-mini"` | `"llama3.2"` |
| Raw SDK import | `import anthropic` | `import openai` | `import openai` (Ollama is OpenAI-compatible) |
| Raw client init | `anthropic.Anthropic()` | `openai.OpenAI()` | `openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")` |
| Raw completion call | `client.messages.create(model=M, max_tokens=N, messages=[...])` | `client.chat.completions.create(model=M, max_completion_tokens=N, messages=[...])` | same as OpenAI form |
| Raw response text | `response.content[0].text` | `response.choices[0].message.content` | same as OpenAI form |
| API key env var | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` | _(none — local server)_ |
| LiteLLM prefix | `"anthropic/claude-sonnet-4-6"` | `"openai/gpt-4o"` | `"ollama/llama3.2"` |

---

## Lessons by category

### Category A — Pure LangChain swap (drop-in replacement)
01, 02, 03, 05, 06, 07, 08, 09, 10, 11, 13, 14, 15, 23, 24, 25, 30, 33

### Category B — LangChain + Raw SDK (swap both)
27, 29

### Category C — Two models (main + judge/small)
31, 32, 34

### Category D — Raw SDK only
20, 26, 28

### Category E — LiteLLM (model string change only)
19

### Category F — No LLM (lesson doc only, no code file)
12 (MCP server/client — MCP protocol is provider-agnostic), 21 (LangGraph HITL — no LLM in graph), 22 (Hybrid RAG — retrieval only, no generation)

---

## Task 1: Directory structure and requirements

**Files:**
- Create: `labs/openai/` (directory)
- Create: `labs/ollama/` (directory)
- Create: `labs/lessons/openai/` (directory)
- Create: `labs/lessons/ollama/` (directory)
- Create: `labs/openai/README.md`
- Create: `labs/ollama/README.md`
- Modify: `labs/requirements.txt`

- [ ] **Step 1: Create directories**

```bash
mkdir -p labs/openai labs/ollama labs/lessons/openai labs/lessons/ollama
```

Expected: four empty directories created.

- [ ] **Step 2: Check current requirements.txt**

```bash
grep -E "langchain|openai|ollama" labs/requirements.txt
```

Note which packages are already present.

- [ ] **Step 3: Add missing dependencies to labs/requirements.txt**

Append after the last langchain line:

```
langchain-openai>=0.3.0
langchain-ollama>=0.3.0
openai>=1.60.0
```

(Skip any that already appear.)

- [ ] **Step 4: Create labs/openai/README.md**

```markdown
# OpenAI variants

Each file here is a standalone version of the corresponding AgenticCourse lab,
adapted to use `gpt-4o` via `langchain-openai` or the `openai` SDK.

**Prerequisite:** `OPENAI_API_KEY` in `.env`.

| Original | OpenAI variant |
|---|---|
| ../01_model_wrapper.py | 01_model_wrapper_openai.py |
| ../02_lcel_chain.py | 02_lcel_chain_openai.py |
| ../03_agent_framework.py | 03_agent_framework_openai.py |
| ../03_agent_manual.py | 03_agent_manual_openai.py |
| ../05_structured_output.py | 05_structured_output_openai.py |
| ../06_parallel_chains.py | 06_parallel_chains_openai.py |
| ../07_output_parsers.py | 07_output_parsers_openai.py |
| ../08_chatbot_memory.py | 08_chatbot_memory_openai.py |
| ../09_rag.py | 09_rag_openai.py |
| ../10_guardrails.py | 10_guardrails_openai.py |
| ../11_production_chatbot.py | 11_production_chatbot_openai.py |
| ../13_reflection_agent.py | 13_reflection_agent_openai.py |
| ../13_plan_execute_agent.py | 13_plan_execute_agent_openai.py |
| ../14_long_term_memory.py | 14_long_term_memory_openai.py |
| ../14_multi_agent.py | 14_multi_agent_openai.py |
| ../15_spec_driven.py | 15_spec_driven_openai.py |
| ../19_ai_gateway.py | 19_ai_gateway_openai.py |
| ../20_citations_demo.py | 20_citations_demo_openai.py |
| ../20_pdf_vision.py | 20_pdf_vision_openai.py |
| ../23_graph_rag.py | 23_graph_rag_openai.py |
| ../24_corrective_rag.py | 24_corrective_rag_openai.py |
| ../25_evaluation.py | 25_evaluation_openai.py |
| ../26_cost_optimization.py | 26_cost_optimization_openai.py |
| ../27_streaming.py | 27_streaming_openai.py |
| ../28_production_app.py | 28_production_app_openai.py |
| ../29_memory_architectures.py | 29_memory_architectures_openai.py |
| ../30_system_design_helper.py | 30_system_design_helper_openai.py |
| ../31_red_teaming.py | 31_red_teaming_openai.py |
| ../32_governance.py | 32_governance_openai.py |
| ../33_ux_audit_helper.py | 33_ux_audit_helper_openai.py |
| ../34_farm_planner_engine.py | 34_farm_planner_engine_openai.py |
```

- [ ] **Step 5: Create labs/ollama/README.md**

```markdown
# Ollama variants

Each file here is a standalone version of the corresponding AgenticCourse lab,
adapted to use `llama3.2` via `langchain-ollama` or the Ollama OpenAI-compatible endpoint.

**Prerequisite:** Ollama running locally. Run `ollama serve` then `ollama pull llama3.2` (one-time).

| Original | Ollama variant |
|---|---|
| ../01_model_wrapper.py | 01_model_wrapper_ollama.py |
| ../02_lcel_chain.py | 02_lcel_chain_ollama.py |
| ../03_agent_framework.py | 03_agent_framework_ollama.py |
| ../03_agent_manual.py | 03_agent_manual_ollama.py |
| ../05_structured_output.py | 05_structured_output_ollama.py |
| ../06_parallel_chains.py | 06_parallel_chains_ollama.py |
| ../07_output_parsers.py | 07_output_parsers_ollama.py |
| ../08_chatbot_memory.py | 08_chatbot_memory_ollama.py |
| ../09_rag.py | 09_rag_ollama.py |
| ../10_guardrails.py | 10_guardrails_ollama.py |
| ../11_production_chatbot.py | 11_production_chatbot_ollama.py |
| ../13_reflection_agent.py | 13_reflection_agent_ollama.py |
| ../13_plan_execute_agent.py | 13_plan_execute_agent_ollama.py |
| ../14_long_term_memory.py | 14_long_term_memory_ollama.py |
| ../14_multi_agent.py | 14_multi_agent_ollama.py |
| ../15_spec_driven.py | 15_spec_driven_ollama.py |
| ../19_ai_gateway.py | 19_ai_gateway_ollama.py |
| ../20_citations_demo.py | 20_citations_demo_ollama.py |
| ../20_pdf_vision.py | 20_pdf_vision_ollama.py |
| ../23_graph_rag.py | 23_graph_rag_ollama.py |
| ../24_corrective_rag.py | 24_corrective_rag_ollama.py |
| ../25_evaluation.py | 25_evaluation_ollama.py |
| ../26_cost_optimization.py | 26_cost_optimization_ollama.py |
| ../27_streaming.py | 27_streaming_ollama.py |
| ../28_production_app.py | 28_production_app_ollama.py |
| ../29_memory_architectures.py | 29_memory_architectures_ollama.py |
| ../30_system_design_helper.py | 30_system_design_helper_ollama.py |
| ../31_red_teaming.py | 31_red_teaming_ollama.py |
| ../32_governance.py | 32_governance_ollama.py |
| ../33_ux_audit_helper.py | 33_ux_audit_helper_ollama.py |
| ../34_farm_planner_engine.py | 34_farm_planner_engine_ollama.py |
```

- [ ] **Step 6: Commit setup**

```bash
git add labs/openai/ labs/ollama/ labs/lessons/openai/ labs/lessons/ollama/ labs/requirements.txt
git commit -m "chore: add OpenAI + Ollama variant directories and update requirements"
```

---

## Task 2: Category A code files — OpenAI (Lessons 01–11)

**Files:** Create all files below in `labs/openai/`

### Adaptation rule for Category A — OpenAI

Open the source file. Make exactly these three changes:
1. Replace `from langchain_anthropic import ChatAnthropic` → `from langchain_openai import ChatOpenAI`
2. Replace every `ChatAnthropic(` → `ChatOpenAI(`
3. Replace every `"claude-sonnet-4-6"` → `"gpt-4o"` (also replace `MODEL = "claude-sonnet-4-6"` where present)

Everything else (tools, prompts, chains, logic) is identical. Save to `labs/openai/<name>_openai.py`.

- [ ] **Step 1: Create labs/openai/01_model_wrapper_openai.py** (full content — this is the canonical template)

```python
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# Requires OPENAI_API_KEY in .env
model = ChatOpenAI(model="gpt-4o")

response = model.invoke("Explain LangChain in 2 sentences.")
print(response.content)
```

- [ ] **Step 2: Create labs/openai/02_lcel_chain_openai.py**

Source: `labs/02_lcel_chain.py`. Apply the Category A — OpenAI adaptation rule.

Changed lines:
```python
# Line 2: was: from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Line 14: was: model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)
model = ChatOpenAI(model="gpt-4o", temperature=0)
```

- [ ] **Step 3: Create labs/openai/03_agent_framework_openai.py**

Source: `labs/03_agent_framework.py`. Apply the Category A — OpenAI adaptation rule.
Changed: import line → `from langchain_openai import ChatOpenAI`; model class → `ChatOpenAI`; model string → `"gpt-4o"`.

- [ ] **Step 4: Create labs/openai/03_agent_manual_openai.py**

Source: `labs/03_agent_manual.py`. Apply the Category A — OpenAI adaptation rule.
Changed:
```python
# was: from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
# was: model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0).bind_tools(tools)
model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)
```

- [ ] **Step 5: Create labs/openai/05_structured_output_openai.py**

Source: `labs/05_structured_output.py`. Apply Category A — OpenAI adaptation rule.
Changed:
```python
# was: from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
# was: model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)
model = ChatOpenAI(model="gpt-4o", temperature=0)
```

- [ ] **Step 6: Create labs/openai/06_parallel_chains_openai.py**

Source: `labs/06_parallel_chains.py`. Apply Category A — OpenAI adaptation rule.
Changed: import → `ChatOpenAI`; `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` → `ChatOpenAI(model="gpt-4o", temperature=0)`.

- [ ] **Step 7: Create labs/openai/07_output_parsers_openai.py**

Source: `labs/07_output_parsers.py`. Apply Category A — OpenAI adaptation rule.
Changed: import → `ChatOpenAI`; all `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` → `ChatOpenAI(model="gpt-4o", temperature=0)`.

Note: `OutputFixingParser.from_llm(parser=pydantic_parser, llm=model)` at the end uses the same `model` variable — no extra change needed.

- [ ] **Step 8: Create labs/openai/08_chatbot_memory_openai.py**

Source: `labs/08_chatbot_memory.py`. Apply Category A — OpenAI adaptation rule.
Changed: import → `ChatOpenAI`; `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` → `ChatOpenAI(model="gpt-4o", temperature=0)`.

- [ ] **Step 9: Create labs/openai/09_rag_openai.py**

Source: `labs/09_rag.py`. Apply Category A — OpenAI adaptation rule.
Changed: import → `ChatOpenAI`; line 182 `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` → `ChatOpenAI(model="gpt-4o", temperature=0)`.

Also remove the comment on line 243 that references `api.anthropic.com` — replace it with `api.openai.com`.

- [ ] **Step 10: Create labs/openai/10_guardrails_openai.py**

Source: `labs/10_guardrails.py`. Apply Category A — OpenAI adaptation rule.
Changed: import → `ChatOpenAI`; line 75 `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` → `ChatOpenAI(model="gpt-4o", temperature=0)`.

- [ ] **Step 11: Create labs/openai/11_production_chatbot_openai.py**

Source: `labs/11_production_chatbot.py`. Apply Category A — OpenAI adaptation rule.
Changed: import → `ChatOpenAI`; line 161 `ChatAnthropic(model="claude-sonnet-4-6", temperature=0)` → `ChatOpenAI(model="gpt-4o", temperature=0)`.
Also remove the inline reference to `ChatAnthropic` in the string on line 131 — update the example code snippet within the string to show `ChatOpenAI`.

- [ ] **Step 12: Verify syntax on all created files**

```bash
python -m py_compile labs/openai/01_model_wrapper_openai.py \
  labs/openai/02_lcel_chain_openai.py \
  labs/openai/03_agent_framework_openai.py \
  labs/openai/03_agent_manual_openai.py \
  labs/openai/05_structured_output_openai.py \
  labs/openai/06_parallel_chains_openai.py \
  labs/openai/07_output_parsers_openai.py \
  labs/openai/08_chatbot_memory_openai.py \
  labs/openai/09_rag_openai.py \
  labs/openai/10_guardrails_openai.py \
  labs/openai/11_production_chatbot_openai.py
```

Expected: no output (silent success).

- [ ] **Step 13: Commit**

```bash
git add labs/openai/
git commit -m "feat: add OpenAI variants for lessons 01-11 (Category A LangChain)"
```

---

## Task 3: Category A code files — OpenAI (Lessons 13–15, 23–25, 30, 33)

**Files:** Continue creating files in `labs/openai/`

### Adaptation rule
Same Category A — OpenAI rule from Task 2. Files using `MODEL = "claude-sonnet-4-6"` constant: change both the constant and any `ChatAnthropic(model=MODEL` calls.

- [ ] **Step 1: Create labs/openai/13_reflection_agent_openai.py**

Source: `labs/13_reflection_agent.py`. Changed:
```python
# was: from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
# was: MODEL = "claude-sonnet-4-6"
MODEL = "gpt-4o"
# was: model = ChatAnthropic(model=MODEL, temperature=0) [wherever it appears]
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 2: Create labs/openai/13_plan_execute_agent_openai.py**

Source: `labs/13_plan_execute_agent.py`. Apply same pattern as Step 1.

- [ ] **Step 3: Create labs/openai/14_long_term_memory_openai.py**

Source: `labs/14_long_term_memory.py`. Changed:
```python
from langchain_openai import ChatOpenAI
# line 98: ChatAnthropic(model="claude-sonnet-4-6", temperature=0) →
model = ChatOpenAI(model="gpt-4o", temperature=0)
```

- [ ] **Step 4: Create labs/openai/14_multi_agent_openai.py**

Source: `labs/14_multi_agent.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 5: Create labs/openai/15_spec_driven_openai.py**

Source: `labs/15_spec_driven.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 6: Create labs/openai/23_graph_rag_openai.py**

Source: `labs/23_graph_rag.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 7: Create labs/openai/24_corrective_rag_openai.py**

Source: `labs/24_corrective_rag.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 8: Create labs/openai/25_evaluation_openai.py**

Source: `labs/25_evaluation.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 9: Create labs/openai/30_system_design_helper_openai.py**

Source: `labs/30_system_design_helper.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 10: Create labs/openai/33_ux_audit_helper_openai.py**

Source: `labs/33_ux_audit_helper.py`. Changed:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

- [ ] **Step 11: Verify syntax**

```bash
python -m py_compile \
  labs/openai/13_reflection_agent_openai.py \
  labs/openai/13_plan_execute_agent_openai.py \
  labs/openai/14_long_term_memory_openai.py \
  labs/openai/14_multi_agent_openai.py \
  labs/openai/15_spec_driven_openai.py \
  labs/openai/23_graph_rag_openai.py \
  labs/openai/24_corrective_rag_openai.py \
  labs/openai/25_evaluation_openai.py \
  labs/openai/30_system_design_helper_openai.py \
  labs/openai/33_ux_audit_helper_openai.py
```

Expected: silent success.

- [ ] **Step 12: Commit**

```bash
git add labs/openai/
git commit -m "feat: add OpenAI variants for lessons 13-15, 23-25, 30, 33 (Category A LangChain)"
```

---

## Task 4: Complex code files — OpenAI (Categories B, C, D, E)

**Files:** Create remaining OpenAI code files in `labs/openai/`

### Category B — LangChain + Raw SDK (Lessons 27, 29)

- [ ] **Step 1: Create labs/openai/27_streaming_openai.py**

Source: `labs/27_streaming.py`. Two sets of changes:

LangChain changes (Category A rule):
```python
# was: from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
# was: MODEL = "claude-sonnet-4-6"
MODEL = "gpt-4o"
# was: lc_model = ChatAnthropic(model=MODEL, temperature=0)
lc_model = ChatOpenAI(model=MODEL, temperature=0)
```

Raw SDK changes (Demo 1 — TTFT measurement):
```python
# was: import anthropic
import openai
# was: raw_client = anthropic.Anthropic()
raw_client = openai.OpenAI()
```

Replace the Demo 1 streaming block. The original uses `anthropic` streaming syntax. Change to OpenAI streaming:
```python
# was: with raw_client.messages.stream(model=MODEL, max_tokens=512, messages=[...]) as stream:
#          for text in stream.text_stream: ...
# OPENAI streaming:
stream = raw_client.chat.completions.create(
    model=MODEL,
    max_completion_tokens=512,
    messages=[{"role": "user", "content": "..."}],
    stream=True,
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        sys.stdout.write(chunk.choices[0].delta.content)
        sys.stdout.flush()
```

Also update `get_usage()` — the Anthropic response object has `.usage.input_tokens`; OpenAI has `.usage.prompt_tokens` and `.usage.completion_tokens`. Adapt accordingly in the TTFT-timing section.

- [ ] **Step 2: Create labs/openai/29_memory_architectures_openai.py**

Source: `labs/29_memory_architectures.py`. Changes:

LangChain changes:
```python
from langchain_openai import ChatOpenAI
MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
```

Raw SDK changes:
```python
# was: import anthropic
import openai
# was: client = anthropic.Anthropic()
client = openai.OpenAI()
```

Replace raw `client.messages.create(...)` calls with `client.chat.completions.create(...)`. The message format stays the same (`[{"role": "user", "content": "..."}]`). Response text changes from `response.content[0].text` to `response.choices[0].message.content`.

### Category C — Two models (Lessons 31, 32, 34)

- [ ] **Step 3: Create labs/openai/31_red_teaming_openai.py**

Source: `labs/31_red_teaming.py`. Changed:
```python
from langchain_openai import ChatOpenAI
TARGET_MODEL = "gpt-4o"
JUDGE_MODEL = "gpt-4o-mini"
target = ChatOpenAI(model=TARGET_MODEL, temperature=0)
judge = ChatOpenAI(model=JUDGE_MODEL, temperature=0)
```

- [ ] **Step 4: Create labs/openai/32_governance_openai.py**

Source: `labs/32_governance.py`. Changed:
```python
from langchain_openai import ChatOpenAI
ANSWER_MODEL = "gpt-4o"
JUDGE_MODEL = "gpt-4o-mini"
answer_model = ChatOpenAI(model=ANSWER_MODEL, temperature=0)
judge_model = ChatOpenAI(model=JUDGE_MODEL, temperature=0)
```

- [ ] **Step 5: Create labs/openai/34_farm_planner_engine_openai.py**

Source: `labs/34_farm_planner_engine.py`. Changed:
```python
from langchain_openai import ChatOpenAI
ANSWER_MODEL = "gpt-4o"
JUDGE_MODEL = "gpt-4o-mini"
```

Find the `_make_planner_model` factory function (line 585) and update:
```python
def _make_planner_model(timeout: int = 600) -> ChatOpenAI:
    return ChatOpenAI(
        model=ANSWER_MODEL,
        timeout=timeout,
        temperature=0,
    )
```

For all other `ChatAnthropic(` calls in the file, substitute `ChatOpenAI(`. Remove `cache_control` arguments if any (OpenAI handles caching automatically on gpt-4o).

### Category D — Raw SDK only (Lessons 20, 26, 28)

- [ ] **Step 6: Create labs/openai/20_citations_demo_openai.py**

Source: `labs/20_citations_demo.py`. This demo uses Anthropic's native citations feature. The OpenAI equivalent uses inline source references via prompt engineering.

Changed:
```python
# was: import anthropic
import openai
# was: client = anthropic.Anthropic()
client = openai.OpenAI()
# was: MODEL = "claude-sonnet-4-6"
MODEL = "gpt-4o"
```

Replace the Anthropic `documents` block with an OpenAI prompt that asks the model to cite sources inline. The structure:
```python
# Build a context string from the same source documents
context = "\n\n".join(f"[Source {i+1}] {doc}" for i, doc in enumerate(SOURCE_DOCS))

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "Answer using only the provided sources. Cite each fact as [Source N]."},
        {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {QUESTION}"},
    ],
)
answer = response.choices[0].message.content
```

Add a note at the top of the file:
```python
# NOTE: OpenAI does not have a native citations API equivalent to Anthropic's.
# This variant uses prompt-based citation instructions instead.
```

- [ ] **Step 7: Create labs/openai/20_pdf_vision_openai.py**

Source: `labs/20_pdf_vision.py`. OpenAI supports PDF vision via base64-encoded image pages or direct file upload.

Changed:
```python
import base64
import openai
client = openai.OpenAI()
MODEL = "gpt-4o"
```

For PDF processing, use PyMuPDF to render pages as images, then pass as base64:
```python
import fitz  # PyMuPDF

def pdf_to_base64_images(pdf_path: str) -> list[str]:
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    return images

images = pdf_to_base64_images(PDF_PATH)
response = client.chat.completions.create(
    model=MODEL,
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": QUESTION},
            *[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
              for img in images],
        ],
    }],
)
answer = response.choices[0].message.content
```

Add at top:
```python
# Requires: pip install pymupdf
# NOTE: OpenAI vision accepts base64-encoded PNG pages. This variant
# renders each PDF page as PNG using PyMuPDF and sends them as images.
```

- [ ] **Step 8: Create labs/openai/26_cost_optimization_openai.py**

Source: `labs/26_cost_optimization.py`. This file covers 4 levers. Lever 2 (prompt caching) is Anthropic-specific; adapt with a note.

Changed:
```python
import openai
client = openai.OpenAI()

# OpenAI pricing reference (gpt-4o), May 2026
PRICES = {
    "gpt-4o":       {"in": 2.50, "out": 10.00},
    "gpt-4o-mini":  {"in": 0.15, "out": 0.60},
}

def call_cost(model: str, usage) -> float:
    p = PRICES[model]
    return (usage.prompt_tokens * p["in"] + usage.completion_tokens * p["out"]) / 1_000_000
```

Replace `client.messages.create(...)` → `client.chat.completions.create(...)`.

For Lever 2 (cache_control), replace the whole section with:
```python
# =====================================================================
# Lever 2 — Prompt caching
#
# gpt-4o supports automatic prompt caching for prompts >1024 tokens.
# There is no explicit cache_control to set — OpenAI caches automatically.
# Check `usage.prompt_tokens_details.cached_tokens` to see cache hits.
# =====================================================================
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": QUERY}],
)
cached = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
print(f"Cache hits: {cached} tokens")
```

For Lever 4 (Batch API), use the OpenAI Batch API:
```python
# OpenAI Batch API: 50% discount, 24h SLA — same semantics as Anthropic
import json, time
batch_input = [
    {"custom_id": f"req-{i}", "method": "POST", "url": "/v1/chat/completions",
     "body": {"model": "gpt-4o", "messages": [{"role": "user", "content": q}]}}
    for i, q in enumerate(QUERIES)
]
input_file = client.files.create(
    file=("\n".join(json.dumps(r) for r in batch_input)).encode(),
    purpose="batch",
)
batch = client.batches.create(
    input_file_id=input_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
)
print(f"Batch {batch.id} created — status: {batch.status}")
```

- [ ] **Step 9: Create labs/openai/28_production_app_openai.py**

Source: `labs/28_production_app.py`. Changed:
```python
import openai
client = openai.OpenAI()
MODEL = "gpt-4o"
```

Replace `client.messages.create(model=MODEL, max_tokens=N, messages=[...])` → `client.chat.completions.create(model=MODEL, max_completion_tokens=N, messages=[...])`.

Replace `response.content[0].text` → `response.choices[0].message.content`.

Replace `response.usage.input_tokens` → `response.usage.prompt_tokens`.
Replace `response.usage.output_tokens` → `response.usage.completion_tokens`.

### Category E — LiteLLM (Lesson 19)

- [ ] **Step 10: Create labs/openai/19_ai_gateway_openai.py**

Source: `labs/19_ai_gateway.py`. Changed:
```python
# was: HAIKU = "anthropic/claude-haiku-4-5-20251001"
# was: SONNET = "anthropic/claude-sonnet-4-6"
# was: OPUS = "anthropic/claude-opus-4-7"
MINI = "openai/gpt-4o-mini"
SONNET = "openai/gpt-4o"
OPUS = "openai/o1"

# Update the fallback chain:
# was: ["anthropic/claude-sonnet-4-6", "anthropic/claude-haiku-4-5-20251001"]
FALLBACK_CHAIN = ["openai/gpt-4o", "openai/gpt-4o-mini"]
```

Update all comments that reference Anthropic/Claude to reference OpenAI/GPT.
Update the section header comments (Lever 2 bake-off) to use the new model names.
Remove the `ANTHROPIC_API_KEY` note; replace with `OPENAI_API_KEY`.

- [ ] **Step 11: Verify syntax on all Task 4 files**

```bash
python -m py_compile \
  labs/openai/19_ai_gateway_openai.py \
  labs/openai/20_citations_demo_openai.py \
  labs/openai/20_pdf_vision_openai.py \
  labs/openai/26_cost_optimization_openai.py \
  labs/openai/27_streaming_openai.py \
  labs/openai/28_production_app_openai.py \
  labs/openai/29_memory_architectures_openai.py \
  labs/openai/31_red_teaming_openai.py \
  labs/openai/32_governance_openai.py \
  labs/openai/34_farm_planner_engine_openai.py
```

Expected: silent success.

- [ ] **Step 12: Commit**

```bash
git add labs/openai/
git commit -m "feat: add OpenAI variants for complex lessons (19, 20, 26-29, 31-32, 34)"
```

---

## Task 5: Category A code files — Ollama (Lessons 01–11)

### Adaptation rule for Category A — Ollama

Same as Category A — OpenAI, but:
1. `from langchain_anthropic import ChatAnthropic` → `from langchain_ollama import ChatOllama`
2. `ChatAnthropic(` → `ChatOllama(`
3. `"claude-sonnet-4-6"` → `"llama3.2"`
4. Add this comment at the top of every file: `# Requires: ollama serve + ollama pull llama3.2`
5. No API key needed — remove any `load_dotenv()` call if the file has NO other env vars (keep it if other env vars are needed).

- [ ] **Step 1: Create labs/ollama/01_model_wrapper_ollama.py**

```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama

# No API key needed — Ollama runs locally on http://localhost:11434
model = ChatOllama(model="llama3.2")

response = model.invoke("Explain LangChain in 2 sentences.")
print(response.content)
```

- [ ] **Step 2: Create labs/ollama/02_lcel_chain_ollama.py**

Source: `labs/02_lcel_chain.py`. Apply Category A — Ollama rule.
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
# model line:
model = ChatOllama(model="llama3.2", temperature=0)
```

- [ ] **Step 3: Create labs/ollama/03_agent_framework_ollama.py**

Source: `labs/03_agent_framework.py`. Apply Category A — Ollama rule.

- [ ] **Step 4: Create labs/ollama/03_agent_manual_ollama.py**

Source: `labs/03_agent_manual.py`. Apply Category A — Ollama rule.
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
model = ChatOllama(model="llama3.2", temperature=0).bind_tools(tools)
```

- [ ] **Step 5: Create labs/ollama/05_structured_output_ollama.py**

Source: `labs/05_structured_output.py`. Apply Category A — Ollama rule.

Note: `with_structured_output()` works with Ollama models that support tool calling (llama3.2 supports it). No extra changes needed.

- [ ] **Step 6: Create labs/ollama/06_parallel_chains_ollama.py**

Source: `labs/06_parallel_chains.py`. Apply Category A — Ollama rule.

- [ ] **Step 7: Create labs/ollama/07_output_parsers_ollama.py**

Source: `labs/07_output_parsers.py`. Apply Category A — Ollama rule.

- [ ] **Step 8: Create labs/ollama/08_chatbot_memory_ollama.py**

Source: `labs/08_chatbot_memory.py`. Apply Category A — Ollama rule.

- [ ] **Step 9: Create labs/ollama/09_rag_ollama.py**

Source: `labs/09_rag.py`. Apply Category A — Ollama rule.
Also update the comment on the Anthropic API URL line to remove any reference to `api.anthropic.com`.

- [ ] **Step 10: Create labs/ollama/10_guardrails_ollama.py**

Source: `labs/10_guardrails.py`. Apply Category A — Ollama rule.

- [ ] **Step 11: Create labs/ollama/11_production_chatbot_ollama.py**

Source: `labs/11_production_chatbot.py`. Apply Category A — Ollama rule.
Update the inline code snippet string on line 131 to show `ChatOllama` instead of `ChatAnthropic`.

- [ ] **Step 12: Verify syntax**

```bash
python -m py_compile \
  labs/ollama/01_model_wrapper_ollama.py \
  labs/ollama/02_lcel_chain_ollama.py \
  labs/ollama/03_agent_framework_ollama.py \
  labs/ollama/03_agent_manual_ollama.py \
  labs/ollama/05_structured_output_ollama.py \
  labs/ollama/06_parallel_chains_ollama.py \
  labs/ollama/07_output_parsers_ollama.py \
  labs/ollama/08_chatbot_memory_ollama.py \
  labs/ollama/09_rag_ollama.py \
  labs/ollama/10_guardrails_ollama.py \
  labs/ollama/11_production_chatbot_ollama.py
```

Expected: silent success.

- [ ] **Step 13: Commit**

```bash
git add labs/ollama/
git commit -m "feat: add Ollama variants for lessons 01-11 (Category A LangChain)"
```

---

## Task 6: Category A code files — Ollama (Lessons 13–15, 23–25, 30, 33)

**Files:** Continue creating files in `labs/ollama/`

Apply Category A — Ollama rule to each source. All follow the same pattern: swap import, class, model string, add prereq comment.

- [ ] **Step 1: Create labs/ollama/13_reflection_agent_ollama.py**

Source: `labs/13_reflection_agent.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
MODEL = "llama3.2"
model = ChatOllama(model=MODEL, temperature=0)
```

- [ ] **Step 2: Create labs/ollama/13_plan_execute_agent_ollama.py**

Source: `labs/13_plan_execute_agent.py`. Same pattern as Step 1.

- [ ] **Step 3: Create labs/ollama/14_long_term_memory_ollama.py**

Source: `labs/14_long_term_memory.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
model = ChatOllama(model="llama3.2", temperature=0)
```

- [ ] **Step 4: Create labs/ollama/14_multi_agent_ollama.py**

Source: `labs/14_multi_agent.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
MODEL = "llama3.2"
model = ChatOllama(model=MODEL, temperature=0)
```

- [ ] **Step 5: Create labs/ollama/15_spec_driven_ollama.py**

Source: `labs/15_spec_driven.py`. Apply Category A — Ollama rule.

- [ ] **Step 6: Create labs/ollama/23_graph_rag_ollama.py**

Source: `labs/23_graph_rag.py`. Apply Category A — Ollama rule.

- [ ] **Step 7: Create labs/ollama/24_corrective_rag_ollama.py**

Source: `labs/24_corrective_rag.py`. Apply Category A — Ollama rule.

- [ ] **Step 8: Create labs/ollama/25_evaluation_ollama.py**

Source: `labs/25_evaluation.py`. Apply Category A — Ollama rule.

- [ ] **Step 9: Create labs/ollama/30_system_design_helper_ollama.py**

Source: `labs/30_system_design_helper.py`. Apply Category A — Ollama rule.

- [ ] **Step 10: Create labs/ollama/33_ux_audit_helper_ollama.py**

Source: `labs/33_ux_audit_helper.py`. Apply Category A — Ollama rule.

- [ ] **Step 11: Verify syntax**

```bash
python -m py_compile \
  labs/ollama/13_reflection_agent_ollama.py \
  labs/ollama/13_plan_execute_agent_ollama.py \
  labs/ollama/14_long_term_memory_ollama.py \
  labs/ollama/14_multi_agent_ollama.py \
  labs/ollama/15_spec_driven_ollama.py \
  labs/ollama/23_graph_rag_ollama.py \
  labs/ollama/24_corrective_rag_ollama.py \
  labs/ollama/25_evaluation_ollama.py \
  labs/ollama/30_system_design_helper_ollama.py \
  labs/ollama/33_ux_audit_helper_ollama.py
```

Expected: silent success.

- [ ] **Step 12: Commit**

```bash
git add labs/ollama/
git commit -m "feat: add Ollama variants for lessons 13-15, 23-25, 30, 33 (Category A LangChain)"
```

---

## Task 7: Complex code files — Ollama (Categories B, C, D, E)

**Files:** Create remaining Ollama code files in `labs/ollama/`

### Key Ollama raw SDK note

Ollama exposes an OpenAI-compatible REST endpoint at `http://localhost:11434/v1`. Use the `openai` Python SDK with a custom `base_url` and `api_key="ollama"`:

```python
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
```

This replaces both `anthropic.Anthropic()` AND `openai.OpenAI()` for Ollama raw calls.

- [ ] **Step 1: Create labs/ollama/27_streaming_ollama.py**

Source: `labs/27_streaming.py`. LangChain changes:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
MODEL = "llama3.2"
lc_model = ChatOllama(model=MODEL, temperature=0)
```

Raw SDK changes (Demo 1):
```python
import openai
raw_client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
```

Replace the Anthropic streaming block with the OpenAI-compatible streaming block (same as Task 4 Step 1, but using the `raw_client` above). Usage object uses `.usage.prompt_tokens` / `.usage.completion_tokens`.

- [ ] **Step 2: Create labs/ollama/29_memory_architectures_ollama.py**

Source: `labs/29_memory_architectures.py`. LangChain changes:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
MODEL = "llama3.2"
model = ChatOllama(model=MODEL, temperature=0)
```

Raw SDK changes:
```python
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
```

Replace `client.messages.create(...)` → `client.chat.completions.create(...)`. Response text: `response.choices[0].message.content`.

- [ ] **Step 3: Create labs/ollama/31_red_teaming_ollama.py**

Source: `labs/31_red_teaming.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
TARGET_MODEL = "llama3.2"
JUDGE_MODEL = "llama3.2"
target = ChatOllama(model=TARGET_MODEL, temperature=0)
judge = ChatOllama(model=JUDGE_MODEL, temperature=0)
```

Note: Ollama uses the same model for both target and judge (no separate small model).

- [ ] **Step 4: Create labs/ollama/32_governance_ollama.py**

Source: `labs/32_governance.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
ANSWER_MODEL = "llama3.2"
JUDGE_MODEL = "llama3.2"
answer_model = ChatOllama(model=ANSWER_MODEL, temperature=0)
judge_model = ChatOllama(model=JUDGE_MODEL, temperature=0)
```

- [ ] **Step 5: Create labs/ollama/34_farm_planner_engine_ollama.py**

Source: `labs/34_farm_planner_engine.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
from langchain_ollama import ChatOllama
ANSWER_MODEL = "llama3.2"
JUDGE_MODEL = "llama3.2"
```

Update `_make_planner_model`:
```python
def _make_planner_model(timeout: int = 600) -> ChatOllama:
    return ChatOllama(
        model=ANSWER_MODEL,
        timeout=timeout,
        temperature=0,
    )
```

Replace all remaining `ChatAnthropic(` with `ChatOllama(`. Remove any `cache_control` arguments.

- [ ] **Step 6: Create labs/ollama/19_ai_gateway_ollama.py**

Source: `labs/19_ai_gateway.py`. Changed:
```python
MINI = "ollama/llama3.2"
SONNET = "ollama/llama3.2"
OPUS = "ollama/llama3.2"
FALLBACK_CHAIN = ["ollama/llama3.2"]
```

Note at top:
```python
# NOTE: Ollama variant — all tiers use llama3.2.
# Ollama does not support the Batch API or Message Batches.
# Requires: ollama serve + ollama pull llama3.2
```

- [ ] **Step 7: Create labs/ollama/20_citations_demo_ollama.py**

Source: `labs/20_citations_demo.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
# NOTE: Ollama has no native citations API. This variant uses prompt-based citation instructions.
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "llama3.2"
```

Same prompt-based citation pattern as the OpenAI variant (Task 4 Step 6).

- [ ] **Step 8: Create labs/ollama/20_pdf_vision_ollama.py**

Source: `labs/20_pdf_vision.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2 (or llava for vision)
# NOTE: For PDF vision, use llava model (multimodal). llama3.2 is text-only.
# ollama pull llava
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "llava"
```

Use the same PyMuPDF base64 rendering approach as the OpenAI variant (Task 4 Step 7). The Ollama OpenAI-compatible endpoint accepts `image_url` with base64 for multimodal models like llava.

- [ ] **Step 9: Create labs/ollama/26_cost_optimization_ollama.py**

Source: `labs/26_cost_optimization.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
# NOTE: Ollama runs locally — no API cost. Token counts shown for reference only.
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

PRICES = {
    "llama3.2": {"in": 0.0, "out": 0.0},  # local model, no API cost
}

def call_cost(model: str, usage) -> float:
    return 0.0  # Ollama is free to run locally
```

Lever 2 (caching): Replace with note that Ollama does not have a prompt cache API. Add a note about KV cache behavior being internal to the runtime.

Lever 4 (Batch API): Replace with note that Ollama does not have a batch API; demonstrate sequential processing instead.

- [ ] **Step 10: Create labs/ollama/28_production_app_ollama.py**

Source: `labs/28_production_app.py`. Changed:
```python
# Requires: ollama serve + ollama pull llama3.2
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "llama3.2"
```

Replace raw API calls (same pattern as Task 4 Step 9). Response object uses `.choices[0].message.content` and `.usage.prompt_tokens` / `.usage.completion_tokens`.

- [ ] **Step 11: Verify syntax**

```bash
python -m py_compile \
  labs/ollama/19_ai_gateway_ollama.py \
  labs/ollama/20_citations_demo_ollama.py \
  labs/ollama/20_pdf_vision_ollama.py \
  labs/ollama/26_cost_optimization_ollama.py \
  labs/ollama/27_streaming_ollama.py \
  labs/ollama/28_production_app_ollama.py \
  labs/ollama/29_memory_architectures_ollama.py \
  labs/ollama/31_red_teaming_ollama.py \
  labs/ollama/32_governance_ollama.py \
  labs/ollama/34_farm_planner_engine_ollama.py
```

Expected: silent success.

- [ ] **Step 12: Commit**

```bash
git add labs/ollama/
git commit -m "feat: add Ollama variants for complex lessons (19, 20, 26-29, 31-32, 34)"
```

---

## Task 8: OpenAI lesson docs (all 30)

**Files:** Create 30 files in `labs/lessons/openai/`

### Lesson doc template

Every OpenAI lesson doc follows this template:

```markdown
# XX — [Lesson Title] (OpenAI variant)

> **Provider variant — OpenAI (`gpt-4o`)**
> This is the OpenAI version of [lesson title]. It uses `ChatOpenAI` from `langchain-openai` and `gpt-4o` instead of `ChatAnthropic` and `claude-sonnet-4-6`. All patterns, chains, and logic are identical to the Anthropic version. Requires `OPENAI_API_KEY` in `.env`.

---

[COPY THE FULL CONTENT OF labs/lessons/XX-lesson-name.md HERE]

[APPLY THESE SUBSTITUTIONS THROUGHOUT:]
- "Anthropic" → "OpenAI" (in non-code prose)
- "ChatAnthropic" → "ChatOpenAI" (in code blocks and prose)
- "claude-sonnet-4-6" → "gpt-4o"
- "claude-haiku-4-5-20251001" → "gpt-4o-mini"
- "langchain_anthropic" → "langchain_openai"
- "ANTHROPIC_API_KEY" → "OPENAI_API_KEY"
- "api.anthropic.com" → "api.openai.com"
- File references "../XX_original.py" → "../openai/XX_original_openai.py"
```

### Category F lessons (no LLM) — special treatment

For lessons 12, 21, 22: copy the original lesson doc, add the provider variant callout at the top stating:
```
> **Provider variant — OpenAI**
> This lesson uses no LLM provider directly — [MCP protocol / LangGraph graph patterns / hybrid retrieval] are fully provider-agnostic. The original lab files work unchanged with any provider. No OpenAI-specific code files are created for this lesson.
```

- [ ] **Step 1: Create the 30 OpenAI lesson docs**

Create each file by copying the corresponding original from `labs/lessons/`, adding the provider variant callout, and applying all substitutions:

| Source | Output |
|---|---|
| `labs/lessons/01-model-wrapper.md` | `labs/lessons/openai/01-model-wrapper.md` |
| `labs/lessons/02-lcel-composition.md` | `labs/lessons/openai/02-lcel-composition.md` |
| `labs/lessons/03-agent-tool-loop.md` | `labs/lessons/openai/03-agent-tool-loop.md` |
| `labs/lessons/05-structured-output.md` | `labs/lessons/openai/05-structured-output.md` |
| `labs/lessons/06-parallel-chains.md` | `labs/lessons/openai/06-parallel-chains.md` |
| `labs/lessons/07-output-parsers.md` | `labs/lessons/openai/07-output-parsers.md` |
| `labs/lessons/08-chatbot-memory.md` | `labs/lessons/openai/08-chatbot-memory.md` |
| `labs/lessons/09-rag.md` | `labs/lessons/openai/09-rag.md` |
| `labs/lessons/10-guardrails.md` | `labs/lessons/openai/10-guardrails.md` |
| `labs/lessons/11-production-capstone.md` | `labs/lessons/openai/11-production-capstone.md` |
| `labs/lessons/12-mcp.md` | `labs/lessons/openai/12-mcp.md` (Category F — no code files) |
| `labs/lessons/13-reflection-plan-execute.md` | `labs/lessons/openai/13-reflection-plan-execute.md` |
| `labs/lessons/14-multi-agent-ltm.md` | `labs/lessons/openai/14-multi-agent-ltm.md` |
| `labs/lessons/15-spec-driven-development.md` | `labs/lessons/openai/15-spec-driven-development.md` |
| `labs/lessons/19-ai-gateway.md` | `labs/lessons/openai/19-ai-gateway.md` |
| `labs/lessons/20-files-document-ai.md` | `labs/lessons/openai/20-files-document-ai.md` |
| `labs/lessons/21-custom-langgraph.md` | `labs/lessons/openai/21-custom-langgraph.md` (Category F) |
| `labs/lessons/22-hybrid-rag.md` | `labs/lessons/openai/22-hybrid-rag.md` (Category F) |
| `labs/lessons/23-graph-rag.md` | `labs/lessons/openai/23-graph-rag.md` |
| `labs/lessons/24-corrective-rag.md` | `labs/lessons/openai/24-corrective-rag.md` |
| `labs/lessons/25-evaluation.md` | `labs/lessons/openai/25-evaluation.md` |
| `labs/lessons/26-cost-optimization.md` | `labs/lessons/openai/26-cost-optimization.md` |
| `labs/lessons/27-streaming.md` | `labs/lessons/openai/27-streaming.md` |
| `labs/lessons/28-production-deploy.md` | `labs/lessons/openai/28-production-deploy.md` |
| `labs/lessons/29-memory-architectures.md` | `labs/lessons/openai/29-memory-architectures.md` |
| `labs/lessons/30-system-design.md` | `labs/lessons/openai/30-system-design.md` |
| `labs/lessons/31-red-teaming.md` | `labs/lessons/openai/31-red-teaming.md` |
| `labs/lessons/32-governance.md` | `labs/lessons/openai/32-governance.md` |
| `labs/lessons/33-ux-patterns.md` | `labs/lessons/openai/33-ux-patterns.md` |
| `labs/lessons/34-farm-planner.md` | `labs/lessons/openai/34-farm-planner.md` |

For each file:
1. Read the source lesson doc
2. Add the provider variant callout block at the very top (after the `# XX —` title)
3. Apply all text substitutions from the template above
4. Update all code blocks within the doc to use OpenAI syntax

Additional per-lesson notes:
- **Lesson 20**: The "What changes from Anthropic" callout must note that citations are prompt-engineered (not native) and PDF vision uses base64 images via PyMuPDF.
- **Lesson 26**: Note that Lever 2 (caching) differs — OpenAI caches automatically; explain `cached_tokens` in usage. Note Lever 4 uses the OpenAI Batch API.
- **Lesson 27**: Note that Demo 1 uses `openai.OpenAI()` for raw streaming; the LangChain and LangGraph demos are unchanged.
- **Lessons 31, 32**: Note that `JUDGE_MODEL = "gpt-4o-mini"` (cheaper small model).

- [ ] **Step 2: Spot-check 5 files**

Open and verify these 5 docs contain no remaining "ChatAnthropic", "claude-sonnet", "langchain_anthropic", or "ANTHROPIC_API_KEY":

```bash
grep -l "ChatAnthropic\|claude-sonnet\|langchain_anthropic\|ANTHROPIC_API_KEY" \
  labs/lessons/openai/*.md
```

Expected: empty output (no matches).

- [ ] **Step 3: Commit**

```bash
git add labs/lessons/openai/
git commit -m "feat: add OpenAI lesson docs for all 30 provider-agnostic lessons"
```

---

## Task 9: Ollama lesson docs (all 30)

**Files:** Create 30 files in `labs/lessons/ollama/`

### Lesson doc template — Ollama

Same template as Task 8, but with these substitutions instead:

```
- "Anthropic" → "Ollama" (in non-code prose)
- "ChatAnthropic" → "ChatOllama"
- "claude-sonnet-4-6" → "llama3.2"
- "claude-haiku-4-5-20251001" → "llama3.2"
- "langchain_anthropic" → "langchain_ollama"
- "ANTHROPIC_API_KEY" → (remove — no API key needed)
- File references "../XX_original.py" → "../ollama/XX_original_ollama.py"
```

Provider variant callout block (use this at the top of every Ollama lesson doc):
```
> **Provider variant — Ollama (`llama3.2`)**
> This is the Ollama version of [lesson title]. It uses `ChatOllama` from `langchain-ollama` and runs fully locally — no API key needed. Requires `ollama serve` running and `ollama pull llama3.2` completed. All patterns and logic are identical to the Anthropic version.
```

Category F callout (for lessons 12, 21, 22):
```
> **Provider variant — Ollama**
> This lesson uses no LLM provider directly — [MCP protocol / LangGraph graph patterns / hybrid retrieval] are fully provider-agnostic. The original lab files work unchanged with any provider. No Ollama-specific code files are created for this lesson.
```

- [ ] **Step 1: Create the 30 Ollama lesson docs**

Same table as Task 8, output path is `labs/lessons/ollama/` instead of `labs/lessons/openai/`.

Additional per-lesson notes for Ollama docs:
- **Lesson 05** (Structured Output): Add a note that `with_structured_output()` requires a model that supports function calling. `llama3.2` supports it; if you encounter errors, try `ollama pull llama3.1:8b` as an alternative.
- **Lesson 19** (AI Gateway): Note that all three model tiers use `llama3.2` since Ollama only has one installed model by default. Students can `ollama pull mistral` to demonstrate a true multi-model bake-off.
- **Lesson 20**: Note that citations are prompt-engineered, and PDF vision requires `llava` (`ollama pull llava`) not `llama3.2`.
- **Lesson 26**: Note that Ollama has no API cost and no Batch API.
- **Lesson 27**: Note raw SDK uses the Ollama OpenAI-compatible endpoint.
- **Lessons 31, 32**: Note that `JUDGE_MODEL = "llama3.2"` (same model for both target and judge, unlike Anthropic which uses haiku for judging).

- [ ] **Step 2: Spot-check**

```bash
grep -l "ChatAnthropic\|claude-sonnet\|langchain_anthropic\|ANTHROPIC_API_KEY" \
  labs/lessons/ollama/*.md
```

Expected: empty output.

- [ ] **Step 3: Commit**

```bash
git add labs/lessons/ollama/
git commit -m "feat: add Ollama lesson docs for all 30 provider-agnostic lessons"
```

---

## Task 10: Final validation

- [ ] **Step 1: Count files created**

```bash
echo "OpenAI code files:"; ls labs/openai/*.py 2>/dev/null | wc -l
echo "Ollama code files:"; ls labs/ollama/*.py 2>/dev/null | wc -l
echo "OpenAI lesson docs:"; ls labs/lessons/openai/*.md 2>/dev/null | wc -l
echo "Ollama lesson docs:"; ls labs/lessons/ollama/*.md 2>/dev/null | wc -l
```

Expected:
```
OpenAI code files: 31
Ollama code files: 31
OpenAI lesson docs: 30
Ollama lesson docs: 30
```

- [ ] **Step 2: Bulk syntax check — OpenAI code files**

```bash
python -m py_compile labs/openai/*.py
```

Expected: silent success (no output).

- [ ] **Step 3: Bulk syntax check — Ollama code files**

```bash
python -m py_compile labs/ollama/*.py
```

Expected: silent success.

- [ ] **Step 4: Verify no Anthropic references in variant code files**

```bash
grep -r "ChatAnthropic\|langchain_anthropic\|anthropic\.Anthropic\|claude-sonnet\|claude-haiku" \
  labs/openai/ labs/ollama/
```

Expected: no matches. If any match found, open that file and apply the correct substitution.

- [ ] **Step 5: Verify no Anthropic API key references in Ollama code**

```bash
grep -r "ANTHROPIC_API_KEY" labs/ollama/
```

Expected: no matches.

- [ ] **Step 6: Final commit**

```bash
git add .
git status  # review staged files
git commit -m "feat: complete OpenAI + Ollama lesson variants (30 lessons, 122 files)"
```

---

## Lessons excluded (for reference)

These 4 lessons have **no variants** — they are Anthropic-specific:

| Lesson | Reason |
|---|---|
| `04-prompt-caching.md` | Uses Anthropic `cache_control` — not portable |
| `16-vibe-coding.md` | Requires Claude Code runtime |
| `17-claude-skills.md` | Claude Code plugin system |
| `18-anthropic-sdk.md` | The lesson IS the Anthropic SDK |
