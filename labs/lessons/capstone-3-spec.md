# Project Specification
## Capstone 3 — Production-Grade Context Intelligence Platform

**Course:** AgenticCourse — Enterprise AI Architecture
**Phase:** Capstone (after L28 + Enterprise Hardening modules)
**Estimated effort:** 12–16 hours
**Prerequisite:** Capstone 1 (CLI Coding Agent), Capstone 2 (Financial Research Agent)

---

## 1. Problem Statement

Enterprise AI teams routinely build agents that work brilliantly in notebooks and fail in production. They crash under concurrent load, leak API keys through environment variables checked into source control, produce outputs with no audit trail, cost 3× more than necessary due to uncontrolled token usage, and cannot present a business case to justify continued investment.

This project bridges that gap. You will take a multi-agent content intelligence system and make it production-ready: containerized, asynchronous, observable, secure, and backed by a quantifiable business case.

---

## 2. What You Are Building

A production-grade web service that accepts a high-level content goal (e.g., *"research climate risk in Indian agriculture and write a 300-word brief"*), executes it through five specialized agents, and returns a verified, cited, on-brand result — with full observability, security controls, and a business-value report.

### 2.1 The Five Agents

| Agent | Responsibility |
|---|---|
| **Summarizer** | Detects inputs exceeding the token budget and condenses them before they reach expensive reasoning agents. Directly reduces API cost. |
| **Librarian** | Retrieves the correct brand-voice blueprint from the vector store based on goal context (e.g., formal research brief vs. casual social post). |
| **Researcher** | Executes hybrid RAG over the knowledge base, returns a structured summary with page-level citations. Every claim is traceable to a source. |
| **Writer** | Generates the final output using the Librarian's blueprint and the Researcher's findings. All content is stylistically governed. |
| **Moderator** | Runs two-stage content safety checks: pre-flight (before execution consumes resources) and post-flight (before output is persisted or returned). |

### 2.2 Execution Flow

```
Client submits goal
        │
        ▼
[API]  Validate request → dispatch to task queue → return 202 + trace_id
        │
        ▼
[Worker] Moderator (pre-flight) → Summarizer → Librarian → Researcher → Writer → Moderator (post-flight)
        │
        ▼
[Store] Persist ExecutionTrace → Redis
        │
        ▼
[Client] Poll /status/{trace_id} → retrieve result + citations + cost report
```

---

## 3. Functional Requirements

### 3.1 API Layer

| ID | Requirement |
|---|---|
| F-01 | `POST /api/v1/execute` accepts `{"goal": str, "require_audit_trace": bool}` and returns HTTP 202 with `trace_id`. |
| F-02 | `GET /api/v1/status/{trace_id}` returns current execution status: `queued \| running \| complete \| failed`. |
| F-03 | On `complete`, response includes: `final_output`, `sources_cited[]`, `agents_called[]`, `token_usage{}`, `duration_seconds`, `cost_inr`. |
| F-04 | `GET /metrics` exposes Prometheus-format metrics. |
| F-05 | All endpoints validate request structure via Pydantic. Malformed requests return HTTP 422 with field-level errors. |

### 3.2 Agent Behavior

| ID | Requirement |
|---|---|
| F-06 | Summarizer activates only when input exceeds a configurable token threshold (default: 4,000 tokens). It must log tokens saved. |
| F-07 | Researcher returns a minimum of 3 cited sources per goal. Each citation includes: source name, URL or document section, and confidence score. |
| F-08 | Writer output must be governed by a blueprint retrieved by the Librarian. If no blueprint matches, Writer uses a default style. |
| F-09 | Moderator pre-flight check must complete before any worker resource is consumed. A blocked goal returns `status: blocked` with reason. |
| F-10 | Moderator post-flight check must complete before ExecutionTrace is persisted. A failed post-flight check sets `status: failed` and suppresses output. |

### 3.3 ExecutionTrace

| ID | Requirement |
|---|---|
| F-11 | Every goal execution produces one `ExecutionTrace` persisted to Redis, keyed by `trace_id`. |
| F-12 | Trace contains: `trace_id`, `goal`, `agents_called[]`, `token_usage{}` (per agent), `tokens_saved`, `sources_cited[]`, `moderation_flags[]`, `status`, `duration_seconds`, `final_output`. |
| F-13 | Traces are immutable once persisted. A retry creates a new `trace_id`. |

### 3.4 Observability

