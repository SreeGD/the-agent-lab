# Session 08b — Inference Platforms & Self-Hosting

**Track C — Alt Architectures | Week 3, Thursday | 2 hours**

**Prerequisites:** Session 08 (AI Gateway / LiteLLM)

---

## Why Inference Platform Choice Matters

Every token your agent generates has three costs: money, latency, and data
exposure.  Different deployment models trade these off in very different ways.
Understanding the landscape lets you pick the right tool for each workload.

---

## 1. Cost / Latency / Privacy Trade-off Matrix

| Deployment model | $/1M tokens | P50 latency | Data leaves your infra? | GPU required? |
|---|---|---|---|---|
| Groq (LPU cloud) | ~$0.05–0.20 | 200–600 ms | Yes | No |
| Together AI | ~$0.20–0.90 | 500 ms–2 s | Yes | No |
| Fireworks AI | ~$0.20–0.90 | 400 ms–1.5 s | Yes | No |
| AWS Bedrock | ~$0.20–3.00 | 500 ms–3 s | Stays in your AWS account | No |
| Google Vertex AI | ~$0.25–3.00 | 500 ms–3 s | Stays in your GCP project | No |
| Azure OpenAI | ~$0.50–3.00 | 600 ms–3 s | Stays in your Azure tenant | No |
| Ollama (local CPU) | $0 (hardware) | 2–30 s | Never leaves device | No |
| Ollama (local GPU) | $0 (hardware) | 200 ms–2 s | Never leaves device | Yes |
| vLLM (GPU server) | $0 + GPU cost | 100 ms–1 s | Never leaves infra | Yes |

**Rule of thumb:**
- Prototype / high-throughput, cost-sensitive → Groq
- Production, needs vendor SLA → Bedrock / Vertex / Azure
- Air-gapped / regulated data → Ollama or vLLM on your own hardware

---

## 2. Cloud Fast-Inference Providers

These providers run open-weight models (Llama, Mistral, Qwen, …) on
custom hardware optimised for token throughput.  All expose an
OpenAI-compatible REST API, so LiteLLM wraps them transparently.

| Provider | Speciality | Example models | LiteLLM prefix |
|---|---|---|---|
| **Groq** | LPU hardware — fastest TTFT | Llama-3-8B / 70B, Mixtral | `groq/` |
| **Together AI** | Wide model catalogue, fine-tuning | Llama-3, Qwen, DeepSeek | `together_ai/` |
| **Fireworks AI** | FireAttention kernel, JSON mode | Llama-3, Mixtral, Qwen | `fireworks_ai/` |
| **Replicate** | Serverless, GPU cold-start | Many open models | `replicate/` |

### Authentication

Each provider expects an API key in an environment variable:

```bash
GROQ_API_KEY=...
TOGETHERAI_API_KEY=...
FIREWORKS_AI_API_KEY=...
```

LiteLLM picks these up automatically — no extra config needed.

### Code Example

```python
import litellm

providers = [
    {"name": "groq",      "litellm_model": "groq/llama3-8b-8192",     "cost_per_1m": 0.05},
    {"name": "together",  "litellm_model": "together_ai/togethercomputer/llama-3-8b", "cost_per_1m": 0.20},
    {"name": "fireworks", "litellm_model": "fireworks_ai/accounts/fireworks/models/llama-v3-8b-instruct", "cost_per_1m": 0.20},
]

for p in providers:
    resp = litellm.completion(
        model=p["litellm_model"],
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=64,
    )
    print(p["name"], resp.choices[0].message.content)
```

---

## 3. Managed Cloud AI — Bedrock, Vertex, Azure

These are the **enterprise-grade** options.  The underlying models are
identical or similar to the public APIs, but your data stays inside your
cloud account and you get:

- VPC endpoints (traffic never crosses the public internet)
- IAM / RBAC integration with your existing cloud identity
- Compliance certs (SOC 2, HIPAA, ISO 27001)
- SLAs with financial penalties

| Feature | AWS Bedrock | Google Vertex AI | Azure OpenAI |
|---|---|---|---|
| Claude access | Yes (Anthropic on Bedrock) | No (Google models) | No (OpenAI models) |
| Llama access | Yes | Yes | Yes |
| GPT-4o access | No | No | Yes |
| Gemini access | No | Yes | No |
| Data residency | AWS region | GCP region | Azure region |
| LiteLLM prefix | `bedrock/` | `vertex_ai/` | `azure/` |

### LiteLLM for managed clouds

