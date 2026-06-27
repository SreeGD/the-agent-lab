# Gap Sessions Design — AI Engineer 2026 Roadmap Coverage

**Date:** 2026-06-27
**Status:** Approved
**Roadmap source:** "How to Become an AI Engineer in 2026" by Brij Kishore Pandey

## Problem

The AgenticCourse curriculum covers Roadmap Categories 03–08 well but has five uncovered
or partially covered categories: LLM Fundamentals (01), Prompt & Context Engineering (02),
Inference & Deployment (10), Multimodal Integration (11), Ecosystem Fluency (12), and
Career Compounding (13). Software Engineering Essentials (09) is assumed background with
no on-ramp.

## Scope

**7 new sessions** (each = lesson `.md` + runnable lab `.py` + CURRICULUM.csv row)
**5 in-place edits** to existing sessions (no new files)

Sequencing: Track-grouped (B), matching existing CURRICULUM.csv track structure.

---

## New Sessions

### Session 00 — LLM Fundamentals
**Fills:** Roadmap Category 01
**Track:** Track 0 — Foundations (new)
**Files:**
- `labs/00_llm_fundamentals.py`
- `labs/lessons/00-llm-fundamentals.md`

**Lesson content — 7 theory blocks, each with ASCII visual:**
1. Transformer architecture (attention heads, layers, residual stream)
2. Tokenization — BPE mechanics, why splitting on spaces is wrong
3. Context window — KV cache, quadratic cost growth with length
4. Sampling — temperature, top-p, top-k; why `temperature=0` ≠ deterministic
5. Reasoning models — chain-of-thought, thinking tokens, when to use them
6. Benchmarks — how to read MMLU, HumanEval, LMSYS Arena, MTEB
7. Model family map — Claude vs GPT vs Gemini vs open-weight, selection heuristics

**Lab (`00_llm_fundamentals.py`):**
- Visualize token boundaries inline for a user-supplied prompt (Anthropic token counting API)
- Measure context window fill % for a given input
- Same prompt at temperature 0 / 0.7 / 1.2 — print output variance across 3 runs each
- Print hardcoded benchmark comparison table (Claude / GPT-4o / Llama-3) with commentary

**Prerequisites:** None — this is session 0.

---

### Session 00b — Engineering Foundations for AI
**Fills:** Roadmap Category 09
**Track:** Track 0 — Foundations (optional)
**Files:**
- `labs/00b_engineering_foundations.py`
- `labs/lessons/00b-engineering-foundations.md`

**Lesson content:** Python async patterns for LLM I/O, FastAPI + Pydantic for an AI
endpoint, Docker + docker-compose for a RAG stack, Postgres + pgvector setup.

**Lab (`00b_engineering_foundations.py`):**
- Minimal FastAPI app with one `/chat` endpoint backed by Claude
- Containerized with Docker (Dockerfile + docker-compose.yml included)
- pgvector wired up as the vector store skeleton
- Runnable as `docker-compose up` — serves as the skeleton every later session builds on

**Prerequisites:** None — optional parallel to Session 00.

---

### Session 02b — Prompt Engineering Deep Dive
**Fills:** Roadmap Category 02 (partial gap — caching and structured output covered)
**Track:** Track 0 — Foundations
**Files:**
- `labs/02b_prompt_engineering.py`
- `labs/lessons/02b-prompt-engineering.md`

**Lesson content:** System prompt anatomy for Claude, few-shot examples, Chain-of-Thought,
XML structuring (Claude-native `<thinking>` + `<answer>` tags), extended thinking
(`budget_tokens` on claude-opus-4-8).

**Lab (`02b_prompt_engineering.py`):**
- Single "prompt workbench" — same classification task run through 5 strategies:
  1. Zero-shot
  2. Few-shot (3 examples)
  3. Chain-of-Thought
  4. XML-structured
  5. Extended thinking
- Prints: output quality (self-graded via LLM judge), token count, cost for each
- Learners see cost/quality trade-off directly; CoT and extended thinking win quality,
  zero-shot wins cost

**Prerequisites:** Sessions 01–05 (uses structured output + prompt caching patterns).

---

### Session 07b — Open-Weight Models & HuggingFace Ecosystem
**Fills:** Roadmap Category 12
**Track:** Track C — Alt Architectures
**Files:**
- `labs/07b_ecosystem_fluency.py`
- `labs/lessons/07b-ecosystem-fluency.md`

**Lesson content:** HuggingFace Hub (model cards, datasets, Spaces, Inference API),
open-weight model families (Llama 3, Qwen 2.5, DeepSeek, Mistral, Kimi), how to read
arXiv papers efficiently (abstract → method → results), interpreting benchmarks with
concrete examples of what MMLU vs HumanEval vs LMSYS Arena vs MTEB actually measure.

