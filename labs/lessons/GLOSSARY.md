# Glossary — terms and acronyms

> Comprehensive reference for every term and acronym used in AgenticCourse. Cross-referenced to the lesson where each term was introduced or covered in depth. Use this as a quick-lookup sheet during the course or as standalone reference material.

---

## How to use this glossary

- **Alphabetical within each section.** Sections are organized by topic area.
- **Each entry has:** one-line definition + cross-reference to the deepest lesson coverage (when applicable).
- **Acronyms** appear at their expansion (e.g., LCEL → "LangChain Expression Language"), with a one-line pointer at the acronym itself.
- **`→ Session N`** = covered in [Lesson N](.) (e.g., `→ Session 9` = [09-rag.md](09-rag.md)).

---

## A — Anthropic SDK, Agents, API

**Agent.** An LLM augmented with tools and a loop: think → call tool → observe result → think again. The simplest implementation is the ReAct pattern. → Session 3

**Agentic AI.** Systems where an LLM plans and executes multi-step work autonomously, using tools and memory rather than producing a single response. The umbrella concept the course is built around.

**`@app.middleware("http")`.** FastAPI decorator for HTTP middleware — runs before/after every request. Used in Session 17 to inject request IDs into the trace context. → Session 17

**Anthropic SDK.** The official Python client for Claude (`anthropic.Anthropic()`). Lower-level than LangChain's `ChatAnthropic`; exposes raw `usage`, streaming events, batches API. → Session 7

**`anthropic.AsyncAnthropic`.** Async variant of the client; uses async httpx under the hood. Use with `async def` FastAPI routes to avoid blocking the event loop.

**API Gateway.** Front door for an HTTP service — handles auth, rate limiting, TLS, routing. In production LLM systems, the gateway also injects the API key to upstream LLM providers so users never hold it.

**Approval gate.** In agent systems, a pause that requires human confirmation before a tool call executes (especially destructive ones like shell commands or file writes). → Session 18 (in the Claude Code-like scenario)

**Async** (`async def`). Python coroutines that don't block the event loop. Required for high-concurrency FastAPI endpoints making LLM calls. → Session 17

**Audit log.** Structured per-interaction log with fields like `request_id`, `policy_violations`, `retention_until` — required for SOC 2 / GDPR / HIPAA. → Session 19

---

## B — Batches, BM25, Brainstorming

**Batches API.** Anthropic's asynchronous endpoint for non-realtime workloads — 50% discount, 24-hour SLA. Used for eval runs, bulk classification, offline summarization. → Session 15

**BM25 / Okapi BM25.** Classical lexical retrieval algorithm scoring documents by term frequency × inverse document frequency. Strong on exact-term queries; complements dense vector search. → Session 11

**`brainstorming` (superpowers skill).** A meta-skill in this development environment that gates implementation behind a design-approval step. Why every session starts with a "design proposal".

**BYOK** (Bring Your Own Key). Architecture where users supply their own LLM provider API key. Common in enterprise tiers for cost-control and procurement reasons.

---

## C — Cache, Claude, Compliance, Context

**Cache hit / cache read.** When a cached prompt prefix is reused on a subsequent request. Anthropic charges ~10% of the fresh input price for cache reads. → Session 4

**Cache write / cache creation.** The *first* time a prompt prefix is cached. Costs 25% MORE than fresh input — break-even after ~2 reuses. → Session 4

**`cache_control: {"type": "ephemeral"}`.** The marker on a content block that opts it into Anthropic's prompt cache. ~5 minute TTL (or 1h for an additional premium). → Session 4, 15

**CD / CI** (Continuous Delivery / Integration). Automated pipelines that build, test, and deploy code on every change. Session 14's eval harness is meant to run in CI. → Session 14, 17

**Chain.** In LangChain, a composition of runnables (`prompt | model | parser`). Built via LCEL (the pipe operator). → Session 2

**`ChatAnthropic`.** LangChain's wrapper around the Anthropic API. Use this in LCEL chains; use raw `anthropic.Anthropic()` when you need usage details for cost/cache instrumentation. → Session 1

**Checkpointer.** In LangGraph, the persistence layer that lets state survive across `.invoke()` calls. `MemorySaver` is the in-memory checkpointer used in the course. → Session 8

**Chunk.** A piece of text produced by a splitter (typically 200-1000 tokens). The atomic unit of retrieval in RAG. → Session 9

**Circuit breaker.** Production pattern: if downstream errors exceed a threshold, stop calling for a cooldown period to avoid cascading failure. Used in `LLM Gateway` patterns. → Session 18

