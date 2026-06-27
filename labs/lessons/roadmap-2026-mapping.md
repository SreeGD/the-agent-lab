# AI Engineer 2026 Roadmap → Course Mapping

Source: "How to Become an AI Engineer in 2026" by Brij Kishore Pandey (@brijpandeyji)

This document maps every category in the 2026 roadmap to existing course sessions,
calls out gaps, and lists suggested new sessions to fill them.

---

## Coverage Summary

| # | Roadmap Category | Status | Sessions |
|---|---|---|---|
| 01 | LLM Fundamentals | ⚠️ Gap | reference only |
| 02 | Prompt & Context Engineering | 🟡 Partial | S4, S5, S1c |
| 03 | RAG Systems | ✅ Covered | S9, S11, S12, S13 |
| 04 | Agentic Systems | ✅ Covered | S1, S1b, S1c, S2, S3, S6 |
| 05 | AI Gateways & Routing | ✅ Covered | S8 |
| 06 | Guardrails & Safety | ✅ Covered | S10, S19, S20 |
| 07 | Observability & Evals | ✅ Covered | S14, S17 |
| 08 | Production AI Engineering | ✅ Covered | S15, S16, S17 |
| 09 | Software Engineering Essentials | ⚠️ Gap | assumed background |
| 10 | Inference & Deployment | 🟡 Partial | S17 (deploy only) |
| 11 | Multimodal Integration | 🟡 Partial | S9 (vision/docs only) |
| 12 | Ecosystem Fluency | ⚠️ Gap | labs/ollama only |
| 13 | Career Compounding | ⚠️ Gap | none |

---

## Detailed Mapping

### 01 — LLM Fundamentals
**Roadmap topics:** Transformers, Tokenization, Context windows, Sampling,
Reasoning models, Benchmarks

**Course coverage:**
- `labs/lessons/llm-api-internals.md` — reference doc, not a lab session
- `labs/01_model_wrapper.py` — basic model invocation (no theory)

**Gap:** No session teaches transformers, tokenization internals, sampling
strategies (temperature, top-p), or how to read model benchmarks.

**Suggested session:** New Session 0 — *LLM Internals & Model Selection*
- Tokens, context windows, sampling parameters
- Benchmark reading (MMLU, HumanEval, LMSYS Arena)
- Model family comparison (Claude, GPT, Gemini, open-weight)
- File: `00_llm_fundamentals.py`

---

### 02 — Prompt & Context Engineering
**Roadmap topics:** System prompts, Few-shot, CoT, XML structuring,
Prompt caching, Structured outputs, Extended thinking

**Course coverage:**
- Session 4 → `04_prompt_caching.py` — prompt caching ✅
- Session 5 → `05_structured_output.py` — structured outputs ✅
- Session 1c → `1c_context_assembly.py` — context window composition ✅

**Gap:** No dedicated session on system prompt design, few-shot examples,
Chain-of-Thought prompting, XML structuring for Claude, or extended thinking.

**Suggested session:** New Session 2.5 — *Prompt Engineering Deep Dive*
- System prompt anatomy for Claude
- Few-shot + CoT patterns
- XML structuring (Claude-native)
- Extended thinking (claude-opus-4-7 budget_tokens)
- File: `02b_prompt_engineering.py`

---

### 03 — RAG Systems
**Roadmap topics:** Embeddings, Chunking, Reranking, Classic→Graph→Agentic RAG,
HyDE, Ragas

**Course coverage:**
- Session 9 → Files & Document AI, multimodal RAG ✅
- Session 11 → Hybrid RAG (dense + sparse + RRF) ✅
- Session 12 → GraphRAG ✅
- Session 13 → Corrective RAG (CRAG) ✅
- Session 14 → Ragas evaluation ✅

**Gap:** HyDE (Hypothetical Document Embeddings) and Agentic RAG not explicitly
covered as named patterns (though CRAG approaches it).

**Suggested addition:** Add HyDE to Session 11 or 13 as a retrieval variant.

---

### 04 — Agentic Systems
**Roadmap topics:** ReAct, Tool use, Multi-agent, Memory, MCP, SKILL.md,
Computer use, Coding agents

**Course coverage:**
- Session 1 → MCP ✅
- Session 1b → A2A Protocol ✅
- Session 1c → Context Assembly ✅
- Session 2 → Reflection + Plan-and-Execute (ReAct) ✅
- Session 3 → Multi-agent + Long-term/Episodic Memory ✅
- Session 6 → Claude Skills (SKILL.md) ✅
- `labs/coding_agent/` → Coding agent example ✅

**Gap:** Computer use (Anthropic Computer Use API) is in Track M Session 42
but not in the core agentic track.

**Suggested:** Promote Session 42 (Browser Automation) to Track A or add a
cross-reference so core-track learners discover it.

---

