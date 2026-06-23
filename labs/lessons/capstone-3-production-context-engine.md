# Capstone 3 — The Production-Grade Context Intelligence Platform

> **Deploy a glass-box multi-agent service to enterprise production.** Five specialized agents (Summarizer, Researcher, Writer, Librarian, Moderator) run inside a containerized, async-first FastAPI service with Celery task queues, Kubernetes orchestration, centralized secrets management, full observability (structured logs + Prometheus + Jaeger), and a business-value dashboard — turning a notebook prototype into a mission-critical enterprise platform.

---

## Roadmap — where this sits

```
Phase 1 (L01-11)   Phase 2 (L12-21)   Phase 3 (L22-28)   Enterprise Hardening   Capstones
Foundation          Agentic Patterns    Advanced RAG        IAM + Model Routing

                                                                                  ○ Capstone 1 — CLI Coding Agent
                                                                                  ○ Capstone 2 — Financial Research
                                                                                  ▶ CAPSTONE 3  ◄ YOU ARE HERE
                                                                                    Production Context Engine
```

**Why this capstone:** Capstones 1 and 2 proved you can build agents. Capstone 3 proves you can **ship** them. Every enterprise AI project eventually hits the same wall — a working prototype that cannot survive production traffic, cannot be audited, cannot recover from failures, and cannot justify its cost to leadership. This capstone tears down that wall.

---

## Scenario

A consulting firm has a working multi-agent content engine that runs in Jupyter notebooks. It does excellent work but crashes under load, leaks API keys, has no audit trail, and costs 3× more than it should. Your job is to productionize it: containerize it, make it async, add full observability, harden security, and present a business case to the CTO.

**Deliverable:** A fully containerized service that a DevOps engineer could deploy to AWS EKS, a Grafana dashboard showing live metrics, a Jaeger trace for a sample request, and a 2-page business case document.

---

## The Five Agents You Deploy

| Agent | Role | Chapter 10 capability |
|---|---|---|
| **Summarizer** | Reduce large docs before they hit expensive models | Proactive cost reduction |
| **Researcher** | Retrieve + cite sources from vector KB | High-fidelity RAG + auditability |
| **Writer** | Generate on-brand content | Brand governance via blueprints |
| **Librarian** | Retrieve brand voice blueprints from vector store | Semantic blueprint retrieval |
| **Moderator** | Pre-flight + post-flight content safety check | Compliance guardrails |

---

## Full Architecture

```
External Client
      │
      ▼
API Gateway  (Kong / AWS API Gateway)
  Auth + Rate Limiting + SSL termination
      │
      ▼
┌─────────────────────────────────────────────────────┐
│              Kubernetes Cluster                     │
│                                                     │
│   ┌──────────────────────┐                          │
│   │  FastAPI Service     │  ◄── Deployment (3 pods) │
│   │  POST /execute       │                          │
│   │  GET  /status/{id}   │                          │
│   │  GET  /metrics       │                          │
│   └──────────┬───────────┘                          │
│              │ dispatch (202 Accepted)               │
│              ▼                                       │
│   ┌──────────────────────┐                          │
│   │  Task Queue          │  RabbitMQ / Redis         │
│   └──────────┬───────────┘                          │
│              │ pull                                  │
│              ▼                                       │
│   ┌──────────────────────┐                          │
│   │  Worker Pool         │  ◄── HPA autoscales       │
│   │  Celery workers      │      on queue length      │
│   │  ┌────────────────┐  │                          │
│   │  │ Summarizer     │  │                          │
│   │  │ Researcher     │  │◄── LLM API (Anthropic)   │
│   │  │ Writer         │  │◄── Vector DB (Pinecone)  │
│   │  │ Librarian      │  │◄── Secrets (Vault)       │
│   │  │ Moderator      │  │                          │
│   │  └────────────────┘  │                          │
│   └──────────┬───────────┘                          │
│              │ persist                               │
│              ▼                                       │
│   ┌──────────────────────┐                          │
│   │  Result Store (Redis)│                          │
│   │  ExecutionTrace logs │                          │
│   └──────────────────────┘                          │
│                                                     │
│   ┌──────────────────────────────────────────────┐  │
│   │  Observability Stack                         │  │
│   │  Structured logs → ELK/CloudWatch            │  │
│   │  Metrics → Prometheus → Grafana              │  │
│   │  Traces  → Jaeger (distributed tracing)      │  │
│   └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Files you will create

```
capstone3/
├── api/
│   ├── main.py           # FastAPI app — /execute, /status, /metrics
│   ├── models.py         # Pydantic request/response schemas
│   └── dependencies.py   # Auth, rate limit, secrets injection
├── workers/
│   ├── tasks.py          # Celery task definitions
│   └── engine.py         # Agent orchestration logic
├── agents/
│   ├── summarizer.py     # Proactive context reduction
│   ├── researcher.py     # High-fidelity RAG + citations
│   ├── writer.py         # Brand-voice content generation
│   ├── librarian.py      # Blueprint retrieval from vector store
│   └── moderator.py      # Pre/post flight content moderation
├── observability/
│   ├── logging.py        # Structured JSON logger (trace_id on every line)
│   ├── metrics.py        # Prometheus counters/histograms
│   └── tracing.py        # OpenTelemetry + Jaeger spans
├── security/
│   ├── secrets.py        # HashiCorp Vault / env-based secrets loader
│   └── sanitizer.py      # Input sanitization + poison detection
├── execution_trace/
│   └── trace.py          # ExecutionTrace dataclass + persistence
├── Dockerfile            # API + Worker image
├── docker-compose.yml    # Local dev: FastAPI + Celery + RabbitMQ + Redis + Jaeger
├── k8s/
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── hpa-worker.yaml   # Autoscale on queue length
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
└── business_case/
    └── roi_report.py     # Auto-generate ROI metrics from ExecutionTrace logs
