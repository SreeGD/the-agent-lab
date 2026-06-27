# AI Engineer 2026 Roadmap → Course Mapping

Source: "How to Become an AI Engineer in 2026" by Brij Kishore Pandey (@brijpandeyji)

This document maps every category in the 2026 roadmap to existing course sessions,
calls out gaps, and lists suggested new sessions to fill them.

---

## Coverage Summary

| # | Roadmap Category | Status | Sessions |
|---|---|---|---|
| 01 | LLM Fundamentals | ✅ Covered | [S00 LLM Fundamentals](00-llm-fundamentals.md) |
| 02 | Prompt & Context Engineering | ✅ Covered | [S00](00-llm-fundamentals.md), [S02b Prompt Engineering](02b-prompt-engineering.md), [S04 Prompt Caching](04-prompt-caching.md), [S05 Structured Output](05-structured-output.md), [S1c Context Assembly](1c-context-assembly.md) |
| 03 | RAG Systems | ✅ Covered | [S09 RAG](09-rag.md), [S22 Hybrid RAG +HyDE](22-hybrid-rag.md), [S23 GraphRAG](23-graph-rag.md), [S24 Corrective RAG](24-corrective-rag.md) |
| 04 | Agentic Systems | ✅ Covered | [S12 MCP](12-mcp.md), [S12b A2A](12b-a2a-protocol.md), [S1c Context Assembly](1c-context-assembly.md), [S13 Reflection](13-reflection-plan-execute.md), [S14 Multi-agent](14-multi-agent-ltm.md), [S17 Claude Skills](17-claude-skills.md) |
| 05 | AI Gateways & Routing | ✅ Covered | [S19 AI Gateway +portkey +Kong](19-ai-gateway.md) |
| 06 | Guardrails & Safety | ✅ Covered | [S10 Guardrails +guardrails-ai +NeMo](10-guardrails.md), [S31 Red-teaming](31-red-teaming.md), [S32 Governance](32-governance.md) |
| 07 | Observability & Evals | ✅ Covered | [S25 Evaluation +Langfuse](25-evaluation.md), [S28 Production Deploy](28-production-deploy.md) |
| 08 | Production AI Engineering | ✅ Covered | [S26 Cost Optimization](26-cost-optimization.md), [S27 Streaming](27-streaming.md), [S28 Production Deploy](28-production-deploy.md) |
| 09 | Software Engineering Essentials | ✅ Covered | [S00b Engineering Foundations](00b-engineering-foundations.md) |
| 10 | Inference & Deployment | ✅ Covered | [S08b Inference Platforms](08b-inference-platforms.md), [S28 Production Deploy](28-production-deploy.md) |
| 11 | Multimodal Integration | ✅ Covered | [S20 Files & Document AI](20-files-document-ai.md), [S09b Voice & Image Agents](09b-voice-image-agents.md) |
| 12 | Ecosystem Fluency | ✅ Covered | [S07b Ecosystem Fluency](07b-ecosystem-fluency.md) |
| 13 | Career Compounding | ✅ Covered | [S21b Portfolio Generator](21b-portfolio-generator.md) |

---

## Detailed Mapping

### 01 — LLM Fundamentals
**Roadmap topics:** Transformers, Tokenization, Context windows, Sampling,
Reasoning models, Benchmarks

**Course coverage:**
- [`llm-api-internals.md`](llm-api-internals.md) — reference doc, not a lab session
- `labs/01_model_wrapper.py` — basic model invocation (no theory)
- [Session 00 — LLM Fundamentals](00-llm-fundamentals.md) ✅

**Status:** ✅ Covered by [Session 00 — LLM Fundamentals](00-llm-fundamentals.md)

---

### 02 — Prompt & Context Engineering
**Roadmap topics:** System prompts, Few-shot, CoT, XML structuring,
Prompt caching, Structured outputs, Extended thinking

**Course coverage:**
- Session 4 → [`04-prompt-caching.md`](04-prompt-caching.md) — prompt caching ✅
- Session 5 → [`05-structured-output.md`](05-structured-output.md) — structured outputs ✅
- Session 1c → [`1c-context-assembly.md`](1c-context-assembly.md) — context window composition ✅
- [Session 02b — Prompt Engineering Deep Dive](02b-prompt-engineering.md) ✅

**Status:** ✅ Covered

---

### 03 — RAG Systems
**Roadmap topics:** Embeddings, Chunking, Reranking, Classic→Graph→Agentic RAG,
HyDE, Ragas