**Claude.** Anthropic's LLM family. The course uses three: claude-sonnet-4-6, claude-haiku-4-5, claude-opus-4-7. Built by Anthropic; safety-trained via RLHF + Constitutional AI.

**Claude Agent SDK.** Anthropic's higher-level agent framework. Provides `query()`, `@tool` decorator, MCP server creation. → Session 7

**Claude Code.** Anthropic's official CLI coding agent — the environment this curriculum is being built in. → Session 18 (architectural design scenario)

**Claude Desktop.** GUI app for Claude (Mac/Windows). Consumes MCP servers for tools/resources. → Session 6

**Claude Skills.** The hand-authored procedural-memory primitive — SKILL.md files in `labs/skills/`. Triggered by description-match. → Session 17 (deploy-time), Session 17.5 (runtime learning)

**CLI** (Command Line Interface). Text-based interface for running tools. Claude Code, Cursor's command palette, and most dev tools have one.

**Compliance.** Regulatory frameworks AI systems must follow: SOC 2, GDPR, HIPAA, EU AI Act, NIST AI RMF, ISO 42001. → Session 19

**Constitutional AI.** Anthropic's RLHF approach where the model critiques its own outputs against a "constitution" of principles. Why Claude refuses many attacks out of the box. → Session 19 (background)

**Context window.** The maximum tokens the model can attend to in one call. Sonnet 4.6 standard: 200K; with 1M context: 1M (used in this conversation).

**Counter** (Prometheus). Monotonically increasing metric (requests, errors, cumulative cost). Rate computed at query time. → Session 17

**CRAG** (Corrective RAG). Retrieve → grade → {use chunks | rewrite query | web fallback}. → Session 13

**`create_react_agent`.** LangGraph helper that builds a ReAct-style agent from a model + tools. → Session 3 (deprecated in V1.0; renamed `create_agent` in `langchain.agents`)

**Cross-encoder.** A reranker model that scores (query, document) pairs by joint encoding. Used after retrieval for an additional 5-10% quality boost. Mentioned in Session 11 as production follow-up.

---

## D — Deploy, Distributed, Docker

**Decode.** The token-by-token generation phase of an LLM call. Happens after prefill. Streaming exposes each decode step as a delta. → Session 16

**Defense in depth.** Layered security — multiple independent controls so that any single one failing doesn't compromise the system. → Session 19

**Dense retrieval.** Vector-similarity search over embeddings. Strong on semantic paraphrase; weaker on exact terms than BM25. → Session 9, 11

**`DiGraph`** (NetworkX). Directed graph data structure. Used in Session 12 for the knowledge graph. → Session 12

**Distributed tracing.** Cross-service request correlation via `trace_id`. OpenTelemetry is the standard. → Session 17

**Docker.** Container runtime. The course's deploy artifact is a multi-stage Dockerfile producing a ~150MB image. → Session 17

**DSAR** (Data Subject Access Request). GDPR mechanism for users to request, see, or delete their data. Requires per-field retention policies in audit logs. → Session 19

**Dunder method.** Python "double underscore" methods (`__init__`, `__call__`, etc.). Mentioned occasionally; not a teaching topic in this course.

---

## E — Embeddings, Episodic, Eval, EU AI Act

**Eject** (related to "eviction"). When working memory exceeds a token budget, the FIFO eviction policy drops oldest turns. → Session 17.5

**Embedding.** A dense vector representation of text (typically 384-1536 dims). Produced by a model like `sentence-transformers/all-MiniLM-L6-v2` (384 dims). → Session 9

**Episodic memory.** Vector store of past interactions with timestamps + outcome ratings. "What we did together." → Session 3 (extended), 17.5

**Eval / Evaluation.** Measuring system quality against a golden dataset using metrics (faithfulness, answer relevance, context precision, context recall). → Session 14

**EU AI Act.** EU regulation in effect 2026 covering risk-classified AI systems. Requires transparency, human oversight, conformity assessment. → Session 19

**Eviction.** Removing items from memory to free space. FIFO, LRU, importance-weighted, LLM-judged are the four common policies. → Session 17.5

---

## F — FastAPI, FAISS, Faithfulness, FIFO

**Faithfulness.** RAG eval metric: does every claim in the answer appear in the retrieved context? 1.0 = fully grounded, 0.0 = hallucinated. → Session 14

**FAISS.** Facebook AI Similarity Search — high-performance vector index library. Used in Session 18's Claude Code-style architecture for local code embedding search.