**Lab (`07b_ecosystem_fluency.py`) — three parts:**
1. **HF Hub API** — search models by task, read a model card programmatically, pull a
   dataset row; uses `huggingface_hub` library
2. **Provider shootout** — same prompt against Claude (Anthropic API) + Llama 3 (Ollama,
   linking to `labs/ollama/`) + a HuggingFace Inference API model; prints output, latency,
   cost side-by-side
3. **Benchmark reader** — given a model name, print its known scores from a bundled
   reference table with commentary on what each benchmark actually measures

**Prerequisites:** Session 07 (Anthropic SDK), `labs/ollama/` installed.

---

### Session 08b — Inference Platforms & Self-Hosting
**Fills:** Roadmap Category 10
**Track:** Track C — Alt Architectures
**Files:**
- `labs/08b_inference_platforms.py`
- `labs/lessons/08b-inference-platforms.md`
- `labs/docker/ollama-compose.yml` (new Docker Compose file)

**Lesson content:** Cloud inference platforms (groq, together.ai, Fireworks, Replicate)
vs managed cloud AI (Bedrock, Vertex AI, Azure AI) vs self-hosting (Ollama, vLLM);
cost/latency/privacy trade-off matrix; when each tier makes sense.

**Lab (`08b_inference_platforms.py`) — two parts:**

*Part 1 — Cloud comparison:*
- Same prompt fired at groq + together.ai + Fireworks via LiteLLM
- Prints tokens/sec, cost per 1M tokens, end-to-end latency side-by-side
- Replicate included as image-gen provider preview (calls Flux Schnell)

*Part 2 — Self-hosting path:*
- `labs/docker/ollama-compose.yml` spins up Ollama container
- Lab script calls it via OpenAI-compatible endpoint (`http://localhost:11434/v1`)
- Lesson notes include vLLM Docker command for GPU-equipped learners (documented,
  not a running lab requirement)

**Prerequisites:** Session 08 (AI Gateway / LiteLLM).

---