```

---

## What each lesson / chapter concept shows up as

| In this capstone | From lesson / Chapter 10 section |
|---|---|
| Five agents (Summarizer, Researcher, Writer, Librarian, Moderator) | L03, L14 |
| Hybrid RAG for Researcher citations | L22 |
| Token counting + auto-summarize over threshold | L04, L26, Ch10 §Cost Management |
| Input/output guardrails (Moderator) | L10, Ch10 §Guardrails |
| FastAPI async service with Pydantic | L28, Ch10 §Orchestration Layer |
| Celery + RabbitMQ task queue (202 Accepted pattern) | Ch10 §Async Task Queues |
| Docker containerization | Ch10 §Containerization |
| Kubernetes deployment + HPA | Ch10 §Infrastructure |
| 12-factor config + secrets management | Ch10 §Secrets Management |
| Structured JSON logging with trace_id | Ch10 §Observability |
| Prometheus + Grafana metrics | Ch10 §Observability |
| Jaeger distributed tracing via OpenTelemetry | Ch10 §Observability |
| ExecutionTrace log as proprietary asset | Ch10 §Knowledge Moat |
| ROI flywheel metrics (cost saved, time saved) | Ch10 §Business Value |
| Brand governance via vector blueprints | Ch10 §Creative Workflows |
| Data poisoning defense at ingestion + runtime | Ch10 §Security |

---

## Step-by-step build sequence

### Phase A — Core service (local)

**Step 1 — Agents**
Implement all five agents as standalone classes. Each accepts a `goal: str` and returns `AgentResult(output, sources, token_usage)`. Test each independently with 3 sample inputs before wiring.

**Step 2 — ExecutionTrace**
```python
@dataclass
class ExecutionTrace:
    trace_id: str
    goal: str
    agents_called: list[str]
    token_usage: dict[str, int]    # per agent
    sources_cited: list[str]       # URLs + page refs
    moderation_flags: list[str]
    status: str                    # running | complete | failed
    duration_seconds: float
    final_output: str
```
Every agent call appends to the trace. At completion, trace is persisted to Redis and logged as JSON.

**Step 3 — FastAPI service**
```python
@app.post("/api/v1/execute", status_code=202)
async def execute_goal(request: GoalRequest, background: BackgroundTasks):
    trace_id = str(uuid4())
    task = run_engine.delay(request.goal, trace_id)   # Celery dispatch
    return {"trace_id": trace_id, "status": "queued"}

@app.get("/api/v1/status/{trace_id}")
async def get_status(trace_id: str):
    trace = redis_client.get(trace_id)
    if not trace:
        raise HTTPException(404)
    return json.loads(trace)
```

**Step 4 — Celery worker + task queue**
- Configure Celery with RabbitMQ as broker, Redis as result backend
- `run_engine` task: orchestrate all five agents, write ExecutionTrace
- Test locally: `docker-compose up` → submit a goal → poll `/status/{id}`

---

### Phase B — Observability

**Step 5 — Structured logging**
```python
import structlog
log = structlog.get_logger()

# Every log line carries trace_id automatically
log.info("agent_called", agent="researcher", trace_id=trace_id,
         tokens_in=1200, tokens_out=340, latency_ms=820)
```
Every log line must carry `trace_id`. This connects all log lines for a single goal across API, queue, and worker pods.

**Step 6 — Prometheus metrics**
```python
from prometheus_client import Counter, Histogram