**FastAPI.** Modern Python web framework — async, OpenAPI docs out of the box, Pydantic-native. Used for the production service in Session 17. → Session 17

**Fast mode** (Claude Code). Toggle that switches Claude Code to a faster output mode using Opus 4.6. Toggled with `/fast`.

**FastMCP.** Python framework for building MCP servers — handles the JSON-RPC protocol details so you write Python decorators. → Session 6

**Few-shot.** Prompting technique that includes a few input/output examples in the prompt to teach format/style. Reduces but doesn't eliminate the need for fine-tuning.

**FIFO** (First-In-First-Out). Queue discipline. The default working-memory eviction policy — drop oldest turn when over budget. → Session 17.5

**Fine-tuning.** Training a base model on labeled task-specific examples. Not covered in the course; mentioned as an alternative to prompting in cost-conscious scenarios.

**Fly.io.** Container PaaS used for the deploy example. Scale-to-zero, region-pinned, $0 idle. → Session 17

---

## G — Gateway, Garak, GDPR, GraphRAG

**Garak.** Open-source LLM vulnerability scanner. Production-grade attack catalog vs the 12-attack demo in Session 19. → Session 19 (production swap)

**Gateway.** See **API Gateway** and **LLM Gateway**.

**Gauge** (Prometheus). Metric that goes up and down (active sessions, queue depth). Different from Counter (only up). → Session 17

**GDPR** (General Data Protection Regulation). EU privacy law. Key requirements: consent, right to erasure (DSAR), data minimization, retention policies. → Session 19

**Golden dataset.** Hand-curated question/answer pairs used as ground truth in eval. → Session 14

**GraphRAG.** Extract entities + relationships from a corpus into a knowledge graph; traverse the graph at query time. → Session 12

**Grafana.** Open-source dashboards for metrics. Pairs with Prometheus / Loki. → Session 17

**Guardrails.** Input/output filters that block policy violations. Different from "safety training" — guardrails are runtime, training is offline. → Session 10, 19

---

## H — Haiku, Hallucination, Hierarchical, HIPAA, Histogram

**Haiku.** The smallest, cheapest, fastest tier in the Claude family. `claude-haiku-4-5-20251001` is the default for graders, classifiers, structured extraction. → Session 15

**Hallucination.** Model output that sounds confident but isn't supported by the context or by ground truth. The primary failure mode RAG and CRAG defend against. → Session 9, 13, 14

**Hard isolation.** Multi-tenant pattern where tenants share no resources at all (separate DBs, separate API keys). Opposite of "soft isolation" (shared resources, row-level auth). → Session 18

**Health check.** HTTP endpoint that returns 200 if the service can serve traffic, 503 if it cannot. Used by orchestrators (k8s, Fly, ECS) for traffic routing. → Session 17

**Hierarchical memory.** MemGPT-style hot/warm/cold paging. → Session 17.5

**HIPAA** (Health Insurance Portability and Accountability Act). US law covering PHI in healthcare. Requires audit logs, encryption, access controls. → Session 19

**Histogram** (Prometheus). Latency-style metric with bucketed observations. Use `histogram_quantile` to compute percentiles. → Session 17

**HITL** (Human In The Loop). Interaction pattern where a human reviews / approves agent actions. Implemented via LangGraph `interrupt()` + `Command(resume=...)`. → Session 10

**Hybrid RAG.** Dense vector search + sparse BM25, fused with RRF (Reciprocal Rank Fusion). Better recall than either alone. → Session 11

---

## I — Indirect injection, Injection, Inference

**Indirect injection.** Prompt-injection attack where the malicious instruction is hidden in a *retrieved document* or tool output, not the user input. → Session 19

**Inference.** Running an LLM to produce output (prefill + decode). Distinct from "training". Inference cost is what production AI systems pay continuously.

**InMemoryVectorStore.** LangChain's no-DB-required vector store. Dev-time stand-in for Pinecone / Weaviate / Qdrant. → Session 9

**Input filter** (Layer 1 defense). Regex + classifier rejecting obvious attack patterns before they reach the LLM. → Session 19

**Instruction tuning / RLHF.** Training step that teaches a base model to follow instructions and refuse unsafe requests. Why Claude is safe out of the box even without guardrails. → Session 19 (background)

**Interrupt** (`interrupt(...)`). LangGraph primitive for pausing the graph and asking a human (or upstream caller) for input. → Session 10