**Course coverage:**
- Session 9 → [`09-rag.md`](09-rag.md) — Files & Document AI, multimodal RAG ✅
- Session 11 → [`22-hybrid-rag.md`](22-hybrid-rag.md) — Hybrid RAG (dense + sparse + RRF) ✅
- Session 12 → [`23-graph-rag.md`](23-graph-rag.md) — GraphRAG ✅
- Session 13 → [`24-corrective-rag.md`](24-corrective-rag.md) — Corrective RAG (CRAG) ✅
- Session 14 → [`25-evaluation.md`](25-evaluation.md) — Ragas evaluation ✅

**Status:** ✅ HyDE added to [22-hybrid-rag.md](22-hybrid-rag.md)

---

### 04 — Agentic Systems
**Roadmap topics:** ReAct, Tool use, Multi-agent, Memory, MCP, SKILL.md,
Computer use, Coding agents

**Course coverage:**
- Session 1 → [`12-mcp.md`](12-mcp.md) — MCP ✅
- Session 1b → [`12b-a2a-protocol.md`](12b-a2a-protocol.md) — A2A Protocol ✅
- Session 1c → [`1c-context-assembly.md`](1c-context-assembly.md) — Context Assembly ✅
- Session 2 → [`13-reflection-plan-execute.md`](13-reflection-plan-execute.md) — Reflection + Plan-and-Execute (ReAct) ✅
- Session 3 → [`14-multi-agent-ltm.md`](14-multi-agent-ltm.md) — Multi-agent + Long-term/Episodic Memory ✅
- Session 6 → [`17-claude-skills.md`](17-claude-skills.md) — Claude Skills (SKILL.md) ✅
- `labs/coding_agent/` → Coding agent example ✅

**Status:** ✅ Parallel tool calls added to [03-agent-tool-loop.md](03-agent-tool-loop.md)

---

### 05 — AI Gateways & Routing
**Roadmap topics:** Model routing, Fallbacks, Cost tracking,
Multi-provider abstraction (LiteLLM, OpenRouter, portkey, Kong)

**Course coverage:**
- Session 8 → [`19-ai-gateway.md`](19-ai-gateway.md) — AI Gateway (LiteLLM / OpenRouter / Vercel AI Gateway) ✅

**Status:** ✅ portkey and Kong added to [19-ai-gateway.md](19-ai-gateway.md)

---

### 06 — Guardrails & Safety
**Roadmap topics:** Input/output validation, Prompt injection defense,
PII redaction, Jailbreak prevention, Hallucination detection
Tools: Guardrails AI, NeMo Guardrails

**Course coverage:**
- Session 10 → [`10-guardrails.md`](10-guardrails.md) — guardrails fundamentals ✅
- Session 19 → [`31-red-teaming.md`](31-red-teaming.md) — Red-teaming & Compliance ✅
- Session 20 → [`32-governance.md`](32-governance.md) — AI Governance & Audit ✅

**Status:** ✅ guardrails-ai + NeMo Guardrails added to [10-guardrails.md](10-guardrails.md)

---

### 07 — Observability & Evals
**Roadmap topics:** Tracing, LLM-as-judge, Custom evals, Regression testing,
Drift detection
Tools: LangSmith, LangWatch, arize phoenix, Helicone, Langfuse

**Course coverage:**
- Session 14 → [`25-evaluation.md`](25-evaluation.md) — Evaluation (Ragas + LangSmith) ✅
- Session 17 → [`28-production-deploy.md`](28-production-deploy.md) — Production Deployment + Observability ✅

**Status:** ✅ Langfuse added to [25-evaluation.md](25-evaluation.md)

---

### 08 — Production AI Engineering
**Roadmap topics:** Streaming, Parallel tool calls, Retries, Rate limits,
Semantic caching, Cost optimization, Latency budgets
Tools: SSE, WebSockets

**Course coverage:**
- Session 15 → [`26-cost-optimization.md`](26-cost-optimization.md) — Cost Optimization ✅
- Session 16 → [`27-streaming.md`](27-streaming.md) — Streaming + Web UI (SSE) ✅
- Session 17 → [`28-production-deploy.md`](28-production-deploy.md) — Production Deployment ✅

**Status:** ✅ Parallel tool calls added to [03-agent-tool-loop.md](03-agent-tool-loop.md)

---

### 09 — Software Engineering Essentials
**Roadmap topics:** Python async, FastAPI, Git, Docker, Postgres + pgvector, Redis

**Course coverage:** Assumed background — no dedicated lab.
- `Dockerfile`, `docker-compose.yml` appear in Session 17 artifacts
- pgvector used in RAG sessions as a dependency