GOALS_TOTAL      = Counter("goals_total", "Total goals submitted", ["status"])
AGENT_LATENCY    = Histogram("agent_latency_seconds", "Agent call latency", ["agent"])
TOKEN_USAGE      = Counter("tokens_total", "Total tokens consumed", ["agent"])
QUEUE_LENGTH     = Gauge("task_queue_length", "Current Celery queue depth")
```
Expose `/metrics` endpoint. In `docker-compose.yml`, add Prometheus scrape config + Grafana with 4 pre-built panels:
- Goals per minute (success vs. failed)
- Agent latency p50/p95
- Token spend rate (₹/hour)
- Queue depth (triggers autoscale alarm > 10)

**Step 7 — Distributed tracing (OpenTelemetry + Jaeger)**
```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
tracer = trace.get_tracer("context-engine")

with tracer.start_as_current_span("researcher_agent") as span:
    span.set_attribute("trace_id", trace_id)
    span.set_attribute("tokens_in", tokens_in)
    result = researcher.run(goal)
```
One Jaeger trace per goal execution, spanning API → queue → worker → each agent call → result store. Verify the full waterfall is visible in Jaeger UI at `localhost:16686`.

---

### Phase C — Security & configuration

**Step 8 — Secrets management (12-factor)**
```python
# security/secrets.py
import os
from pathlib import Path

def get_secret(name: str) -> str:
    # Priority: Vault sidecar file > env var > raise
    vault_path = Path(f"/vault/secrets/{name}")
    if vault_path.exists():
        return vault_path.read_text().strip()
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Secret {name!r} not found in Vault or environment")
    return value

ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY")
PINECONE_API_KEY  = get_secret("PINECONE_API_KEY")
```
No API keys in code. `.env` for local dev, Kubernetes Secret + Vault sidecar for production. Test: confirm `grep -r "sk-ant"` finds nothing in source.

**Step 9 — Input sanitization + poison defense**
Apply `sanitize_input()` at two checkpoints:
1. At ingestion: before any document is chunked into the vector store
2. At runtime: before retrieved context is passed to Researcher or Writer

Sanitizer checks: prompt injection patterns, PII (SSN, card numbers), known toxic strings. Returns `SanitizationResult(is_clean, flags, sanitized_text)`.

---

### Phase D — Kubernetes deployment

**Step 10 — Dockerfile + docker-compose**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Same image, different CMD for worker:
```yaml
# docker-compose.yml
worker:
  image: context-engine:latest
  command: celery -A workers.tasks worker --loglevel=INFO --concurrency=4
```

**Step 11 — Kubernetes manifests**
Write `k8s/` manifests for:
- API Deployment (3 replicas) + Service + Ingress
- Worker Deployment (2 replicas baseline)
- HPA for Worker: scale up when queue depth > 10 (custom metric via Prometheus adapter)
- ConfigMap for non-secret config (model names, token thresholds)
- Secret for API keys (base64 encoded, referenced by pod env vars)

Test: `kubectl apply -f k8s/` → `kubectl get pods` → all Running.

---

### Phase E — Business value dashboard

**Step 12 — ROI report from ExecutionTrace logs**
```python
# business_case/roi_report.py
def generate_roi_report(trace_logs: list[ExecutionTrace]) -> ROIReport:
    total_tokens     = sum(sum(t.token_usage.values()) for t in trace_logs)
    tokens_saved     = sum(t.tokens_saved_by_summarizer for t in trace_logs)
    avg_latency      = mean(t.duration_seconds for t in trace_logs)
    goals_completed  = sum(1 for t in trace_logs if t.status == "complete")
    cost_inr         = total_tokens * TOKEN_COST_PER_1K / 1000
    cost_saved_inr   = tokens_saved * TOKEN_COST_PER_1K / 1000

    return ROIReport(
        goals_completed=goals_completed,
        total_cost_inr=cost_inr,
        cost_saved_by_summarizer_inr=cost_saved_inr,
        avg_goal_duration_seconds=avg_latency,
        sources_cited=sum(len(t.sources_cited) for t in trace_logs),
        moderation_blocks=sum(len(t.moderation_flags) for t in trace_logs),
    )
```
Run against 20 sample traces and print the ROI flywheel numbers: cost saved, time saved vs. manual, moderation blocks (brand protection events).

---

## Run it

```bash
# Local dev
docker-compose up

# Submit a goal
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"goal": "Research the impact of climate change on Indian agriculture and write a 300-word brief"}'

# → {"trace_id": "abc-123", "status": "queued"}

# Poll status
curl http://localhost:8000/api/v1/status/abc-123

# → {"status": "complete", "final_output": "...", "sources_cited": [...], "tokens_used": 4200}