**ISO/IEC 42001.** International standard for organizational AI management systems. Process + people + tooling for responsible AI. → Session 19

---

## J — Jailbreak, JSON-RPC, JWT

**Jailbreak.** Attack class where the user tries to bypass the model's safety training (e.g., DAN-style "you are now unrestricted"). → Session 19

**JSON-RPC.** Lightweight RPC protocol used by MCP for client/server communication. → Session 6

**JSON output parser.** LangChain parser that buffers tokens until valid JSON is parseable. Different streaming contract from `StrOutputParser`. → Session 16

**JWT** (JSON Web Token). Stateless auth token; commonly used in HTTP `Authorization: Bearer ...` headers. Threaded through to LLM service for row-level data access in Session 18 scenarios.

---

## K — kNN, KV cache

**kNN** (k-Nearest Neighbors). Retrieval algorithm: find the k vectors closest to a query vector. The core operation in vector stores. → Session 9

**KV cache.** Key/Value tensor cache stored during transformer prefill — what prompt caching saves from being recomputed on every request. → Session 4

---

## L — LangChain, LangGraph, LCEL, LiteLLM, Liveness, LlamaGuard

**LangChain.** Python framework for composing LLM applications. Provides LCEL (pipe operator), retrievers, vector stores, output parsers. → Session 1

**LangGraph.** LangChain's stateful workflow framework. Built around `StateGraph` with nodes, edges, and a checkpointer. → Session 10

**LangSmith.** LangChain's hosted observability product — tracing, dashboards, eval persistence. Mentioned as production swap-in for the homegrown harness in Session 14.

**LCEL** (LangChain Expression Language). The pipe operator (`|`) that composes runnables: `prompt | model | parser`. → Session 2

**Likelihood × Impact.** Two-axis risk classification used in red-team risk registers. Cheap mitigations for low-impact risks waste effort; expensive ones for high-impact risks pay off. → Session 19

**LiteLLM.** Unified Python interface for 100+ LLM providers. Supports fallback chains, cost tracking, OpenAI-compatible interface for Claude/Bedrock/Gemini/etc. → Session 8

**Liveness probe.** Health-check variant — *"is the process alive?"* If liveness fails, the orchestrator kills + restarts the pod. → Session 17

**LlamaGuard.** Meta's purpose-built safety classifier model. Production swap-in for the LLM-as-judge output validator. → Session 19

**LLM** (Large Language Model). Transformer-based neural net trained on text. The course uses Claude (claude-sonnet-4-6, claude-haiku-4-5, claude-opus-4-7).

**LLM-as-judge.** Use an LLM to score outputs (quality metrics, attack-success judgment, output validation). → Session 14, 19

**LLM Gateway.** Thin proxy in front of an LLM provider — handles auth injection, model routing, retries, circuit-breaking, request logging. → Session 18

**Loki.** Grafana's logs store — log aggregation, indexed by labels. Pairs with structured JSON logs. → Session 17

**LTM** (Long-Term Memory). Memory that persists across sessions. Includes semantic LTM (user facts) and episodic LTM (past conversations). → Session 3, 17.5

---

## M — MCP, MemorySaver, Metrics, Model card, Multi-tenant

**MAU** (Monthly Active Users). Standard scale metric. Used in back-of-envelope cost math in Session 18.

**MCP** (Model Context Protocol). Open protocol for LLMs to discover and call tools / resources via JSON-RPC. Used by Claude Desktop and Claude Code. → Session 6

**MemGPT.** Academic paper introducing hierarchical agent memory with OS-style hot/warm/cold paging. → Session 17.5

**MemorySaver.** LangGraph's in-memory checkpointer. Production-replace with `PostgresSaver` or `SqliteSaver`. → Session 8

**Metrics.** Numeric observations exported for monitoring. Prometheus exposition format is the standard. → Session 17

**Middleware.** Code that runs before/after request handlers. FastAPI's `@app.middleware("http")` decorator is where you inject request IDs, auth checks, structured logs. → Session 17

**MiniLM.** `sentence-transformers/all-MiniLM-L6-v2` — small (384-dim) open-source embedding model used throughout the course's RAG demos. → Session 9

**Model card.** Structured transparency artifact: purpose, capabilities, limitations, known failure modes, mitigations, eval metrics. Required for SOC 2 / EU AI Act audits. → Session 19

**Multi-agent.** Architecture where multiple specialized agents coordinate (supervisor + workers). → Session 3

**Multi-modal.** Models / pipelines that handle text + images + audio in a unified way. Claude is natively multi-modal for text + images + PDFs. → Session 9