| ID | Requirement |
|---|---|
| F-14 | Every log line (across API, queue, worker) carries `trace_id` as a structured field. |
| F-15 | Prometheus exposes four metrics minimum: `goals_total{status}`, `agent_latency_seconds{agent}`, `tokens_total{agent}`, `task_queue_depth`. |
| F-16 | Grafana dashboard has four panels: goals/min, agent latency p95, token spend rate (₹/hr), queue depth. |
| F-17 | OpenTelemetry spans cover: API request, Celery task dispatch, each agent call, Redis persist. All spans linked under one `trace_id` in Jaeger. |

---

## 4. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NF-01 | **No secrets in source code.** `grep -r "sk-ant\|OPENAI\|PINECONE" src/` must return zero matches. |
| NF-02 | **Async-first.** API must return 202 in under 200ms regardless of worker backlog. |
| NF-03 | **Containerized.** `docker-compose up` must start all services (API, worker, broker, redis, jaeger, prometheus, grafana) without manual steps. |
| NF-04 | **Reproducible.** Same goal submitted twice must produce structurally identical `ExecutionTrace` schemas (content may differ; schema must not). |
| NF-05 | **Cost-bounded.** Each goal execution must not exceed ₹50 in token spend. Worker must abort and set `status: budget_exceeded` if threshold is breached mid-run. |
| NF-06 | **Sanitization at two checkpoints.** Input sanitization runs at: (1) document ingestion into vector store; (2) runtime before retrieved context reaches any agent. |
| NF-07 | **Kubernetes-deployable.** `kubectl apply -f k8s/` must produce Running pods for API and Worker deployments. HPA must be configured for Worker. |

---

## 5. Technical Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11 | |
| API framework | FastAPI + Uvicorn | Async endpoints, Pydantic v2 |
| Task queue | Celery 5.x | |
| Message broker | RabbitMQ | Can substitute Redis as broker for local dev |
| Result backend | Redis | Also used for ExecutionTrace persistence |
| LLM | Anthropic Claude (claude-haiku-4-5 / claude-sonnet-4-6) | Haiku for Summarizer + Moderator; Sonnet for Researcher + Writer |
| Vector store | In-memory or Pinecone | In-memory acceptable for capstone submission |
| Logging | `structlog` | JSON output, `trace_id` on every line |
| Metrics | `prometheus-client` | |
| Tracing | `opentelemetry-sdk` + Jaeger exporter | |
| Containerization | Docker + docker-compose | |
| Orchestration | Kubernetes manifests | Minikube acceptable for local submission |
| Secrets | Environment variables + `.env` (local); K8s Secret (production manifests) | |

---

## 6. Repository Structure

```
capstone3/
├── api/
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic schemas
│   └── dependencies.py      # Auth, rate limit middleware
├── workers/
│   ├── tasks.py             # Celery task definitions
│   └── engine.py            # Agent orchestration
├── agents/
│   ├── summarizer.py
│   ├── researcher.py
│   ├── writer.py
│   ├── librarian.py
│   └── moderator.py
├── observability/
│   ├── logging.py           # structlog setup
│   ├── metrics.py           # Prometheus counters/histograms
│   └── tracing.py           # OpenTelemetry + Jaeger
├── security/
│   ├── secrets.py           # Secrets loader
│   └── sanitizer.py         # Input sanitization
├── execution_trace/
│   └── trace.py             # ExecutionTrace dataclass + Redis persistence
├── business_case/
│   └── roi_report.py        # ROI report generator
├── k8s/
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── hpa-worker.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
├── Dockerfile
├── docker-compose.yml       # Full local stack
├── requirements.txt
├── .env.example             # Template — never commit .env
└── tests/
    ├── test_agents.py
    ├── test_api.py
    └── test_sanitizer.py
```

---

## 7. Deliverables

Submit the following. Missing deliverables cap the grade at 60.

| # | Deliverable | Format |
|---|---|---|
| D-01 | Working service | `docker-compose up` → end-to-end goal execution |
| D-02 | Kubernetes manifests | `kubectl apply -f k8s/` → pods Running |
| D-03 | Grafana dashboard screenshot | PNG — all 4 panels populated with live data |
| D-04 | Jaeger trace screenshot | PNG — full waterfall for one goal execution |
| D-05 | ROI report | Generated by `roi_report.py` from 10+ trace logs |
| D-06 | Architecture Decision Record | 1 page, 4 questions answered (see §9) |
| D-07 | Business case document | 2 pages — ROI flywheel + trust pillar + knowledge moat |
| D-08 | Secret hygiene proof | Output of `grep -r "sk-ant\|OPENAI\|PINECONE" src/` showing zero matches |

---

## 8. Grading Rubric