# View Grafana: http://localhost:3000
# View Jaeger:  http://localhost:16686
# View metrics: http://localhost:8000/metrics
```

Expected terminal output in worker:
```
[moderator]   pre-flight PASS  (trace=abc-123, 0.3s)
[summarizer]  input=18,400 tokens → reduced to 4,200 (77% reduction, saved ₹11.20)
[librarian]   blueprint retrieved: "research_brief_formal" (score=0.91)
[researcher]  retrieved 6 chunks from 3 sources, citations attached
[writer]      draft generated (820 tokens, 2.1s)
[moderator]   post-flight PASS (trace=abc-123, 0.2s)
[trace]       persisted → Redis (trace=abc-123, total=6.8s, cost=₹3.40)
```

---

## Grading rubric

| Area | Points | Criteria |
|---|---|---|
| **All 5 agents functional** | 15 | Each agent produces correct output independently; integration works end-to-end |
| **Async task queue** | 15 | 202 Accepted response; goal executes in worker; result retrievable via poll |
| **Observability** | 15 | Every log line has trace_id; Prometheus metrics visible; Jaeger waterfall complete |
| **Docker + docker-compose** | 10 | `docker-compose up` starts all services; end-to-end goal execution works |
| **Kubernetes manifests** | 10 | All manifests apply cleanly; pods reach Running state; HPA configured |
| **Secrets management** | 10 | Zero API keys in source code; secrets load from env/vault; grep check passes |
| **Sanitization** | 10 | Poison injection blocked at ingestion and runtime; PII detected |
| **ExecutionTrace + ROI report** | 10 | Trace persisted for every goal; ROI report generates from 20 traces |
| **Business case** | 5 | 2-page doc covers ROI flywheel, trust pillar, knowledge moat |

**Total: 100 points. Pass: 75+**

---

## Architecture Decision Record (deliverable)

Write a 1-page ADR answering:
1. Why async task queue instead of a synchronous API call? What would break at 100 concurrent goals with a sync approach?
2. Why does the Summarizer run before the Researcher and Writer, not after? What is the cost of getting this order wrong?
3. The ExecutionTrace is called a "knowledge moat" in the business case. What specific data in the trace is proprietary and what would a competitor need to replicate it?
4. If a Celery worker crashes mid-execution, what happens to the in-flight goal? How would you make this recoverable?

---

## Business case deliverable

Generate a 2-page document using `roi_report.py` output covering:

**Page 1 — ROI Flywheel**
- Cost saved: `₹X saved in token spend via Summarizer (Y% reduction)`
- Productivity gain: `Z goals completed per hour vs. N hours manual equivalent`
- Moderation value: `W brand protection events blocked`

**Page 2 — Trust Pillar + Knowledge Moat**
- Auditability: every output has an immutable trace with source citations
- Security: `V sanitization checks run, P poisoning attempts blocked`
- Knowledge moat: `T ExecutionTrace logs accumulated = proprietary reasoning dataset`

---

## Extension challenges

| Challenge | What you learn |
|---|---|
| Add Celery Beat for scheduled goals (nightly research digest) | Cron-style agentic workflows |
| Add webhook callback instead of polling | Event-driven result delivery |
| Add multi-tenant support — each tenant has isolated vector namespace + cost tracking | Enterprise SaaS patterns |
| Export ExecutionTrace logs to fine-tune a smaller model | Knowledge moat → model distillation |
| Add Istio service mesh for mTLS between pods | Zero-trust networking |

---

## Mental model in one line

> **A production AI service is not a smarter agent — it is a reliable system built around an agent: async, observable, secure, containerized, and capable of justifying its own existence to a CFO.**

---

## Chapter 10 concept coverage map

| Chapter 10 Section | Where in this capstone |
|---|---|
| Environment config + secrets management | Step 8, `security/secrets.py`, k8s Secret |
| FastAPI orchestration layer | Step 3, `api/main.py` |
| Async task queues (Celery + RabbitMQ) | Step 4, `workers/tasks.py` |
| Structured logging + ELK | Step 5, `observability/logging.py` |
| Prometheus + Grafana | Step 6, `observability/metrics.py` |
| Jaeger distributed tracing | Step 7, `observability/tracing.py` |
| Docker containerization | Step 10, `Dockerfile` |
| Kubernetes + HPA | Step 11, `k8s/` manifests |
| Proactive cost reduction (Summarizer) | Step 1, `agents/summarizer.py` |
| High-fidelity RAG + citations | Step 1, `agents/researcher.py` |
| Data poisoning defense | Step 9, `security/sanitizer.py` |
| Content moderation guardrails | Step 1, `agents/moderator.py` |
| Brand governance via blueprints | Step 1, `agents/librarian.py` + `agents/writer.py` |
| ExecutionTrace as knowledge moat | Step 2, `execution_trace/trace.py` |
| ROI flywheel business case | Step 12, `business_case/roi_report.py` |

---

## Related

- **Prerequisites:** Capstone 1 (CLI Coding Agent), Capstone 2 (Financial Research Agent)
- **Core dependencies:** L03, L10, L14, L22, L26, L28
- **Chapter 10 reference:** The Blueprint for Production-Ready AI
