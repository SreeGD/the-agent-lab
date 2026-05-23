# 28 — Production Deploy + Observability (Session 17)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `openai` (raw SDK), model is `gpt-4o`, and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/28_production_app_openai.py`. Note: the readiness check uses `client.models.retrieve("gpt-4o")` instead of `count_tokens` (OpenAI doesn't have a free count_tokens endpoint); cost is computed from `response.usage.prompt_tokens` and `response.usage.completion_tokens` using the published token rates.

> **The session where the chatbot stops being a notebook and becomes a service.** FastAPI + structured logs + distributed traces + Prometheus metrics + health checks + a Dockerfile + a deploy target. This is the operating manual for shipping any of the prior 16 sessions to a real URL.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-16 (foundation + RAG + eval + cost + streaming)     Track F: PRODUCTION
                                                             ✓ Session 14: Evaluation
                                                             ✓ Session 15: Cost Optimization
                                                             ✓ Session 16: Streaming
                                                             ▶ Session 17: DEPLOY + OBSERVABILITY  ◄ HERE
                                                           Track G: ○ Architect Skills
```

**Why this lesson now:** You have a tested (S14), cost-optimized (S15), latency-tuned (S16) pipeline. What's left is making it run as a *service*: an HTTP API, observability, a container, and a one-command deploy. Track F closes here.

---

## File involved

| File | Role |
|---|---|
| [`28_production_app_openai.py`](../../openai/28_production_app_openai.py) | FastAPI app with `/chat` (SSE streaming), `/health` (liveness + readiness), `/metrics` (Prometheus). Structured JSON logs, request IDs threaded through, manual spans, cost + cache metrics. Includes an in-process demo via FastAPI's `TestClient` so you can run it without binding a port. |

The deploy artifacts (Dockerfile, fly.toml) live in this lesson — they're configs, not Python.

---

## What problem it solves

A working pipeline in a Python script is not a product. A product has:

| Need | Provided by |
|---|---|
| Other services can call it | An HTTP API |
| You can debug when it breaks | Structured logs with request IDs |
| You know how it's behaving in aggregate | Metrics endpoint scraped by Prometheus / Datadog |
| You know which calls are slow | Distributed traces |
| The load balancer knows when a pod is bad | Health / readiness endpoints |
| You can ship it anywhere | A Dockerfile |
| You can ship it cheaply | A one-command deploy target (Fly, Cloud Run, ECS, Lambda) |
| You can track AI spend | Cost computed per-call from the SDK `usage` object |

This lesson wires up all eight in one ~250-line file.

---

## The analogy

**Renting an apartment vs. running a restaurant.**

Your Python script is your kitchen at home — works fine, only you eat there, no inspections.

A production service is a restaurant. Different requirements:
- A storefront (the HTTP API) — people can walk in
- A health permit (readiness endpoint) — proves the kitchen is open and safe
- Books (metrics + cost tracking) — you know if you're making money
- Cameras (traces + structured logs) — when something goes wrong you can replay the night
- Standard recipes (Dockerfile) — anyone can run the same kitchen in another building
- A landlord (deploy target) — somewhere to actually open up

You can't open a restaurant without those. You can't ship AI without these.

---

## Visual

```
                         ┌────────────────────────────────────────┐
                         │           FastAPI app                  │
   ┌─────────┐    POST   │                                        │
   │ Browser │ ────────► │  middleware: assign request_id ────────┤  ──► structured JSON log
   │  /CLI   │           │                                        │      {request_id, span, ...}
   └─────────┘           │  /chat ──► span("chat.llm_stream") ──► │
                         │            openai.chat.completions     │  ──► /metrics scraped by
                         │            .stream()                   │      Prometheus / Datadog
                         │            yield SSE deltas            │
                         │                                        │
   ┌─────────┐    GET    │  /health ──► models.retrieve() ────────┤  ──► load balancer sees 503
   │   k8s   │ ────────► │            return {status, readiness}  │      → pulls pod out of rotation
   └─────────┘           │                                        │
                         │  /metrics ──► generate_latest() ───────┤  ──► Grafana dashboards
                         │                                        │      alertmanager pages
                         └────────────────────────────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   Dockerfile    │
                              │   fly.toml      │
                              │  ─────────────  │
                              │  fly deploy →   │
                              │  https://app.   │
                              │  fly.dev/chat   │
                              └─────────────────┘