| Area | Points | Pass criteria |
|---|---|---|
| **Agents (F-06 to F-10)** | 20 | All 5 agents functional; pre/post moderation enforced; Summarizer activates on threshold |
| **API + async queue (F-01 to F-05)** | 15 | 202 response under 200ms; poll endpoint returns correct status lifecycle |
| **ExecutionTrace (F-11 to F-13)** | 10 | Every goal produces a complete trace in Redis; schema matches spec |
| **Observability (F-14 to F-17)** | 15 | trace_id on every log; Prometheus metrics; Grafana 4 panels; Jaeger waterfall |
| **Security (NF-01, NF-06)** | 10 | Zero secrets in source; sanitization at both checkpoints |
| **Docker + docker-compose (NF-03)** | 10 | `docker-compose up` starts full stack; end-to-end works |
| **Kubernetes manifests (NF-07)** | 10 | Manifests apply; API + Worker pods Running; HPA present |
| **ROI report + business case (D-05, D-07)** | 5 | Report generates from traces; 3 value pillars articulated |
| **ADR (D-06)** | 5 | All 4 questions answered with specific technical reasoning |

**Total: 100 points. Pass: 75+**

Partial credit is awarded per sub-criterion within each area.

---

## 9. Architecture Decision Record (ADR) — Required Questions

Answer each in 2–4 sentences with specific technical reasoning (not generic definitions):

1. **Sync vs. async:** Why does a synchronous architecture fail at 50 concurrent goals? What specific resource is exhausted first, and how does the task queue solve it?

2. **Agent ordering:** The Summarizer runs before the Researcher, not after. What would the cost and latency impact be if this order were reversed on a 30-page input document?

3. **ExecutionTrace as business asset:** Your CTO asks: *"What makes our trace logs proprietary if we're using the same Claude models as our competitors?"* Answer with reference to at least two specific fields in the `ExecutionTrace` schema.

4. **Worker crash recovery:** A Celery worker crashes after the Researcher completes but before the Writer runs. What is the current state of the system? What would you add to make the goal automatically retry from the last completed step rather than from the beginning?

---

## 10. Business Case Document Structure

Two pages maximum. Use the ROI report output as your data source.

**Page 1 — Value Multiplier (ROI Flywheel)**

- **Reduce costs:** Summarizer saved `₹X` across `N` goals (Y% token reduction). Annualised projection at current usage.
- **Increase productivity:** Average goal completion time `Z seconds` vs. estimated `W minutes` manual equivalent. Hours saved per 100 goals.
- **Accelerate revenue:** Moderator blocked `M` brand-safety events. Each event avoided = estimated reputational risk of `₹R`.

**Page 2 — Trust Pillar + Knowledge Moat**

- **Auditability dividend:** Every output has an immutable `ExecutionTrace` with citations. Describe one compliance scenario where this trace satisfies an auditor's explainability requirement.
- **Security guarantee:** Sanitization runs at ingestion and runtime. Describe what a data poisoning attack looks like and how the two-checkpoint defense stops it.
- **Knowledge moat:** After 6 months of operation, what does the accumulated `ExecutionTrace` dataset enable that a competitor starting today cannot replicate?

---

## 11. Submission Checklist

Before submitting, verify each item:

- [ ] `docker-compose up` starts cleanly with no manual steps
- [ ] `curl -X POST /api/v1/execute -d '{"goal": "test"}'` returns 202 + trace_id in under 200ms
- [ ] Polling `/status/{trace_id}` eventually returns `complete` with `final_output` populated
- [ ] Grafana at `localhost:3000` shows all 4 panels with data
- [ ] Jaeger at `localhost:16686` shows a trace with spans for all 5 agents
- [ ] `grep -r "sk-ant\|OPENAI\|PINECONE" src/` returns zero matches
- [ ] `kubectl apply -f k8s/` runs without errors (dry-run acceptable if no cluster available)
- [ ] `python business_case/roi_report.py` generates output from ≥10 trace logs
- [ ] ADR answers all 4 questions with technical specificity
- [ ] Business case document is ≤2 pages and cites actual numbers from ROI report

---

## 12. Extension Challenges (ungraded)

These are not required for a passing grade. They demonstrate mastery beyond the spec.

| Challenge | What it tests |
|---|---|
| Add Celery Beat for a nightly scheduled research digest | Scheduled agentic workflows |
| Add webhook callback so client doesn't need to poll | Event-driven result delivery |
| Implement per-tenant cost isolation (each tenant has a separate token budget) | Enterprise multi-tenancy |
| Export ExecutionTrace logs to fine-tune a smaller open-source model | Knowledge moat → model distillation |
| Replace polling with Server-Sent Events for real-time progress | L27 Streaming applied to async jobs |

---

*This spec defines the contract between student and evaluator. Implementation details not specified here are at the student's discretion provided all functional and non-functional requirements are met.*