**Multi-tenant.** Architecture serving many customers from shared infrastructure with isolation between tenants. → Session 18

---

## N — NeMo Guardrails, NetworkX, NIST AI RMF

**NeMo Guardrails.** NVIDIA's purpose-built guardrails framework with pre-trained safety classifiers. Production swap for LLM-as-judge validation. → Session 19

**NetworkX.** Python library for graphs — dev-time stand-in for Neo4j / Memgraph / Kuzu. Used in Session 12's GraphRAG demo. → Session 12

**NIST AI RMF** (AI Risk Management Framework). US National Institute of Standards risk-management methodology for AI systems. Recommended baseline for US-government-adjacent work. → Session 19

---

## O — OAuth2, Observability, OpenAPI, OpenTelemetry, Output parser

**OAuth2.** Standard for delegated authorization (used for JWTs in many SaaS contexts). Mentioned in Session 18 scenarios.

**Observability.** The discipline of making system behavior visible via logs + metrics + traces. → Session 17

**OpenAPI.** Specification format for HTTP APIs. FastAPI generates one automatically. → Session 17

**OpenTelemetry / OTel.** Vendor-neutral spec + library for traces + metrics + logs. The standard for distributed observability in 2026. → Session 17

**Opus.** The largest, smartest, most expensive tier in the Claude family. `claude-opus-4-7` is what's powering this conversation.

**Orchestrator.** In agent architectures, the component that classifies intent and routes to RAG / tools / direct LLM / escalation. → Session 18

**Output parser.** LangChain primitive that converts LLM text output into structured data. `StrOutputParser`, `JsonOutputParser`, Pydantic schemas via `with_structured_output`. → Session 5, 7

**Output validator** (Layer 3 defense). LLM-as-judge that scans response text for policy violations (PII, prompt leak, refusal bypass) before delivery. → Session 19

**OWASP Top 10.** Industry-standard list of web app vulnerabilities. The "for LLMs" variant adds prompt injection, training data poisoning, etc.

---

## P — p95, PII, Pinecone, Prometheus, Prompt, Procedural

**p50 / p95 / p99.** Latency percentiles. p95 = "95% of requests are faster than this". Industry-standard latency SLOs are stated at p95 or p99.

**Page in / page out** (memory). Move an item from cold/warm tier to hot tier (page in), or from hot to warm/cold (page out). MemGPT pattern. → Session 17.5

**PHI** (Protected Health Information). HIPAA-regulated category — patient names, conditions, treatments. Must be encrypted at rest + in transit + scrubbed from logs. → Session 19

**PII** (Personally Identifiable Information). Email, SSN, phone, account ID. Must be scrubbed from logs, minimized in context, never disclosed without consent. → Session 19

**Pinecone.** Managed vector database. Production swap for `InMemoryVectorStore`. Mentioned in Session 18 scenarios.

**Pipe operator** (`|`). LCEL composition operator. `prompt | model | parser` chains the three together. → Session 2

**Presidio.** Microsoft's PII detection + anonymization library. Production swap for regex-based input filtering. → Session 19

**Prefill.** First phase of LLM inference: read the prompt and build the KV cache. Doesn't stream — TTFT is dominated by prefill duration on long contexts. → Session 16

**Procedural memory.** Skill library: learned workflows and tool sequences. → Session 17 (Claude Skills as deploy-time procedural memory), 17.5 (runtime learning loop)

**Prometheus.** Open-source metrics system. Pull-model scraping of `/metrics` endpoint in exposition format. → Session 17

**`prompt`.** The input message(s) to an LLM call. Composed of system + user + (optionally) prior assistant turns.

**Prompt caching.** Anthropic's mechanism for reusing the KV cache server-side across requests with the same prefix. → Session 4

**Prompt compression.** Removing redundant tokens from prompts (verbose system prompts → compact) for cost reduction. → Session 15

**Prompt injection.** Attack where the user input contains instructions that override the system prompt ("ignore the above and..."). → Session 19

**`promptfoo`.** Open-source prompt-testing tool, including adversarial test suites. → Session 19

**Pydantic.** Python data validation library. `BaseModel`, `Field`, `Literal[...]` are the primitives the course uses constantly for structured output. → Session 5

**`PyRIT`.** Microsoft's Python Risk Identification Toolkit for adversarial AI testing. Production-grade attack catalog. → Session 19

---

## Q — Query rewriter, QPS

**QPS** (Queries Per Second). Throughput unit. The standard capacity number in system design.