```

---

## Concept walk-through

### 1. The FastAPI app — three endpoints

```python
app = FastAPI(title="AgenticCourse Production Chat", version="0.1.0")

@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    return StreamingResponse(
        stream_chat(request.state.request_id, req.question),
        media_type="text/event-stream",
    )

@app.get("/health")
async def health():
    # liveness implicit, readiness = "can we reach OpenAI?"
    ...

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(REGISTRY),
                    media_type=CONTENT_TYPE_LATEST)
```

Three endpoints, three jobs:
- `/chat` → the product (Session 16 streaming, wrapped in HTTP)
- `/health` → ops contract (load balancers, k8s probes)
- `/metrics` → observability contract (Prometheus scrapers)

### 2. Request IDs — the audit trail

```python
@app.middleware("http")
async def add_request_id(request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    log("http", "request.received", request_id=request_id, ...)
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response
```

Every request gets a UUID. That ID is:
- Logged on receive + complete
- Threaded into every span
- Threaded into every log line from inside the handler
- Echoed back to the caller in the `x-request-id` response header

When a user reports a bug, that ID lets you grep across logs, traces, *and other services* (if they pass it through). This is the single most important production hygiene practice you'll learn from this lesson.

### 3. Structured JSON logs

```python
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", ...),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload)
```

Every log line is a JSON object on stdout. Real output from the run:
```json
{"timestamp": "2026-05-21T04:56:43Z", "level": "INFO", "logger": "chat", "message": "ttft", "request_id": "1c44c4d2...", "ttft_ms": 1309.31}
{"timestamp": "2026-05-21T04:56:45Z", "level": "INFO", "logger": "chat", "message": "completed", "request_id": "1c44c4d2...", "chunks": 6, "input_tokens": 31, "output_tokens": 97, "cost_usd": 0.001548, "total_ms": 3283.19}
```

Why JSON? **Log aggregators ingest these directly** — no parsing rules, no fragile regexes. Datadog, CloudWatch Logs, Loki, Splunk, Grafana Loki all index any field automatically. Want to find all calls slower than 5 seconds? `total_ms > 5000`. Want a chart of cost per hour? Sum `cost_usd` grouped by `floor(timestamp / 1h)`. You don't write parsers; you just query.

### 4. Manual span instrumentation

```python
@contextmanager
def span(name: str, **fields):
    span_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    log("trace", f"span.start: {name}", span_id=span_id, span_name=name, **fields)
    try:
        yield span_id
    except Exception as e:
        log("trace", f"span.error: {name}", span_id=span_id, latency_ms=..., error=str(e))
        raise
    else:
        log("trace", f"span.end: {name}", span_id=span_id, latency_ms=...)
```

Usage:
```python
with span("chat.llm_stream", request_id=request_id, question=question[:60]):
    # ... do the work ...
```

Each span emits a structured `span.start` + `span.end` (or `span.error`) with `latency_ms`. The JSON shape matches what OpenTelemetry emits — when you're ready to send traces to Honeycomb / Jaeger / Datadog APM, swap the contextmanager:

```python
# Before (this lab):
with span("chat.llm_stream", request_id=request_id):
    ...

# After (real OpenTelemetry):
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("chat.llm_stream") as sp:
    sp.set_attribute("request_id", request_id)
    ...
```

Same shape comes out the other side. The manual version teaches the *concept* — what data structure a span actually is — without dragging in 8 OpenTelemetry packages.

### 5. Prometheus metrics

```python
CHAT_REQUESTS = Counter("chat_requests_total", "Total chat requests received.")
CHAT_TTFT = Histogram("chat_ttft_seconds", "Time to first streamed token.",
                       buckets=(0.25, 0.5, 1.0, 2.0, 4.0, 8.0))
COST_TOTAL = Counter("chat_cost_usd_total", "Cumulative spend in USD.")
```

Real output from `/metrics`:
```
chat_requests_total 1.0
chat_errors_total 0.0
chat_ttft_seconds_count 1.0
chat_ttft_seconds_sum 1.309314750134945
chat_total_seconds_count 1.0
chat_total_seconds_sum 3.283187916968018
chat_cost_usd_total 0.001548
chat_cache_read_tokens_total 0.0
```

Three metric kinds:
- **Counter** — monotonically increasing (requests, errors, cumulative cost). Rate is computed at query time (`rate(chat_requests_total[5m])`).
- **Histogram** — buckets for latency (`chat_ttft_seconds_bucket{le="0.25"} 0`, etc.). Lets you compute percentiles in PromQL: `histogram_quantile(0.95, ...)`.
- **Gauge** — current value (not used here, but typical for things like "queue depth" or "active sessions").

The right metric set for an LLM service:
- Request volume + error rate (saturation + health)
- TTFT histogram + total-latency histogram (UX SLOs)
- Cumulative cost + per-call cost histogram (cost SLOs)
- Cache hit ratio (efficiency)
- Per-model breakdown (label the metrics with `model=` for cost attribution)

### 6. Health checks — liveness vs readiness

```python
@app.get("/health")
async def health():
    with span("health.check"):
        ready = False
        try:
            client.models.retrieve("gpt-4o")   # cheap reachability probe
            ready = True
        except Exception as e:
            error = str(e)
        return JSONResponse(
            {"status": "ok" if ready else "degraded",
             "liveness": True, "readiness": ready},
            status_code=200 if ready else 503,
        )
```

**Liveness** — "is the process up?" — always True if `/health` responds.
**Readiness** — "can it actually serve traffic?" — `models.retrieve` exercises auth + reachability cheaply.

Why 503 on readiness failure? Kubernetes / Fly / ECS / Cloud Run all interpret 5xx as "not ready" and pull the pod out of load-balancer rotation. If OpenAI is down, your pod stops getting traffic — automatic graceful degradation. Same code, no extra wiring.

Real output from the run:
```
status=200  body={'status': 'ok', 'liveness': True, 'readiness': True, 'error': None}
```

### 7. The streaming endpoint — connecting the dots

The `/chat` endpoint is where every observability surface comes together:

```python
def stream_chat(request_id: str, question: str) -> Iterator[bytes]:
    CHAT_REQUESTS.inc()                             # ← metric
    start = time.perf_counter()                     # ← latency tracking
    with span("chat.llm_stream", request_id=...):   # ← trace
        with client.chat.completions.stream(...) as stream:
            for event in stream:
                if event.type == "content.delta":
                    if first_token_at is None:
                        CHAT_TTFT.observe(...)      # ← histogram
                        log("chat", "ttft", ...)    # ← structured log
                    yield f"data: {json.dumps({'type': 'token', 'delta': event.delta})}\n\n".encode()
            final = stream.get_final_completion()
        # cost from usage
        cost = compute_cost(final.usage)
        COST_TOTAL.inc(cost)                        # ← metric
        log("chat", "completed", cost_usd=cost, ...) # ← structured log
        yield f"data: {json.dumps({'type': 'done', 'cost_usd': cost})}\n\n".encode()
```

Six observability surfaces wrapping one streaming generator. None of them slow down the user-facing stream — they all run alongside it.

---

## Run it

In-process demo (no port binding, uses TestClient):
```
cd labs
./.venv/bin/python openai/28_production_app_openai.py
```

Real server (binds port 8000):
```
cd labs
./.venv/bin/python -m uvicorn openai.28_production_app_openai:app --host 0.0.0.0 --port 8000
```

Then in another terminal:
```bash
curl http://localhost:8000/health
curl -N http://localhost:8000/chat -X POST \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is LangChain LCEL?"}'
curl http://localhost:8000/metrics
```

---

## Real output highlights

**Health check:**
```json
{"status": "ok", "liveness": true, "readiness": true, "error": null}
```

**Streamed answer (parsed deltas, then done):**
```
> LangChain Expression Language (LCEL) is a declarative syntax for composing
  LangChain components (like prompts, models, and parsers) into chains using
  the pipe operator (|). It enables easy chaining of components where the
  output of one step becomes the input of the next. LCEL provides built-in
  support for streaming, async execution, batch processing, and observability
  out of the box.
[done] cost=$0.001548  total_ms=3283  in=31 out=97
```

**Structured logs (the audit trail for the above call):**
```json
{"logger": "http",  "message": "request.received", "request_id": "1c44c4d2...", "method": "POST", "path": "/chat"}
{"logger": "trace", "message": "span.start: chat.llm_stream", "span_id": "4a1eb31f", "request_id": "1c44c4d2..."}
{"logger": "chat",  "message": "ttft", "request_id": "1c44c4d2...", "ttft_ms": 1309.31}
{"logger": "trace", "message": "span.end: chat.llm_stream", "span_id": "4a1eb31f", "latency_ms": 3283.06}
{"logger": "chat",  "message": "completed", "request_id": "1c44c4d2...", "chunks": 6, "input_tokens": 31, "output_tokens": 97, "cost_usd": 0.001548, "total_ms": 3283.19}
```

**Metrics:**
```
chat_requests_total 1.0
chat_ttft_seconds_count 1.0
chat_ttft_seconds_sum 1.309
chat_total_seconds_sum 3.283
chat_cost_usd_total 0.001548
```

---

## Deploy artifacts

### `Dockerfile` (multi-stage, slim, non-root)

```dockerfile
# Build stage — install deps into a virtualenv
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Runtime stage — copy the venv, run as non-root
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser 28_production_app_openai.py .

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "28_production_app_openai:app", "--host", "0.0.0.0", "--port", "8000"]
```

Why the multi-stage build:
- Builder downloads + compiles deps (heavy)
- Runtime is just Python + the venv (slim)
- Result: ~150 MB image vs ~500 MB single-stage

Why non-root user: container security baseline. Most modern runtimes (Cloud Run, ECS, Kubernetes with PSP) require it.

### `fly.toml` (Fly.io — fast, cheap, regional deploys)

```toml
app = "agenticcourse-chat"
primary_region = "iad"

