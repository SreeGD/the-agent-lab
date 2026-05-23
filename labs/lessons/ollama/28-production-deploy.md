# 28 — Production Deploy + Observability (Session 17)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. The health check pings the local Ollama server instead of a cloud API. Code file: `labs/ollama/28_production_app_ollama.py`.

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

**Why this lesson now:** You have a tested (S14), optimized (S15), latency-tuned (S16) pipeline. What's left is making it run as a *service*: an HTTP API, observability, a container, and a one-command deploy. Track F closes here.

---

## File involved

| File | Role |
|---|---|
| [`28_production_app_ollama.py`](../ollama/28_production_app_ollama.py) | FastAPI app with `/chat` (SSE streaming), `/health` (liveness + readiness), `/metrics` (Prometheus). Structured JSON logs, request IDs threaded through, manual spans, latency metrics. Includes an in-process demo via FastAPI's `TestClient` so you can run it without binding a port. |

---

## Ollama-specific notes

- **Health check**: instead of pinging the Anthropic API, the readiness check pings `http://localhost:11434/api/tags` (Ollama's local REST API). Returns 503 if Ollama is not running.
- **Cost tracking**: Ollama has no API cost. The `chat_cost_usd_total` metric from the Anthropic version is replaced with `chat_inference_ms_total` — cumulative local inference time.
- **Connection**: uses `ChatOllama(model="llama3.2", base_url="http://localhost:11434")`.

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

This lesson wires up all seven in one ~250-line file.

---

## The analogy

**Renting an apartment vs. running a restaurant.**

Your Python script is your kitchen at home — works fine, only you eat there, no inspections.

A production service is a restaurant. Different requirements:
- A storefront (the HTTP API) — people can walk in
- A health permit (readiness endpoint) — proves the kitchen is open and safe
- Books (metrics tracking) — you know if you're making money
- Cameras (traces + structured logs) — when something goes wrong you can replay the night
- Standard recipes (Dockerfile) — anyone can run the same kitchen in another building
- A landlord (deploy target) — somewhere to actually open up

You can't open a restaurant without those. You can't ship AI without these.

---

## Visual

```
                     ┌────────────────────────────────────────┐
                     │           FastAPI app                  │
   ┌─────────┐  POST │                                        │
   │ Browser │──────►│  middleware: assign request_id ────────┤──► structured JSON log
   │  /CLI   │       │                                        │    {request_id, span, ...}
   └─────────┘       │  /chat ──► span("chat.llm_stream") ──► │
                     │            ChatOllama.stream()         │──► /metrics scraped by
                     │            yield SSE deltas            │    Prometheus / Datadog
                     │                                        │
   ┌─────────┐  GET  │  /health ──► ping ollama tags API ─────┤──► load balancer sees 503
   │   k8s   │──────►│            return {status, readiness}  │    → pulls pod out
   └─────────┘       │                                        │
                     │  /metrics ──► generate_latest() ───────┤──► Grafana dashboards
                     │                                        │
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
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
app = FastAPI(title="AgenticCourse Production Chat", version="0.1.0")

@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    return StreamingResponse(
        stream_chat(request.state.request_id, req.question),
        media_type="text/event-stream",
    )

@app.get("/health")
async def health():
    # liveness implicit, readiness = "can we reach Ollama?"
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
- Echoed back to the caller in the `x-request-id` response header

When a user reports a bug, that ID lets you grep across logs and traces. This is the single most important production hygiene practice you'll learn from this lesson.

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
{"timestamp": "2026-05-21T04:56:45Z", "level": "INFO", "logger": "chat", "message": "completed", "request_id": "1c44c4d2...", "chunks": 6, "input_tokens": 31, "output_tokens": 97, "inference_ms": 3283.19}
```

Why JSON? **Log aggregators ingest these directly** — no parsing rules, no fragile regexes. Datadog, CloudWatch Logs, Loki, Splunk all index any field automatically.

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

Each span emits a structured `span.start` + `span.end` with `latency_ms`. The JSON shape matches what OpenTelemetry emits — when you're ready to send traces to Honeycomb / Jaeger / Datadog APM, swap the contextmanager for a real tracer.

### 5. Prometheus metrics

```python
CHAT_REQUESTS = Counter("chat_requests_total", "Total chat requests received.")
CHAT_TTFT = Histogram("chat_ttft_seconds", "Time to first streamed token.",
                       buckets=(0.25, 0.5, 1.0, 2.0, 4.0, 8.0))
INFERENCE_TOTAL_MS = Counter("chat_inference_ms_total", "Cumulative local inference time (ms).")
```

Three metric kinds:
- **Counter** — monotonically increasing (requests, errors, cumulative time). Rate is computed at query time.
- **Histogram** — buckets for latency. Lets you compute percentiles in PromQL.
- **Gauge** — current value (not used here, but typical for "active sessions").

The right metric set for a local LLM service:
- Request volume + error rate (saturation + health)
- TTFT histogram + total-latency histogram (UX SLOs)
- Cumulative inference time (GPU/CPU utilization tracking)
- Per-model breakdown (label the metrics with `model=` for attribution)

### 6. Health checks — Ollama readiness

```python
@app.get("/health")
async def health():
    ready = False
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        ready = response.status_code == 200
    except Exception as e:
        error = str(e)
    return JSONResponse(
        {"status": "ok" if ready else "degraded",
         "liveness": True, "readiness": ready},
        status_code=200 if ready else 503,
    )
```

**Liveness** — "is the process up?" — always True if `/health` responds.
**Readiness** — "can it actually serve traffic?" — pinging `http://localhost:11434/api/tags` exercises Ollama reachability cheaply.

Why 503 on readiness failure? Kubernetes / Fly / ECS / Cloud Run all interpret 5xx as "not ready" and pull the pod out of load-balancer rotation. If Ollama is down, your pod stops getting traffic — automatic graceful degradation.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

In-process demo (no port binding, uses TestClient):
```bash
python ollama/28_production_app_ollama.py
```

Real server (binds port 8000):
```bash
./.venv/bin/python -m uvicorn 28_production_app_ollama:app --host 0.0.0.0 --port 8000
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

## Deploy artifacts

### `Dockerfile` (multi-stage, slim, non-root)

For deploying the FastAPI app alongside a locally-running Ollama:

```dockerfile
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser 28_production_app_ollama.py .

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "28_production_app_ollama:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Note:** for deployment with Ollama, you'd typically run Ollama separately (as a sidecar or on a GPU machine) and set `OLLAMA_BASE_URL` in the environment.

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

---

## Production patterns

### Secrets — never in env files

For Ollama-based services, secrets are typically limited to:
- Database credentials (for session storage)
- API keys for external services (search, databases)
- NOT an LLM API key (Ollama is local)

Rule: if a secret is committed anywhere in your repo, rotate it.

### Connection management

The `ChatOllama` client connects to the Ollama server. Keep:
- One client *per process* (instantiate at import time, not per-request)
- Async variant for async FastAPI routes (use `ChatOllama` with `astream`)

### Rate limits + error handling

Ollama can return errors if:
- The model is still loading (cold start)
- The GPU runs out of memory (OOM)
- The server is temporarily overloaded

```python
from langchain_core.exceptions import OutputParserException
try:
    ...
except Exception as e:
    CHAT_ERRORS.labels(type="ollama_error").inc()
    raise HTTPException(status_code=503, detail="Local model unavailable; retry")
```

### Autoscaling considerations

Ollama runs locally, so horizontal scaling means multiple Ollama instances (multiple machines/GPUs). The FastAPI app itself is stateless and scales normally; the bottleneck is the Ollama backend.

---

## Try this

1. **Run the real server.** `uvicorn 28_production_app_ollama:app --port 8000`. Hit it with `curl -N http://localhost:8000/chat -X POST -d '{"question":"Hi"}'`. See the SSE stream live.

2. **Stop Ollama mid-test.** Run `killall ollama` then hit `/health` — observe the 503 and `readiness: false`. Restart `ollama serve` and observe recovery.

3. **Add a `chat_total_seconds` percentile alert.** Compute p95 in PromQL: `histogram_quantile(0.95, sum(rate(chat_total_seconds_bucket[5m])) by (le))`. Configure Alertmanager / Grafana to page if > 8 seconds for local Ollama.

4. **Swap manual spans to OpenTelemetry.** `pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp`. Replace the `@contextmanager span(...)` with `tracer.start_as_current_span(...)`. Point at a local Jaeger. Same traces, real distributed tracing.

5. **Add inference-time-per-model attribution.** Label the `chat_inference_ms_total` metric with `model=`. When you switch between `llama3.2` and `llama3.2:3b`, Grafana shows per-model breakdown.

---

## Mental model

> **Observability is not optional infrastructure — it's a property of the code itself.** Logs, metrics, traces, request IDs are not bolted on at the end. They're how the code talks to its operators in production.

If you can't answer "what happened on request 1c44c4d2…?" in under 30 seconds, your observability is broken. The four primitives — structured logs, request IDs, spans, metrics — are the entire toolkit.

---

## FAQ

**Q: Why FastAPI and not Flask / Litestar / Django?**
FastAPI gives async + streaming + Pydantic + OpenAPI docs out of the box. The surrounding ecosystem (uvicorn, starlette TestClient, OpenTelemetry instrumentation) is the most mature for LLM workloads. Litestar is also great; Flask is harder to make async-friendly.

**Q: Why expose Prometheus metrics directly?**
The pull model is more robust at small scale (Prometheus scrapes you; no work for the app). Datadog / Grafana Cloud all have Prometheus-format scrapers built in.

**Q: How often is `/health` called?**
k8s default: every 10s. Fly default: every 30s. The Ollama API tags call is lightweight — add up to a few thousand calls/day from probes. Consider caching the readiness result for 5 seconds to reduce noise.

**Q: How do I handle long-running tool calls without blocking the stream?**
The pattern from Session 16 Demo 4: stream the first pass (which ends at the tool_use block), run the tool (async if it's network-bound), then stream the second pass. The client UI renders a status indicator during the gap.

**Q: How does this lab interact with Sessions 14 + 15 + 16?**
- **Session 14 (eval)** — your CI runs the eval script before deploys; fails the deploy if quality regresses
- **Session 15 (optimization)** — `chat_inference_ms_total` from this lab feeds into your dashboard; you optimize with model selection + compression and watch the metric drop
- **Session 16 (streaming)** — the actual stream implementation; this lesson wraps it in HTTP

All four sessions compose into a single production-ready service.

---

## Related

- **Previous:** [27 — Streaming](27-streaming.md) — the streaming primitives this app wraps
- **Next:** Session 18 — System Design Interview Prep (start of Track G: Architect Skills)
- **Builds on:** [25 — Evaluation](25-evaluation.md) (the CI quality gate), [26 — Cost Optimization](26-cost-optimization.md) (the metric this app tracks), [27 — Streaming](27-streaming.md) (the chat endpoint pattern)
- **Track F status:** ✓ **COMPLETE** — Evaluation → Cost → Streaming → Deploy. You can now ship a real, observable, deployable LLM service. The next track shifts from *building* to *senior-IC skills* around the systems you build.