**Query rewriter.** In CRAG, the LLM call that rewrites a user query to be more retrieval-friendly when the grader marks results "ambiguous". → Session 13

---

## R — RAG, Ragas, ReAct, Readiness, Redis, Reflection, Request ID, RLHF, RRF

**RAG** (Retrieval-Augmented Generation). Retrieve relevant chunks from a corpus, feed them to an LLM as context, generate a grounded answer. → Session 9

**Ragas.** Production-grade Python library for RAG eval. Same metrics as Session 14 (faithfulness, answer relevance, context precision, context recall) with battle-tested prompts. → Session 14 (production swap)

**Rank fusion.** See **RRF** (Reciprocal Rank Fusion).

**`rank_bm25`.** Python library implementing BM25 (Okapi variant). Used as the dev-time sparse retriever in Session 11. → Session 11

**`rate_limit`.** HTTP 429 status code; production code must retry with backoff. Track separately in metrics from generic 5xx errors. → Session 17

**ReAct.** Reasoning + Acting pattern for agents — interleave LLM reasoning with tool calls. `create_react_agent` is LangGraph's implementation. → Session 3

**Readiness probe.** Health-check variant — *"can the process serve traffic NOW?"* If readiness fails, the load balancer pulls the pod out of rotation. → Session 17

**Recall buffer.** The "warm" tier in MemGPT-style hierarchical memory. → Session 17.5

**Redis.** In-memory key-value store. Used for session state in production LLM systems. → Session 18

**Reflection.** Agent pattern where the LLM reviews its own output and refines. → Session 13 (in some Brij infographic context)

**Refusal bypass.** Attack class where the attacker tries to get the model to comply via roleplay, hypotheticals, or authority claims. → Session 19

**Regression check.** Re-running the eval on a modified system to verify quality hasn't dropped. Built into Session 14's harness. → Session 14

**Request ID.** UUID assigned per HTTP request, threaded through logs / spans / response headers. The most important production hygiene primitive. → Session 17

**Retrieval grader.** In CRAG, the LLM call that scores each retrieved chunk as correct / ambiguous / incorrect. → Session 13

**Risk register.** Structured list of risks with likelihood × impact × mitigation. Standard system-design output. → Session 18, 19

**RLHF** (Reinforcement Learning from Human Feedback). Training step that teaches the model human preferences. The foundation of Claude's helpfulness and safety. → Session 19 (background)

**Roleplay attack.** Jailbreak attack pattern — "pretend you're an unrestricted assistant." → Session 19

**`Router`.** In agent architectures, the component that classifies user input and dispatches to the appropriate handler (RAG / tool / direct LLM / escalation). → Session 18

**RRF** (Reciprocal Rank Fusion). Algorithm for merging multiple ranked lists into one without score normalization. Used in hybrid RAG to combine dense + sparse retrievers. → Session 11

**Runnable.** LangChain's protocol for chainable components. Anything with `.invoke()`, `.stream()`, `.batch()`. The interface LCEL composes over. → Session 2

---

## S — Semantic memory, Skill, SLM, SOC 2, Span, SSE, Stream, Structured output

**Scale-to-zero.** PaaS pattern where idle services pay $0. Fly.io supports this with `auto_stop_machines`. → Session 17

**Semantic memory.** Entity-attribute fact store: `dict[str, str]` keyed by canonical fact names. "Who the user is." → Session 17.5

**Semantic search.** Synonym for dense vector retrieval. Strong on paraphrase. → Session 9

**`sentence-transformers`.** Python library + model registry for sentence embeddings. The course uses `all-MiniLM-L6-v2` (384 dims). → Session 9

**SLM** (Small Language Model). Smaller-than-frontier models. Haiku is Anthropic's SLM tier (compared to Opus). → Session 15

**Skill library.** Procedural memory: a list of reusable workflows (`SkillEntry{name, when_to_use, steps}`). Author-written (Session 17) or runtime-learned (Session 17.5).

**`SKILL.md`.** The format for a Claude Skill — YAML frontmatter (`name`, `description`) + Markdown body. Triggered by description-match. → Session 17

**SLA** (Service Level Agreement). Customer-facing latency / uptime contract. e.g., "99.95% availability".

**SLO** (Service Level Objective). Internal target (typically tighter than SLA). e.g., "p95 < 800ms" so we have headroom before breaching SLA.

**SOC 2.** AICPA audit framework for B2B SaaS. Type II = audited over a 6-12 month period. Common procurement requirement. → Session 19

