"""Production Deployment + Observability — turn the chatbot into a service.

A working pipeline in a Python script is not a product. Production needs
an HTTP API, structured logs, distributed traces, metrics, health checks,
cost tracking, a container, and a deploy target.

This file builds a real FastAPI service that wraps the streaming chain
from Session 16, with four observability surfaces:

  POST /chat     — SSE streaming endpoint, request_id threaded through
  GET  /health   — liveness + readiness probes
  GET  /metrics  — Prometheus exposition format (counters, histograms)
  Logs           — structured JSON, one event per span, ready for log
                   aggregation (Datadog / CloudWatch / Loki / etc.)

Run as a service:
    uvicorn 28_production_app_openai:app --host 0.0.0.0 --port 8000

Run the in-process demo (default `python 28_production_app_openai.py`):
    Uses FastAPI's TestClient to exercise /health, /chat, /metrics
    without binding a real port. Prints structured logs + metrics output.

Deploy artifacts (Dockerfile, fly.toml) are in the lesson markdown.
"""

import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Iterator

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel

load_dotenv()

MODEL = "gpt-4o"
client = openai.OpenAI()

PRICES = {
    "gpt-4o": {"in": 2.50, "out": 10.00},
}


# =====================================================================
# Structured JSON logging
# =====================================================================

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def log(name: str, message: str, **fields):
    """Emit a structured log line with arbitrary key/value fields."""
    logger = logging.getLogger(name)
    record = logger.makeRecord(
        name=name, level=logging.INFO, fn="", lno=0, msg=message,
        args=(), exc_info=None,
    )
    record.extra_fields = fields
    logger.handle(record)


# =====================================================================
# Manual span instrumentation (OpenTelemetry shape, without the dep).
# =====================================================================

@contextmanager
def span(name: str, **fields):
    """Wrap a block of code in a span — emit start + end logs with timing."""
    span_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    log("trace", f"span.start: {name}", span_id=span_id, span_name=name, **fields)
    try:
        yield span_id
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log("trace", f"span.error: {name}",
            span_id=span_id, span_name=name,
            latency_ms=round(elapsed_ms, 2), error=str(e))
        raise
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log("trace", f"span.end: {name}",
            span_id=span_id, span_name=name,
            latency_ms=round(elapsed_ms, 2))


# =====================================================================
# Prometheus metrics — use a private registry so multiple imports in
# the same Python process don't error on duplicate registration.
# =====================================================================

REGISTRY = CollectorRegistry()
CHAT_REQUESTS = Counter("chat_requests_total", "Total chat requests received.",
                        registry=REGISTRY)
CHAT_ERRORS = Counter("chat_errors_total", "Total chat requests that errored.",
                      registry=REGISTRY)
CHAT_TTFT = Histogram(
    "chat_ttft_seconds", "Time to first streamed token in seconds.",
    buckets=(0.25, 0.5, 1.0, 2.0, 4.0, 8.0),
    registry=REGISTRY,
)
CHAT_TOTAL = Histogram(
    "chat_total_seconds", "Total request duration in seconds.",
    buckets=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0),
    registry=REGISTRY,
)
COST_TOTAL = Counter("chat_cost_usd_total", "Cumulative spend in USD.",
                     registry=REGISTRY)


# =====================================================================
# FastAPI app
# =====================================================================

app = FastAPI(title="AgenticCourse Production Chat (OpenAI)", version="0.1.0")


class ChatRequest(BaseModel):
    question: str


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Generate a per-request UUID. Threaded through logs + response headers."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    log("http", "request.received",
        request_id=request_id, method=request.method, path=str(request.url.path))
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    log("http", "request.completed",
        request_id=request_id, status=response.status_code)
    return response


@app.get("/health")
async def health():
    """Liveness (process up) + readiness (OpenAI API reachable)."""
    with span("health.check"):
        ready = False
        error = None
        try:
            # Minimal check: list models (fast, cheap)
            client.models.list()
            ready = True
        except Exception as e:
            error = str(e)
        return JSONResponse({
            "status": "ok" if ready else "degraded",
            "liveness": True,
            "readiness": ready,
            "error": error,
        }, status_code=200 if ready else 503)