[build]

[env]
  PORT = "8000"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"        # scale to zero when idle
  auto_start_machines = true
  min_machines_running = 0

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/health"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory = "512mb"
```

Deploy commands:
```bash
fly launch                          # one-time: claim app name, region
fly secrets set OPENAI_API_KEY=sk-...
fly deploy
# ... ~60 seconds later ...
# https://agenticcourse-chat.fly.dev/chat is live
```

Cost: scale-to-zero means **$0 when idle**, ~$2/month for the small VM when handling traffic. Hard to beat for hobby / pre-revenue services.

### `.dockerignore`

```
.venv
__pycache__
*.pyc
.git
.env
*.md
tests
```

Excludes the venv (200+ MB) and secrets from the build context. The .env file in particular should NEVER make it into a container — use real secrets management (`fly secrets`, AWS Secrets Manager, etc.).

---

## Production patterns

### Secrets — never in env files

The `.env` is a developer convenience. In production:
- **Fly**: `fly secrets set KEY=value` (encrypted at rest, injected as env at runtime)
- **AWS**: Secrets Manager + IAM role on the task/container
- **Cloud Run**: Secret Manager + `--set-secrets` at deploy time
- **Kubernetes**: `Secret` resource + `envFrom: secretRef:` (or external-secrets-operator)

Rule: if a secret is committed anywhere in your repo (including `.env.example` with real values), rotate it.

### Connection pooling

The `openai.OpenAI()` client maintains an httpx connection pool. Default 100 connections — fine for a single replica. Watch:
- One client *per process* (instantiate at import time, not per-request)
- Async variant (`openai.AsyncOpenAI`) for async FastAPI routes — uses async httpx, doesn't block the event loop
- The streaming endpoint in this lab is sync but spawned on a thread (FastAPI handles this transparently with `def`); for high concurrency switch to `async def` + `AsyncOpenAI`

### Rate limits + 429 handling

OpenAI rate limits per API key are tier-based. In production:
- Retry with exponential backoff on 429 + 5xx
- Surface 429 to the *user* with a friendly message ("we're a bit overloaded, try again in 30 seconds")
- Track `chat_errors_total{type="rate_limit"}` separately — distinguishes capacity issues from real errors

```python
from openai import RateLimitError
try:
    ...