**Sonnet.** The mid-tier Claude model — balanced cost/quality. `claude-sonnet-4-6` is the course default. → Session 1

**Span.** Unit of distributed tracing — a named operation with start/end timestamps + arbitrary tags. Spans nest into traces. → Session 17

**Sparse retrieval.** Lexical / keyword-based retrieval (BM25). Opposite of dense (semantic). → Session 11

**`spawn` / subagent.** Dispatching a specialized agent for a focused task (Explore, Plan, Code Reviewer, etc.). Returns a single result that the parent absorbs.

**SQLite.** Embedded relational DB. Used in Session 18's Claude Code-style architecture for local session/state persistence.

**SSE** (Server-Sent Events). One-way HTTP streaming protocol — `text/event-stream` content type, `data: {...}\n\n` line format. The default for streaming chat UIs. → Session 16, 17

**SSN.** Social Security Number — high-sensitivity PII. The course's red-team demos use it as the canonical "never disclose" field. → Session 19

**`StateGraph`.** LangGraph's primary class. Define nodes, edges, conditional edges, then `.compile()`. → Session 10

**Stop reason.** Anthropic API field on a Message indicating why generation ended: `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`. → Session 7

**`StrOutputParser`.** LangChain parser that passes string chunks through unchanged. Streams cleanly. → Session 2, 16

**Stream / Streaming.** Yielding response tokens as they're generated, instead of waiting for the full response. The UX feature that makes 4-second responses feel instant. → Session 16

**`stream_mode`.** LangGraph parameter for `.stream()`: `values` (full state per node), `updates` (per-node diff), `messages` (token-level deltas). → Session 16

**Structured output.** LLM responses constrained to a Pydantic schema via `with_structured_output(MyModel)`. → Session 5

**Subagent.** See **`spawn`**.

**Supervisor pattern.** Multi-agent pattern where a supervisor LLM routes tasks to specialist workers. → Session 3

---

## T — Tavily, TestClient, Token, Tool, Tool router, Tracing, Trade-off, TTFT, TTL, Tree-sitter

**Tavily.** Hosted search API purpose-built for LLM grounding. Production swap for the web-fallback stub in Session 13. → Session 13 (production swap)

**`TestClient`** (Starlette / FastAPI). In-process HTTP client for testing without binding a port. Used in Session 17's demo. → Session 17

**Token.** The atomic unit of LLM input/output — roughly a syllable or short word. Pricing is per million tokens. → Session 4

**Tool call.** When the LLM emits a `tool_use` content block requesting a function invocation. The agent loop intercepts, runs the function, returns the result, and the LLM continues. → Session 3, 7

**Tool router.** Component that dispatches tool calls from the LLM to the right handler (local function, remote API, MCP server). → Session 18

**Trace / `trace_id`.** A trace is a tree of spans across services. The `trace_id` correlates them. → Session 17

**Trade-off.** Named design decision with 2-3 options and a recommendation. The unit of senior-IC signal in system design interviews. → Session 18

**Tree-sitter.** Multi-language AST parser. Used in Session 18's Claude Code scenario for chunking code at function/class boundaries. → Session 18

**TTFT** (Time To First Token). Latency from request submission to first streamed delta. The UX-relevant latency, not total. → Session 16

**TTL** (Time To Live). Cache / session expiry duration. Anthropic prompt cache default TTL is ~5 minutes; 1-hour TTL is also available. → Session 4

---

## U — UUID, Uvicorn

**UUID.** Universally unique identifier — used for request IDs, session IDs, span IDs. → Session 17

**Uvicorn.** ASGI server that runs FastAPI apps. The deploy command is `uvicorn <module>:app --host 0.0.0.0 --port 8000`. → Session 17

---

## V — Validation, Vector store, Vibe coding

**Validation.** Output gating to enforce policy (no PII, no prompt leak). Implemented as LLM-as-judge in Session 19's Layer 3. → Session 19

**Vector store.** Database optimized for kNN queries on embeddings. `InMemoryVectorStore` is dev-time; Pinecone / Weaviate / Qdrant / pgvector are production. → Session 9

**Vibe coding.** Anthropic's term for writing prompts that *describe* what you want; the LLM fills in the code. → Session 5 (vibe coding session)

---

## W — Working memory, with_structured_output

**`with_structured_output(MyModel)`.** LangChain wrapper that returns a runnable producing instances of a Pydantic model. The course's go-to for type-safe LLM output. → Session 5