**Status:** ✅ Covered by [Session 00b — Engineering Foundations](00b-engineering-foundations.md)

---

### 10 — Inference & Deployment
**Roadmap topics:** Frontier APIs, Inference platforms, Cloud AI, Self-hosting
Tools: together.ai, replicate, fireworks, groq, cerebras, vLLM, ollama,
AWS Bedrock, Vertex AI, Azure AI

**Course coverage:**
- Session 17 → [`28-production-deploy.md`](28-production-deploy.md) — deployment (Fly.io, Docker) ✅
- `labs/ollama/` → local Ollama inference ✅
- Session 8 → multi-provider via LiteLLM (partial) 🟡

**Status:** ✅ Covered by [Session 08b — Inference Platforms](08b-inference-platforms.md)

---

### 11 — Multimodal Integration
**Roadmap topics:** Vision, Image gen, Voice agents, Video gen, Document AI
Tools: NanoBanana, Flux, Eleven Labs, DALL-E, Sora, Veo, Runway

**Course coverage:**
- Session 9 → [`20-files-document-ai.md`](20-files-document-ai.md) — Vision + Document AI (Claude native, Files API, Citations API) ✅

**Status:** ✅ Covered by [Session 09b — Voice & Image Agents](09b-voice-image-agents.md)

---

### 12 — Ecosystem Fluency
**Roadmap topics:** Open models, Hugging Face, Papers, Benchmarks
Tools: Llama, Qwen, DeepSeek, Mistral, Kimi, HuggingFace, arXiv

**Course coverage:**
- `labs/ollama/` → runs Llama/Mistral locally ✅ (not in CURRICULUM.csv)
- `labs/openai/` → OpenAI parallel track ✅ (not in CURRICULUM.csv)

**Status:** ✅ Covered by [Session 07b — Ecosystem Fluency](07b-ecosystem-fluency.md)

---

### 13 — Career Compounding
**Roadmap topics:** Ship publicly, Open source, Write, Communities,
Build in public
Platforms: GitHub, LinkedIn, X (Twitter), Substack

**Course coverage:** None.

**Status:** ✅ Covered by [Session 21b — Portfolio Generator](21b-portfolio-generator.md)

---

## Suggested New Sessions Summary

| New Session | Title | Fills Gap |
|---|---|---|
| [00](00-llm-fundamentals.md) | LLM Internals & Model Selection | Category 01 |
| [00b](00b-engineering-foundations.md) | Engineering Foundations for AI | Category 09 |
| [02b](02b-prompt-engineering.md) | Prompt Engineering Deep Dive | Category 02 |
| [07b](07b-ecosystem-fluency.md) | Open-Weight Models & HuggingFace | Category 12 |
| [08b](08b-inference-platforms.md) | Inference Platforms & Self-Hosting | Category 10 |
| [09b](09b-voice-image-agents.md) | Voice & Image Generation Agents | Category 11 |
| [21b](21b-portfolio-generator.md) | Shipping & Building in Public | Category 13 |

## Minor Additions (extend existing sessions)

| Session | Addition |
|---|---|
| [S10](10-guardrails.md) or S10b | Integrate `guardrails-ai` and `nemo_guardrails` libraries |
| [S22](22-hybrid-rag.md) | Add HyDE retrieval pattern |
| [S25](25-evaluation.md) | Add Langfuse as second observability platform |
| [S03](03-agent-tool-loop.md) or S15 | Add parallel tool calls example |
| [S19](19-ai-gateway.md) | Add portkey and Kong as gateway mentions |

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

---

## Implementation Complete

As of 2026-06-27, all 13 roadmap categories are covered by this curriculum.

**New sessions added:**
- Session 00: LLM Internals & Model Selection
- Session 00b: Engineering Foundations for AI (optional on-ramp)
- Session 02b: Prompt Engineering Deep Dive
- Session 07b: Open-Weight Models & HuggingFace Ecosystem
- Session 08b: Inference Platforms & Self-Hosting
- Session 09b: Voice & Image Generation Agents
- Session 21b: Portfolio Generator (Shipping & Building in Public)

**Minor additions to existing sessions:**
- Session 10: guardrails-ai + NeMo Guardrails integration
- Session 22: HyDE (Hypothetical Document Embeddings) retrieval pattern
- Session 25: Langfuse observability tracing
- Session 03: Parallel tool call dispatch with asyncio
- Session 19: portkey + Kong API Gateway mentions