except RateLimitError as e:
    CHAT_ERRORS.labels(type="rate_limit").inc()
    raise HTTPException(status_code=429, detail="Rate limited; retry in 30s")
```

### Persistent storage

The lab is stateless. Production usually needs:
- **Sessions** — Redis (chat history, agent memory). Don't put this in the application process; it dies on every deploy.
- **Vector store** — Pinecone / Weaviate / Qdrant Cloud / managed pgvector. NOT `InMemoryVectorStore`.
- **Eval datasets, prompts** — in the repo (versioned with code) or in a "prompt store" service if your team wants to edit prompts without redeploying.

### Autoscaling

Trigger on the right signal:
- **HTTP request rate** (good — direct proxy for load)
- **CPU** (bad — LLM apps are I/O bound; CPU is misleading)
- **In-flight requests** (best — `chat_active_requests` gauge, scale at `> 50`)

Concurrency limit per replica: OpenAI's rate limit / N replicas. Don't accept more concurrent streams than you can service.

### Observability stack — the minimum useful set

| Tool | Replaces |
|---|---|
| Datadog ($) | logs + metrics + traces + APM, all in one. Expensive but turn-key. |
| Honeycomb ($) | traces + logs. Best for "I have a bug — let me follow this request through 5 services." |
| Grafana Cloud ($) | metrics (Prometheus) + logs (Loki) + traces (Tempo). Open-source roots, generous free tier. |
| Self-hosted: Prometheus + Grafana + Loki + Tempo | Cheap if you have ops people. Expensive otherwise. |

The "minimum useful set" for an LLM service: **structured logs + metrics**. Traces are next, but logs + metrics get you 80% of the way.

### Alerts that don't burn out your oncall

- p99 TTFT > 3s for 5 minutes → page
- Error rate > 5% for 5 minutes → page
- Cumulative cost > $100/hour → page
- /health returning 503 > 2 minutes → page

That's the full alert set for a small LLM service. Resist the urge to add more — every alert costs human attention.

---

## Try this

1. **Run the real server.** `uvicorn openai.28_production_app_openai:app --port 8000`. Hit it with `curl -N http://localhost:8000/chat -X POST -d '{"question":"Hi"}'`. See the SSE stream live.