**Working memory.** The conversation history visible to the LLM in the current call. FIFO eviction at a token budget keeps it bounded. → Session 8 (MemorySaver), 17.5 (FIFO)

---

## X — XML tags

**XML tags** (`<user_input>...</user_input>`). Structural boundary marker in prompts. Tells the LLM "this is data, not instructions". Defense Layer 2 in Session 19. → Session 19

---

## Y — YAML

**YAML frontmatter.** The metadata block at the top of `SKILL.md` files (`name`, `description`). → Session 17

---

## Z — Zero-shot

**Zero-shot.** Prompting without providing examples. Modern frontier models do well zero-shot on most tasks. The opposite of few-shot.

---

## Models in use across the course

| Model | Tier | When used |
|---|---|---|
| `claude-opus-4-7` | Most capable | The model powering this conversation; for "max capability needed" |
| `claude-sonnet-4-6` | Balanced | Default for all course labs (chains, RAG, agents) |
| `claude-haiku-4-5-20251001` | Fastest, cheapest | Graders, classifiers, validators, output judges |
| `sentence-transformers/all-MiniLM-L6-v2` | Local embedding | 384-dim text embeddings throughout RAG demos |

---

## Sessions index (where things were introduced)

| # | Session | Lesson file |
|---|---|---|
| 1 | Model wrapper, ChatAnthropic | [01-model-wrapper.md](01-model-wrapper.md) |
| 2 | LCEL composition, pipe operator | [02-lcel-composition.md](02-lcel-composition.md) |
| 3 | Agent tool loop, ReAct, multi-agent + LTM | [03-agent-tool-loop.md](03-agent-tool-loop.md), [14-multi-agent-ltm.md](14-multi-agent-ltm.md) |
| 4 | Prompt caching, KV cache | [04-prompt-caching.md](04-prompt-caching.md) |
| 5 | Structured output, Pydantic schemas, vibe coding | [05-structured-output.md](05-structured-output.md), [16-vibe-coding.md](16-vibe-coding.md) |
| 6 | Parallel chains, MCP | [06-parallel-chains.md](06-parallel-chains.md), [12-mcp.md](12-mcp.md) |
| 7 | Output parsers, Anthropic SDK, Claude Agent SDK | [07-output-parsers.md](07-output-parsers.md), [18-anthropic-sdk.md](18-anthropic-sdk.md) |
| 8 | Chatbot memory, MemorySaver | [08-chatbot-memory.md](08-chatbot-memory.md) |
| 9 | RAG, multimodal | [09-rag.md](09-rag.md), [20-files-document-ai.md](20-files-document-ai.md) |
| 10 | Guardrails, custom LangGraph + HITL | [10-guardrails.md](10-guardrails.md), [21-custom-langgraph.md](21-custom-langgraph.md) |
| 11 | Production capstone, Hybrid RAG | [11-production-capstone.md](11-production-capstone.md), [22-hybrid-rag.md](22-hybrid-rag.md) |
| 12 | GraphRAG | [23-graph-rag.md](23-graph-rag.md) |
| 13 | Corrective RAG | [24-corrective-rag.md](24-corrective-rag.md) |
| 14 | Evaluation (LLM-as-judge) | [25-evaluation.md](25-evaluation.md) |
| 15 | Cost optimization (4 levers) | [26-cost-optimization.md](26-cost-optimization.md) |
| 16 | Streaming | [27-streaming.md](27-streaming.md) |
| 17 | Production deploy + observability | [28-production-deploy.md](28-production-deploy.md) |
| 17.5 | Memory architectures (5-pattern survey) | [29-memory-architectures.md](29-memory-architectures.md) |
| 17 (bis) | Claude Skills, AI gateway, spec-driven, reflection/PE | [17-claude-skills.md](17-claude-skills.md), [19-ai-gateway.md](19-ai-gateway.md), [15-spec-driven-development.md](15-spec-driven-development.md), [13-reflection-plan-execute.md](13-reflection-plan-execute.md) |
| 18 | System design interview prep | [30-system-design.md](30-system-design.md) |
| 19 | Red-teaming & compliance | [31-red-teaming.md](31-red-teaming.md) |

---

## How this glossary stays current

When a new term is introduced in a session lesson:
1. Add an entry here (alphabetical within section).
2. Cross-reference the lesson (`→ Session N`).
3. Keep the definition to 1-3 sentences — this is a quick-lookup sheet, not a textbook.

Removing a term: if a session is removed or renamed, the cross-reference in this glossary becomes stale. Periodically grep for `→ Session N` and fix.