### 05 — AI Gateways & Routing
**Roadmap topics:** Model routing, Fallbacks, Cost tracking,
Multi-provider abstraction (LiteLLM, OpenRouter, portkey, Kong)

**Course coverage:**
- Session 8 → AI Gateway (LiteLLM / OpenRouter / Vercel AI Gateway) ✅

**Coverage is solid.** Add portkey and Kong as tool mentions if not present.

---

### 06 — Guardrails & Safety
**Roadmap topics:** Input/output validation, Prompt injection defense,
PII redaction, Jailbreak prevention, Hallucination detection
Tools: Guardrails AI, NeMo Guardrails

**Course coverage:**
- Session 10 (`10-guardrails.md`) → guardrails fundamentals ✅
- Session 19 → Red-teaming & Compliance ✅
- Session 20 → AI Governance & Audit ✅

**Gap:** No hands-on use of Guardrails AI library or NeMo Guardrails SDK.
Session 10 uses Claude's own mechanisms.

**Suggested addition:** Extend Session 10 or add Session 10b — integrate
`guardrails-ai` and `nemo_guardrails` libraries alongside Claude guardrails.

---

### 07 — Observability & Evals
**Roadmap topics:** Tracing, LLM-as-judge, Custom evals, Regression testing,
Drift detection
Tools: LangSmith, LangWatch, arize phoenix, Helicone, Langfuse

**Course coverage:**
- Session 14 → Evaluation (Ragas + LangSmith) ✅
- Session 17 → Production Deployment + Observability ✅

**Gap:** LangWatch, Arize Phoenix, Helicone, Langfuse not covered.
Drift detection not explicitly taught.

**Suggested addition:** Extend Session 14 to include one additional observability
platform (Langfuse is open-source, easy to self-host).

---

### 08 — Production AI Engineering
**Roadmap topics:** Streaming, Parallel tool calls, Retries, Rate limits,
Semantic caching, Cost optimization, Latency budgets
Tools: SSE, WebSockets

**Course coverage:**
- Session 15 → Cost Optimization ✅
- Session 16 → Streaming + Web UI (SSE) ✅
- Session 17 → Production Deployment ✅

**Gap:** Parallel tool calls and rate-limit retry logic not dedicated topics
(though used in multi-agent sessions). WebSockets covered in Session 16.

**Coverage is good.** Add parallel tool calls example to Session 3 or 15.

---

### 09 — Software Engineering Essentials
**Roadmap topics:** Python async, FastAPI, Git, Docker, Postgres + pgvector, Redis

**Course coverage:** Assumed background — no dedicated lab.
- `Dockerfile`, `docker-compose.yml` appear in Session 17 artifacts
- pgvector used in RAG sessions as a dependency

**Gap:** Learners without FastAPI/Docker background have no on-ramp.

**Suggested session:** New Session 0b — *Engineering Foundations for AI*
(optional, for non-backend engineers)
- Async Python patterns for LLM calls
- FastAPI route + Pydantic model for an AI endpoint
- Docker + docker-compose for a RAG stack
- Postgres + pgvector setup
- File: `00b_engineering_foundations.py`

---

### 10 — Inference & Deployment
**Roadmap topics:** Frontier APIs, Inference platforms, Cloud AI, Self-hosting
Tools: together.ai, replicate, fireworks, groq, cerebras, vLLM, ollama,
AWS Bedrock, Vertex AI, Azure AI

**Course coverage:**
- Session 17 → deployment (Fly.io, Docker) ✅
- `labs/ollama/` → local Ollama inference ✅
- Session 8 → multi-provider via LiteLLM (partial) 🟡

**Gap:** No dedicated session on inference platforms (together.ai, Replicate,
Fireworks, groq, cerebras), vLLM self-hosting, or managed cloud AI
(Bedrock, Vertex AI, Azure AI).

**Suggested session:** New Session 8b — *Inference Platforms & Self-Hosting*
- together.ai / groq / Fireworks API comparison
- vLLM local deployment
- AWS Bedrock vs Vertex AI vs Azure AI trade-offs
- Cost/latency benchmarks
- File: `08b_inference_platforms.py`

---

### 11 — Multimodal Integration
**Roadmap topics:** Vision, Image gen, Voice agents, Video gen, Document AI
Tools: NanoBanana, Flux, Eleven Labs, DALL-E, Sora, Veo, Runway

**Course coverage:**
- Session 9 → Vision + Document AI (Claude native, Files API, Citations API) ✅

**Gap:** Image generation, voice agents (TTS/STT), and video generation
are not covered. These require third-party APIs (Replicate for Flux/SDXL,
ElevenLabs for TTS, Whisper for STT).