2. **Add the Dockerfile.** Copy the Dockerfile from this lesson, run `docker build -t agenticcourse-chat .` then `docker run -p 8000:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY agenticcourse-chat`. Hit `localhost:8000/health` — same behavior, now containerized.

3. **Deploy to Fly.io.** Get a free account, install `flyctl`, run `fly launch` then `fly secrets set OPENAI_API_KEY=...` then `fly deploy`. ~5 minutes from `git clone` to public URL.

4. **Add a `chat_total_seconds` percentile alert.** Compute p95 in PromQL: `histogram_quantile(0.95, sum(rate(chat_total_seconds_bucket[5m])) by (le))`. Configure Alertmanager / Grafana to page if > 6 seconds.

5. **Swap manual spans to OpenTelemetry.** `pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp`. Replace the `@contextmanager span(...)` with `tracer.start_as_current_span(...)`. Point at a local Jaeger via `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318`. Same traces, real distributed tracing.

6. **Add cost-per-user attribution.** Accept `user_id` in the request body, label the cost metric: `COST_TOTAL.labels(user=user_id).inc(cost)`. Grafana can now show top spenders.

---

## Mental model

> **Observability is not optional infrastructure — it's a property of the code itself.** Logs, metrics, traces, request IDs are not bolted on at the end. They're how the code talks to its operators in production.

If you can't answer "what happened on request 1c44c4d2…?" in under 30 seconds, your observability is broken. The whole point of this lesson is the discipline of *making sure you can answer that question*.

The four primitives you walked through — structured logs, request IDs, spans, metrics — are the entire toolkit. Every other observability tool (Datadog, Honeycomb, New Relic) is a UI on top of these four primitives. Master the primitives and the tools become interchangeable.

---

## FAQ

**Q: Why FastAPI and not Flask / Litestar / Django?**
FastAPI gives async + streaming + Pydantic + OpenAPI docs out of the box, and the surrounding ecosystem (uvicorn, starlette TestClient, OpenTelemetry instrumentation) is the most mature for LLM workloads in 2026. Litestar is also great; Flask is harder to make async-friendly. Pick whichever your team knows; the patterns in this lesson port directly.