```python
# AWS Bedrock — uses boto3 credentials (env vars or IAM role)
litellm.completion(
    model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    messages=[{"role": "user", "content": "Hello"}],
)

# Google Vertex AI — uses GOOGLE_APPLICATION_CREDENTIALS
litellm.completion(
    model="vertex_ai/gemini-1.5-pro",
    messages=[{"role": "user", "content": "Hello"}],
    vertex_project="my-gcp-project",
    vertex_location="us-central1",
)

# Azure OpenAI — set AZURE_API_KEY / AZURE_API_BASE / AZURE_API_VERSION
litellm.completion(
    model="azure/gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

**When to choose managed cloud AI:**
- Your data is regulated (PII, PHI, financial records)
- You already have AWS / GCP / Azure infrastructure and IAM
- You need guaranteed uptime and vendor SLAs
- You want to avoid per-call rate limits of public APIs

---

## 4. Self-Hosting with Ollama

Ollama wraps `llama.cpp` in a Docker image and exposes an
OpenAI-compatible API on `localhost:11434`.  Zero cloud dependency.

### Architecture

```
┌─────────────────────────────────┐
│         Your application        │
│   (labs/08b_inference_platforms)│
└────────────────┬────────────────┘
                 │  HTTP POST /v1/chat/completions
                 ▼
┌─────────────────────────────────┐
│      Ollama (Docker container)  │
│   image: ollama/ollama:latest   │
│   port: 11434                   │
│   volume: ollama_data:/root/.ollama │
└────────────────┬────────────────┘
                 │  GGUF model weights
                 ▼
┌─────────────────────────────────┐
│   llama.cpp runtime (CPU/GPU)   │
│   quantised model: llama3.gguf  │
└─────────────────────────────────┘
```

### Quick Start

```bash
# 1 — Start the Ollama server
docker compose -f labs/docker/ollama-compose.yml up -d

# 2 — Pull a model (first run only; ~4 GB for llama3)
docker compose -f labs/docker/ollama-compose.yml exec ollama ollama pull llama3

# 3 — Test directly
curl http://localhost:11434/api/generate \
  -d '{"model":"llama3","prompt":"Hello"}'

# 4 — Call via LiteLLM / the lab script
python labs/08b_inference_platforms.py
```

### `labs/docker/ollama-compose.yml` (abbreviated)

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: >
      sh -c "ollama serve & sleep 5 && ollama pull llama3 && wait"

volumes:
  ollama_data:
```

### Calling Ollama from Python

```python
import litellm

def call_ollama(prompt: str, model: str, base_url: str) -> str:
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        api_base=base_url,
    )
    return response.choices[0].message.content or ""

output = call_ollama("Hello", "llama3", "http://localhost:11434/v1")
```

LiteLLM translates the `ollama/` prefix into the correct local API call.

---

## 5. vLLM — GPU-Accelerated Self-Hosting

Ollama uses `llama.cpp` (CPU-optimised, quantised).  For production
self-hosting on GPUs, **vLLM** gives higher throughput via PagedAttention
and continuous batching.

### One-liner Docker start (NVIDIA GPU)

```bash
docker run --runtime=nvidia --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3-8B-Instruct \
  --dtype float16
```

Then call it like any OpenAI-compatible endpoint:

```python
litellm.completion(
    model="openai/meta-llama/Llama-3-8B-Instruct",
    messages=[{"role": "user", "content": "Hello"}],
    api_base="http://localhost:8000/v1",
    api_key="dummy",   # vLLM doesn't enforce keys by default
)
```

### Ollama vs vLLM

| | Ollama | vLLM |
|---|---|---|
| Hardware | CPU (or GPU) | GPU required |
| Quantisation | GGUF (Q4/Q8) | float16 / bfloat16 |
| Throughput (8B model) | 10–50 tok/s CPU | 800–2000+ tok/s A100 |
| Startup complexity | `docker compose up` | Needs CUDA driver + NVIDIA runtime |
| Best for | Local dev, air-gapped laptops | Production GPU clusters |

---

## 6. Lab Exercise

Run `labs/08b_inference_platforms.py` in two modes:

**Part 1 — Cloud comparison (API keys required):**

```bash
# Set at least one key
export GROQ_API_KEY=...
python labs/08b_inference_platforms.py
```

Observe the latency and throughput table printed to stdout.

**Part 2 — Ollama self-hosting (Docker required):**

```bash
docker compose -f labs/docker/ollama-compose.yml up -d
# Wait ~60 s for the model to download on first run
python labs/08b_inference_platforms.py
```

---

## Key Takeaways

1. **LiteLLM is the universal adapter** — one API call works for Groq,
   Together, Bedrock, Vertex, Ollama, and vLLM.
2. **Cost and latency are inversely coupled** — Groq is cheapest and
   fastest, managed cloud is most expensive and has the highest latency,
   but data stays inside your perimeter.
3. **Self-hosting eliminates per-token cost** but shifts the burden to
   GPU procurement and MLOps.
4. **Ollama** is the right choice for local dev, demos, and regulated
   environments with no GPU budget.
5. **vLLM** is the right choice when you have GPUs and need production
   throughput.

---

## Further Reading

- [LiteLLM provider docs](https://docs.litellm.ai/docs/providers)
- [Ollama model library](https://ollama.com/library)
- [vLLM PagedAttention paper](https://arxiv.org/abs/2309.06180)
- [Groq LPU architecture](https://groq.com/technology/)
- [AWS Bedrock supported models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