**Suggested session:** New Session 9b — *Voice & Image Generation Agents*
- Whisper STT → Claude reasoning → ElevenLabs TTS pipeline
- Image generation via Replicate (Flux/SDXL) with Claude as director
- Document AI: extend Session 9 with multimodal RAG pipeline
- File: `09b_voice_image_agents.py`

---

### 12 — Ecosystem Fluency
**Roadmap topics:** Open models, Hugging Face, Papers, Benchmarks
Tools: Llama, Qwen, DeepSeek, Mistral, Kimi, HuggingFace, arXiv

**Course coverage:**
- `labs/ollama/` → runs Llama/Mistral locally ✅ (not in CURRICULUM.csv)
- `labs/openai/` → OpenAI parallel track ✅ (not in CURRICULUM.csv)

**Gap:** No session on reading papers (arXiv), using HuggingFace Hub
(model cards, inference API, datasets), or interpreting benchmarks.
Ollama and OpenAI tracks not surfaced in curriculum.

**Suggested session:** New Session 7b — *Open-Weight Models & HuggingFace Ecosystem*
- HuggingFace Hub: model cards, datasets, Spaces
- Running Llama/Mistral/Qwen via Ollama (link to labs/ollama/)
- Reading arXiv papers efficiently (abstract → method → results)
- Interpreting benchmarks: MMLU, HumanEval, LMSYS Arena, MTEB
- File: `07b_ecosystem_fluency.py`

---

### 13 — Career Compounding
**Roadmap topics:** Ship publicly, Open source, Write, Communities,
Build in public
Platforms: GitHub, LinkedIn, X (Twitter), Substack

**Course coverage:** None.

**Suggested session:** New Session 21b — *Shipping & Building in Public*
(lightweight, no code lab)
- How to document and open-source a course project
- Writing a technical post about a system you built
- GitHub README → LinkedIn post → Substack draft pipeline
- Contributing to open-source LLM tooling
- File: `21b_career_compounding.md` (essay-style, no code)

---

## Suggested New Sessions Summary

| New Session | Title | Fills Gap |
|---|---|---|
| 00 | LLM Internals & Model Selection | Category 01 |
| 00b | Engineering Foundations for AI | Category 09 |
| 02b | Prompt Engineering Deep Dive | Category 02 |
| 07b | Open-Weight Models & HuggingFace | Category 12 |
| 08b | Inference Platforms & Self-Hosting | Category 10 |
| 09b | Voice & Image Generation Agents | Category 11 |
| 21b | Shipping & Building in Public | Category 13 |

## Minor Additions (extend existing sessions)

| Session | Addition |
|---|---|
| S10 or S10b | Integrate `guardrails-ai` and `nemo_guardrails` libraries |
| S11 or S13 | Add HyDE retrieval pattern |
| S14 | Add Langfuse as second observability platform |
| S3 or S15 | Add parallel tool calls example |
| S8 | Add portkey and Kong as gateway mentions |

## Regrouped Track Structure (aligned to 2026 Roadmap)

```
Track 0 — Foundations (NEW)
  00  LLM Internals & Model Selection        [Roadmap 01]
  00b Engineering Foundations for AI         [Roadmap 09]  optional

Track A — Agentic Systems                    [Roadmap 04]
  1   MCP
  1b  A2A Protocol
  1c  Context Assembly
  2   Reflection + Plan-and-Execute
  2b  Prompt Engineering Deep Dive (NEW)     [Roadmap 02]
  3   Multi-agent + Memory

Track B — RAG Systems                        [Roadmap 03]
  9   Files & Document AI
  9b  Voice & Image Gen Agents (NEW)         [Roadmap 11]
  11  Hybrid RAG
  12  GraphRAG
  13  Corrective RAG

Track C — Infrastructure & Routing           [Roadmap 05, 09, 10]
  7   Anthropic SDK / Claude Agent SDK
  7b  Open-Weight Models & HuggingFace (NEW) [Roadmap 12]
  8   AI Gateway
  8b  Inference Platforms & Self-Hosting(NEW) [Roadmap 10]

Track D — Workflow & Skill                   [Roadmap 04]
  4   Spec-Driven Development
  5   Vibe Coding
  6   Claude Skills

Track E — Safety & Governance                [Roadmap 06]
  10  Guardrails (+ library extensions)
  19  Red-teaming & Compliance
  20  AI Governance & Audit

Track F — Production                         [Roadmap 07, 08]
  14  Evaluation (Ragas + LangSmith)
  15  Cost Optimization
  16  Streaming + Web UI
  17  Production Deployment + Observability
  17b IAM & Auth

Track G — Architect Skills                   [all]
  18  System Design Interview
  21  AI Product & UX Patterns
  21b Shipping & Building in Public (NEW)    [Roadmap 13]

Track H–L — Verticals (Healthcare, Agritech, Finance, Vidya Karana, Family AI)

Track M — Claude Code Mastery (Optional)
```