**Q: Why expose Prometheus metrics directly instead of using a push gateway / agent?**
The pull model is more robust at small scale (Prometheus scrapes you; no work for the app), and Datadog / Grafana Cloud / etc. all have Prometheus-format scrapers built in. Push gateways are only for short-lived jobs (cron, batches) that finish before being scraped.

**Q: Why is `/health` calling the OpenAI API? Isn't that expensive?**
`models.retrieve("gpt-4o")` is a cheap metadata call — no inference. It exercises the auth + reachability path without paying for completion. Cost: ~$0. Latency: ~200-500ms.

**Q: How often is `/health` called?**
k8s default: every 10s. Fly default: every 30s. Cloud Run / ECS: every 30s. Add up to a few thousand calls/day from probes. Free, but you might want to cache the readiness result for 5 seconds to reduce noise.

**Q: Why both readiness AND a healthcheck in the Dockerfile?**
`/health` is for the orchestrator (k8s/Fly/ECS) — controls traffic routing. `HEALTHCHECK` in the Dockerfile is for the container runtime (Docker / Podman) — controls container lifecycle. Different layers, same idea.

**Q: How do I authenticate users on /chat?**
Add a `Depends(get_current_user)` to the endpoint:
```python
from fastapi import Depends, HTTPException, Header

async def get_current_user(authorization: str = Header(None)):
    token = (authorization or "").replace("Bearer ", "")
    user = verify_jwt(token)
    if not user: raise HTTPException(401)
    return user

@app.post("/chat")
async def chat(req: ChatRequest, request: Request, user=Depends(get_current_user)):
    ...
```

**Q: Can I run multiple model variants behind the same endpoint?**
Yes — accept `model` in the request, label the metrics: `CHAT_REQUESTS.labels(model=req.model).inc()`. Now your Grafana shows per-model breakdown of cost / latency / errors. This is how A/B testing works in production.

**Q: How do I handle long-running tool calls without blocking the stream?**
The pattern from Session 16 Demo 4: stream the first pass (which ends at the tool_calls block), run the tool (async if it's network-bound), then stream the second pass. The client UI renders a status indicator during the gap. For very long tools (>30s), surface progress events: yield `{"type": "tool_progress", "fraction": 0.4}`.

**Q: What about WebSocket instead of SSE?**
SSE is one-way (server → client) — perfect for streaming chat responses. WebSocket is two-way — needed if you want to interrupt the LLM, cancel mid-stream, send mid-stream user messages. Most production chat UIs use SSE. The remaining 5% use WebSocket for live collaboration features.

**Q: How does this lab interact with Sessions 14 + 15 + 16?**
- **Session 14 (eval)** — your CI runs `python labs/openai/25_evaluation_openai.py` before deploys; fails the deploy if quality regresses
- **Session 15 (cost)** — `chat_cost_usd_total` from this lab feeds into your Grafana cost dashboard; you cut cost with the levers and watch the metric drop
- **Session 16 (streaming)** — the actual stream implementation; this lesson wraps it in HTTP

All four sessions compose into a single production-ready service.

**Q: Where does OpenAI's dashboard (platform.openai.com) fit in?**
The OpenAI dashboard tracks billing + usage at the account level. Your `chat_cost_usd_total` should *match* what the dashboard shows (give or take rounding). If they diverge significantly, your cost calculation has a bug — typically a missed cached_tokens field.

**Q: Track F is complete — what's next?**
Track G — Architect Skills (Sessions 18-21): System design interview prep, red-teaming, governance & audit, UX patterns. The "senior IC" track. Or you can jump tracks per the menu.

---

## Related

- **Previous:** [27 — Streaming](27-streaming.md) — the streaming primitives this app wraps
- **Next:** Session 18 — System Design Interview Prep (start of Track G: Architect Skills)
- **Builds on:** [25 — Evaluation](25-evaluation.md) (the CI quality gate), [26 — Cost Optimization](26-cost-optimization.md) (the metric this app tracks), [27 — Streaming](27-streaming.md) (the chat endpoint pattern)
- **Track F status:** ✓ **COMPLETE** — Evaluation → Cost → Streaming → Deploy. You can now ship a real, observable, deployable LLM service. The next track shifts from *building* to *senior-IC skills* around the systems you build.