### Session 09b — Voice & Image Generation Agents
**Fills:** Roadmap Category 11 (extends Session 09's vision/document coverage)
**Track:** Track D — Data & Multi-modal
**Files:**
- `labs/09b_voice_image_agents.py`
- `labs/lessons/09b-voice-image-agents.md`

**Lesson content:** STT → reasoning → TTS pipeline architecture, image generation as a
tool call, Claude vision for understanding generated images, provider trade-offs
(cost vs quality vs latency), when to reach for each modality.

**Lab (`09b_voice_image_agents.py`) — two tracks, selected by `TRACK` env var:**

*Budget track (`TRACK=budget`):*
- STT: local `openai-whisper` package (CPU, no API key)
- Reasoning: Claude Sonnet
- Image gen: DALL-E 3 via OpenAI API
- TTS: OpenAI TTS API
- Pipeline: speak a prompt → transcribe → Claude refines → DALL-E generates →
  Claude describes result → TTS reads aloud
- New accounts required: none beyond existing Anthropic + OpenAI keys

*Quality track (`TRACK=quality`):*
- STT: Whisper via Replicate API
- Reasoning: Claude Opus
- Image gen: Flux Pro via Replicate
- TTS: ElevenLabs
- Same pipeline, swapped providers; learners observe quality delta directly
- New accounts required: Replicate, ElevenLabs

Both tracks produce identical output structure (transcription, refined prompt, image URL,
audio file path) enabling direct comparison. Required API keys documented at file top.

**Prerequisites:** Session 09 (Files & Document AI), OpenAI API key.

---

### Session 21b — Portfolio Generator
**Fills:** Roadmap Category 13
**Track:** Track G — Architect Skills
**Files:**
- `labs/21b_portfolio_generator.py`
- `labs/lessons/21b-portfolio-generator.md`

**Lesson content:** Why building in public compounds (shipping → writing → community →
opportunities), what separates a strong AI project README from a weak one, how to extract
a coherent narrative from course work for a technical audience.

**Lab (`21b_portfolio_generator.py`):**
1. Scans `labs/*.py` for module-level docstrings + key patterns (tools used, LangGraph
   nodes, APIs called) via AST parsing
2. Calls Claude to write a project card per lab: one-line summary, what it demonstrates,
   tech stack
3. Synthesizes `PORTFOLIO.md` at repo root — GitHub-ready, with:
   - Skills matrix table (patterns × sessions)
   - Project cards grid
   - Getting started instructions
4. Drafts a LinkedIn "what I built" post summarizing the full course arc (written to
   `PORTFOLIO_linkedin.txt`)

**Prerequisites:** All prior sessions (reads their source files).

---

## In-Place Edits (5 existing sessions)

### 1. Guardrails (`10_guardrails.py` + `10-guardrails.md`)
**Add:** `guardrails-ai` library integration
- Input validator using a Guardrails AI guard (topic restriction)
- Output validator checking for PII using a built-in guard
- NeMo Guardrails YAML config example (colang file) with a jailbreak rail
- Side-by-side: Claude's native refusal vs library-enforced guardrail

### 2. Hybrid RAG (`22_hybrid_rag.py` + `22-hybrid-rag.md`)
**Add:** HyDE (Hypothetical Document Embeddings) retrieval variant
- `hyde_retrieve(query)`: generate a hypothetical answer via Claude, embed it, use
  as query vector — 3-line addition to existing pipeline
- Compare HyDE vs standard dense retrieval on the same query set
- Add to lesson as a named pattern with a "when to use" section

### 3. Evaluation (`25_evaluation.py` + `25-evaluation.md`)
**Add:** Langfuse as second observability platform
- Langfuse SDK trace wrapping the same eval run as LangSmith
- Side-by-side dashboard comparison noted in lesson (Langfuse is open-source,
  self-hostable; LangSmith is managed)
- Add `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` to env var list

### 4. Agent Tool Loop (`03_agent_manual.py` + `03-agent-tool-loop.md`)
**Add:** Parallel tool calls example
- New section demonstrating two tools dispatched simultaneously via async gather
- `tool_choice: auto` with two independent tools in one turn
- Print timing: sequential vs parallel dispatch on the same task

### 5. AI Gateway (`19_ai_gateway.py` + `19-ai-gateway.md`)
**Add:** portkey and Kong API Gateway as named alternatives
- portkey: semantic caching + observability layer (mention + code snippet)
- Kong AI Gateway: enterprise rate-limiting + plugin model (mention + config snippet)
- Extend the provider comparison table with these two

---

## CURRICULUM.csv Updates

7 new rows to be inserted at correct track positions:

| Session | Week | Track | Title | Hours | Files to Build |
|---|---|---|---|---|---|
| 00 | 0 | Track 0 — Foundations | LLM Internals & Model Selection | 2 | `00_llm_fundamentals.py` |
| 00b | 0 | Track 0 — Foundations (Optional) | Engineering Foundations for AI | 2 | `00b_engineering_foundations.py`, `Dockerfile`, `docker-compose.yml` |
| 02b | 1 | Track 0 — Foundations | Prompt Engineering Deep Dive | 2 | `02b_prompt_engineering.py` |
| 07b | 3 | Track C — Alt Architectures | Open-Weight Models & HuggingFace | 2 | `07b_ecosystem_fluency.py` |
| 08b | 3 | Track C — Alt Architectures | Inference Platforms & Self-Hosting | 2 | `08b_inference_platforms.py`, `docker/ollama-compose.yml` |
| 09b | 4 | Track D — Data & Multi-modal | Voice & Image Generation Agents | 2 | `09b_voice_image_agents.py` |
| 21b | 6 | Track G — Architect Skills | Shipping & Building in Public | 1 | `21b_portfolio_generator.py` |

---

## Dependencies & New Packages

| Session | New packages |
|---|---|
| 00 | none (uses `anthropic` SDK already installed) |
| 00b | `fastapi`, `uvicorn`, `asyncpg`, `pgvector` (Docker path: no install needed) |
| 02b | none |
| 07b | `huggingface_hub` |
| 08b | `litellm` (already in Session 08), Docker for Ollama path |
| 09b budget | `openai-whisper`, `sounddevice`, `soundfile` |
| 09b quality | `replicate`, `elevenlabs` |
| 21b | none (uses `anthropic` + stdlib `ast`) |
| S10 edit | `guardrails-ai`, `nemoguardrails` |
| S14 edit | `langfuse` |

---

## File Tree (net new)

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
docs/
  superpowers/
    specs/
      2026-06-27-gap-sessions-design.md   ← this file
PORTFOLIO.md                              (generated by Session 21b lab)
```

---

## Success Criteria

- All 13 roadmap categories have at least one session mapped in `roadmap-2026-mapping.md`
- Every new session has a runnable lab (no import errors, exits cleanly with `python labs/NN.py`)
- `pytest labs/ -x` passes (no regressions in existing sessions)
- `ruff check labs/` clean across all new and edited files
- CURRICULUM.csv has 7 new rows in correct track positions
- `roadmap-2026-mapping.md` status column updated: all gaps resolved