@app.get("/metrics")
async def metrics():
    """Prometheus exposition format — scrape this with your monitoring stack."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def stream_chat(request_id: str, question: str) -> Iterator[bytes]:
    """SSE generator. Yields server-sent event lines."""
    CHAT_REQUESTS.inc()
    start = time.perf_counter()
    first_token_at = None
    chunk_count = 0
    prompt_tokens = 0
    completion_tokens = 0

    try:
        with span("chat.llm_stream", request_id=request_id, question=question[:60]):
            stream = client.chat.completions.create(
                model=MODEL,
                max_completion_tokens=200,
                messages=[
                    {"role": "system", "content": "Answer concisely. 2-3 sentences max."},
                    {"role": "user", "content": question},
                ],
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    if first_token_at is None:
                        first_token_at = time.perf_counter() - start
                        CHAT_TTFT.observe(first_token_at)
                        log("chat", "ttft",
                            request_id=request_id,
                            ttft_ms=round(first_token_at * 1000, 2))
                    chunk_count += 1
                    payload = json.dumps({"type": "token", "delta": text})
                    yield f"data: {payload}\n\n".encode()
                # Collect final usage from the last chunk
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens

        p = PRICES[MODEL]
        cost = (prompt_tokens * p["in"] + completion_tokens * p["out"]) / 1_000_000

        COST_TOTAL.inc(cost)

        total = time.perf_counter() - start
        CHAT_TOTAL.observe(total)

        log("chat", "completed",
            request_id=request_id,
            chunks=chunk_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost, 6),
            total_ms=round(total * 1000, 2))

        done = json.dumps({
            "type": "done",
            "request_id": request_id,
            "cost_usd": round(cost, 6),
            "total_ms": round(total * 1000, 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        })
        yield f"data: {done}\n\n".encode()

    except Exception as e:
        CHAT_ERRORS.inc()
        log("chat", "errored", request_id=request_id, error=str(e))
        err = json.dumps({"type": "error", "request_id": request_id, "error": str(e)})
        yield f"data: {err}\n\n".encode()


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    request_id = request.state.request_id
    return StreamingResponse(
        stream_chat(request_id, req.question),
        media_type="text/event-stream",
        headers={"x-request-id": request_id},
    )


# =====================================================================
# In-process demo (TestClient — no actual network)
# =====================================================================

def run_demo():
    from fastapi.testclient import TestClient

    print("\n" + "=" * 70)
    print("PRODUCTION APP (OpenAI) — observability demo via TestClient (in-process)")
    print("=" * 70)
    print("  For real deploys: `uvicorn 28_production_app_openai:app --host 0.0.0.0 --port 8000`")
    print("  This demo uses FastAPI's TestClient — same code paths, no real port.")

    with TestClient(app) as test:
        print("\n>>> GET /health")
        r = test.get("/health")
        print(f"  status={r.status_code}  body={r.json()}")

        print("\n>>> POST /chat  (streaming SSE)")
        with test.stream("POST", "/chat", json={"question": "What is LangChain LCEL?"}) as r:
            print(f"  status={r.status_code}  x-request-id={r.headers.get('x-request-id', '?')}")
            print(f"  --- streamed body ---")
            print(f"  > ", end="", flush=True)
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                if payload["type"] == "token":
                    sys.stdout.write(payload["delta"])
                    sys.stdout.flush()
                elif payload["type"] == "done":
                    print(f"\n  [done] cost=${payload['cost_usd']:.6f}  total_ms={payload['total_ms']:.0f}  "
                          f"in={payload['prompt_tokens']} out={payload['completion_tokens']}")
                elif payload["type"] == "error":
                    print(f"\n  [error] {payload['error']}")

        print("\n>>> GET /metrics  (Prometheus exposition — filtered to chat_ metrics)")
        r = test.get("/metrics")
        wanted = (
            "chat_requests_total", "chat_errors_total",
            "chat_ttft_seconds_count", "chat_ttft_seconds_sum",
            "chat_total_seconds_count", "chat_total_seconds_sum",
            "chat_cost_usd_total",
        )
        for line in r.text.splitlines():
            if any(line.startswith(name + " ") or line == "# HELP " + name + " "[:0]
                   for name in wanted):
                if not line.startswith("#"):
                    print(f"  {line}")


if __name__ == "__main__":
    setup_logging()
    run_demo()
    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • Structured JSON logs were emitted to stdout for every request,\n"
        "    every span, and every chat event. Log aggregators (Datadog,\n"
        "    Loki, CloudWatch) ingest these directly — no parsing rules.\n\n"
        "  • Every request got a UUID `request_id` threaded through the\n"
        "    middleware → spans → chat events → response header. When a\n"
        "    user reports a bug, that ID lets you grep all related log\n"
        "    lines across services.\n\n"
        "  • Spans wrap each significant block of work (health check, chat\n"
        "    stream). Each span emits start + end with latency_ms. The\n"
        "    JSON shape matches OpenTelemetry — swap the contextmanager\n"
        "    for a real `tracer.start_as_current_span()` to send to\n"
        "    Honeycomb / Jaeger / Datadog APM in 5 lines.\n\n"
        "  • Prometheus metrics expose request counts, error counts, TTFT\n"
        "    + total latency histograms, and cumulative cost in USD.\n"
        "    Grafana + alertmanager turn these into dashboards + pages.\n\n"
        "  • /health returns 503 if the OpenAI API is unreachable.\n"
        "    Kubernetes / Fly / ECS use this for readiness probes — pulls\n"
        "    bad pods out of load-balancer rotation automatically.\n\n"
        "  • The deploy artifacts (Dockerfile + fly.toml) are in the\n"
        "    lesson markdown. `fly launch && fly deploy` is the whole\n"
        "    deploy story once you have those files."
    )
