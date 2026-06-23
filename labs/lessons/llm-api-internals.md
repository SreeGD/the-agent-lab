# Deep Dive — What Happens When You Call an LLM API

> **The full journey in ~400ms.** Every token you send passes through 7 distinct layers before the model generates a single character. Understanding this journey explains why your costs look the way they do, why latency is unpredictable, why streaming feels faster, and why prompt caching is the single highest-leverage optimization available to you.

---

## Roadmap — where this sits

```
Phase 1 (L01-11)   Phase 2: Architect Skills
Foundation

  ✓ 01-17                ▶ LLM API INTERNALS  ◄ YOU ARE HERE
  (foundation)
                         ○ 18-anthropic-sdk
                         ○ 19-ai-gateway
                         ○ 20-files-document-ai
```

**Why this lesson now:** Every lesson from L01 to L17 called `model.invoke()` or `client.messages.create()` as a black box. Before going deeper on SDK patterns, AI gateways, and cost optimization, you need to know what actually happens inside that call. This mental model will change how you design every agent you build from here.

---

## The Full Journey (~400ms)

```
Your code                                                Response
POST /v1/chat/completions                                ←────────────────────
        │                                                                     │
        ▼                                                                     │
┌───────────────────────────────────────────────────────────────────────────┐│
│ 1. API Gateway        (~5ms)   TLS, auth, rate limit, billing starts      ││
│ 2. Load Balancer      (~2ms)   geographic routing, health checks          ││
│ 3. Tokenization       (~3ms)   text → token IDs, count = your cost        ││
│ 4. Model Router       (~1ms)   HIDDEN — version pinning, queue mgmt       ││
│ 5. Inference Engine   (300-800ms) ← 95% of your wait time                 ││
│    ├── Prefill Phase           all input tokens processed in parallel     ││
│    ├── Decode Phase            autoregressive token-by-token generation   ││
│    ├── Attention Mechanism     Q×K softmax × V                            ││
│    └── Hardware Layer          A100/H100, NVLink, tensor parallelism      ││
│ 6. Post-Processing    (~5ms)   safety check, format JSON, stop sequences  ││
│ 7. Response & Billing (~5ms)   streaming chunks, usage metadata           ││
└───────────────────────────────────────────────────────────────────────────┘│
        └────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — API Gateway (~5ms)

This is the fortified perimeter. Four things happen before your request touches any AI logic:

**TLS termination:** Your HTTPS connection is decrypted here. The interior of the data center communicates unencrypted (faster). This is why API keys in transit are safe — TLS protects them end-to-end.

**Authentication:** Your API key is validated against a key store. This is where `401 Unauthorized` originates. Note: the key is never sent to the model.

**Rate limiting (TPM/RPM):** Tokens-per-minute and requests-per-minute limits are enforced here via a sliding window counter. If you hit the limit, you get `429 Too Many Requests` before any compute is consumed. This is why exponential backoff saves money — you're not charged for rejected requests.

**Billing meter starts:** The moment your request passes the gateway, the clock starts. You are billed for input tokens even if the model never generates output (e.g., if it errors mid-generation).

**Key insight for agent design:** Rate limiting happens at the gateway, not at the model. When you run parallel fan-out agents, all branches share the same TPM bucket. Five agents running simultaneously consume 5× the tokens per second.

---

## Layer 2 — Load Balancer (~2ms)

The load balancer routes your validated request to one of several GPU clusters using:

- **Least-connections algorithm:** Routes to the cluster currently handling the fewest active requests
- **Geographic routing:** Requests from India may route to Mumbai or Singapore clusters, reducing network latency
- **Health checks:** Unhealthy nodes (crashed workers, full memory) are excluded from routing

**Why this matters:** This is why latency varies between identical requests. A request at 2 AM routes to an idle cluster and completes in 300ms. The same request at peak load routes to a busy cluster and takes 800ms. The model did not change. The queue changed.

**For enterprise deployments:** Providers like OCI, AWS Bedrock, and Azure OpenAI let you provision dedicated inference endpoints that bypass the shared load balancer. You pay more; you get consistent latency.

---

## Layer 3 — Tokenization (~3ms)

This is where your text becomes numbers.

**How it works (BPE — Byte Pair Encoding):**
```
"Hello world" → [15339, 1917]   (GPT tokenizer)
"Hello world" → [9906, 1917]    (Llama tokenizer)
"Hello world" → [32331, 14973]  (Claude tokenizer)
```

Rules of thumb:
- ~4 characters per token (English prose)
- ~1 token per word (simple vocabulary)
- Code, URLs, numbers tokenize less efficiently (~2-3 chars/token)
- Non-English languages tokenize poorly (~1-2 chars/token)

**Token count = your cost.** The tokenizer output length is what gets billed. This is the only number that matters for cost optimization.

```python
# Count tokens before sending (avoid surprises)
import anthropic
client = anthropic.Anthropic()

# Anthropic provides a count_tokens endpoint
response = client.messages.count_tokens(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": your_prompt}]
)
print(f"Will cost: {response.input_tokens} input tokens")
```

**Critical:** Different providers use different tokenizers. A 1,000-token prompt on OpenAI may be 1,100 tokens on Claude or 950 tokens on Gemini. Never assume token counts transfer across providers.

---

## Layer 4 — Model Router (The Hidden Layer, ~1ms)

This layer is undocumented by providers but real. It does three things:

**Model version pinning:** `claude-sonnet-4-6` is an alias. The router maps it to a specific model version that may be updated without warning. This is why outputs can drift over time on the same prompt.

**Capacity-aware routing:** If the Large Model cluster is at capacity, requests may be queued or routed to a smaller fallback model (at the same price). This is rare but happens at peak load.

**Queue management:** During peak load, requests wait here. This is the second source of latency variance (after the inference engine itself). A queue of 50 requests adds 50 × average_inference_time to your wait.

**For production systems:** This is why AI gateways (L19) are valuable. A gateway like LiteLLM adds its own routing layer on top, giving you control over fallbacks, retries, and model selection that the provider's hidden router doesn't expose.

---

## Layer 5 — Inference Engine (300–800ms, 95% of your wait)

This is where language models actually generate text. Three sub-phases:

### 5a. Prefill Phase

All input tokens are processed **in parallel** in one forward pass through the model.

```
Input: "The capital of France is"
        [Token 1] [Token 2] [Token 3] [Token 4] [Token 5]
             ↓         ↓         ↓         ↓         ↓
        [All processed simultaneously on GPU]
             ↓
        KV Cache generated (Key-Value pairs for attention)
```

**Why this matters:** Prefill time scales with input length, but sublinearly because of parallelism. Doubling your input roughly 1.5× the prefill time, not 2×. This is why long system prompts are less expensive than they appear.

**KV Cache:** The key optimization. The attention computation for every input token is cached in GPU HBM memory. These cached key-value pairs are reused during decode. This is the physical mechanism behind **prompt caching** — the provider stores your KV cache between requests so you don't pay to recompute it.

### 5b. Decode Phase (Autoregressive Generation)

After prefill, the model generates output **one token at a time**. Each token requires a full forward pass.

```
Input KV Cache + "is" → Softmax → Sample → "Paris"
Input KV Cache + "Paris" → Softmax → Sample → "."
Input KV Cache + "." → Softmax → Sample → [END]
```

This is why **output tokens cost more than input tokens** — each output token requires its own forward pass. Input tokens only require one pass (prefill). A response with 500 output tokens requires 500 sequential forward passes.

**Temperature controls this step:** Temperature scales the logits before softmax. Temperature = 0 → argmax (deterministic). Temperature = 1 → sample from distribution. Temperature > 1 → flatter distribution, more random.

**top_p / top_k sampling:** Before sampling, low-probability tokens are filtered. top_k keeps only the k highest-probability tokens. top_p keeps the smallest set of tokens whose cumulative probability ≥ p. Most providers default to top_p = 1 (no filtering).

### 5c. Attention Mechanism

Each decode step runs the full attention computation:

```
Q = query vector (current token)
K = key vectors (all prior tokens, from KV cache)
V = value vectors (all prior tokens, from KV cache)

Attention = softmax(Q × K^T / √d_k) × V
```

In plain English: the model computes how relevant each prior token is to the current token (Q×K), normalizes it (softmax), and takes a weighted sum of all prior token values (×V). This weighted sum is what flows into the feed-forward network.

**32-128 attention heads run in parallel** — each head learns to attend to different linguistic relationships (syntax, semantics, coreference, etc.).

**Flash Attention:** A memory-efficient implementation that avoids materializing the full attention matrix (O(n²) memory → O(n) memory). All modern inference uses this.

**GQA/MQA (Grouped Query Attention):** Instead of one K,V pair per attention head, multiple heads share K,V pairs. Reduces KV cache size dramatically — enabling longer contexts on the same hardware.

### 5d. Hardware Layer

```
A100 GPU (80GB HBM)
├── 312 TFLOPS (BF16)
├── 6,912 CUDA cores
├── 600 GB/s memory bandwidth
└── Connected via NVLink (600 GB/s GPU-to-GPU)

H100 GPU (80GB HBM3)
├── 1,979 TFLOPS (BF16) — 6× faster than A100
├── 16,896 CUDA cores
└── NVSwitch (900 GB/s GPU-to-GPU)
```

Large models (70B+) are split across multiple GPUs via **tensor parallelism** — each GPU holds a shard of the weight matrix. NVLink enables fast all-reduce communication between shards.

**Cost reality:** GPU compute costs $2–5/hour (A100) to $8–12/hour (H100). Inference is ~300–800ms. A single H100 at $10/hour running at 100% utilization costs $0.0028 per inference. Providers charge $15/million output tokens (Claude Sonnet) = $0.0075 per 500-token response. The margin is thin; scale is everything.

---

## Layer 6 — Post-Processing (~5ms)

Three checks run on every generated response before it leaves the inference cluster:

**Stop sequences:** If any configured stop sequence appears in output, generation halts and the sequence is stripped. This is how `"Human:"` in a chat template stops the model from roleplaying both sides.

**Safety classifier:** A fast, small classifier runs on the output. If flagged, the response is blocked and a refusal is returned. This classifier is separate from the model — it cannot be prompted away.

**Format response:** Raw logits → decoded text → JSON response schema (`{"content": [...], "usage": {...}}`). This is where `finish_reason` is set: `stop`, `length`, `tool_use`, `end_turn`.

**Key insight:** The safety filter can block responses the model "wanted" to generate. From the model's perspective, generation completed successfully. The blocking happens here, after the model's work is done. You are still billed for those tokens.

---

## Layer 7 — Response & Billing (~5ms)

**Streaming:** Instead of waiting for complete generation, the API sends tokens as they are decoded. Each token arrives as a Server-Sent Event (SSE). This is why streaming **feels** faster — time-to-first-token is typically 200–400ms regardless of output length.

```
Non-streaming: wait 3 seconds → receive 500 tokens at once
Streaming:     wait 200ms → first token → token/50ms → done in 2.5s
```

Both take the same total compute time. Streaming reduces perceived latency.

**Usage metadata:** Every response includes:
```json
{
  "usage": {
    "input_tokens": 1024,
    "output_tokens": 312,
    "cache_read_input_tokens": 800,    // tokens served from KV cache
    "cache_creation_input_tokens": 224  // tokens that created new cache
  }
}
```

**Prompt caching economics:**
- Normal input token: $3.00/million (Sonnet)
- Cache write token: $3.75/million (25% premium to store)
- Cache read token: $0.30/million (90% discount to retrieve)

If you send the same 1,000-token system prompt 100 times:
- Without caching: 100 × 1,000 × $3/M = $0.30
- With caching: 1 × $3.75/M + 99 × $0.30/M = $0.0337

**89% cost reduction.** This is the highest-leverage optimization in the entire stack.

---

## Layer 8 — Logging & Observability

Every call is logged by the provider:
- Latency at each layer
- Token counts (input/output/cached)
- Model version used
- Safety flags triggered
- Geographic endpoint used

Provider dashboards expose this data. For enterprise deployments, you pipe it to your own observability stack (Prometheus, Datadog, CloudWatch) via the usage metadata in every response.

---

## Mental Models — What This Changes

### Why output tokens cost more
Input = 1 forward pass (prefill, parallel). Output = N forward passes (decode, sequential). A 500-token response runs the GPU 500 times. Price reflects compute.

### Why streaming feels faster
Time-to-first-token ≠ total generation time. Streaming sends token 1 at t=200ms. Non-streaming sends all tokens at t=2500ms. Same GPU work; different delivery.

### Why prompt caching is architectural, not optional
The KV cache is the physical artifact of prefill computation. Reusing it means not re-running prefill. At scale (10k requests/day with a 2k-token system prompt), the difference between cached and uncached is $500/month vs. $5/month.

### Why latency is stochastic
Three sources of variance: queue depth (load balancer), KV cache availability (did your cache expire?), and decode length (model decides when to stop). You cannot fully control any of these.

### Why the model router is dangerous
`claude-sonnet-4-6` is not pinned to a specific model version. Providers update the alias. Your outputs can silently drift. For production: pin to a dated version ID when it matters, test against version updates explicitly.

---

## Lab

See `llm_api_internals.py` — hands-on exercises observing:
1. Token counting before sending
2. Measuring time-to-first-token vs. total time
3. Streaming vs. non-streaming latency comparison
4. Prompt caching: measuring cache write vs. cache read cost
5. Observing how output length affects total latency
6. Cost estimation function for any prompt

---

## Key numbers to memorise

| Metric | Value |
|---|---|
| Inference share of latency | 95% |
| Typical chars per token | ~4 (English prose) |
| Prefill vs. decode cost ratio | Input ≈ 10× cheaper than output (Claude Sonnet) |
| Prompt cache discount | 90% off input token price |
| Time-to-first-token | 200–400ms (Sonnet) |
| Total latency range | 300ms (short) → 30s (long output) |
| GPU compute cost | $2–12/hour (A100–H100) |

---

## FAQ

**Q: Why does the same prompt sometimes produce different outputs?**
A: Temperature sampling is stochastic. Even at temperature = 0, floating-point non-determinism across GPU shards means outputs can vary. For true reproducibility, use a fixed seed if the provider supports it (most don't).

**Q: Why do I get billed for a failed request?**
A: Billing starts at the API gateway (Layer 1). If your request was tokenized and queued, you pay for input tokens even if generation fails. Only requests rejected at rate limiting (429) are not billed.

**Q: Why is my cached prompt not hitting the cache?**
A: Three reasons: (1) cache TTL expired (5 minutes on Anthropic), (2) you changed the system prompt even slightly — cache is byte-exact, (3) you didn't mark the content block with `cache_control`. Check `cache_read_input_tokens` in the usage field to verify.

**Q: Why does my agent's second call take longer than the first?**
A: First call: cold KV cache, full prefill. Second call with identical system prompt: cache hit on prefix. If the second call is slower, your system prompt changed (different variable interpolated in) or the TTL expired.

**Q: What is the context window limit physically?**
A: The KV cache must fit in GPU HBM memory. A 200k token context on Claude uses ~100GB of KV cache. This requires multiple H100s. Providers gate context window by hardware tier — longer context = more expensive inference = higher price tier.

---

## Related

- **Previous:** L17 — Claude Skills Router
- **Next:** L18 — Anthropic SDK (direct)
- **Connects to:** L04 (Prompt Caching), L26 (Cost Optimization), L27 (Streaming), L28 (Production Deployment)
- **Infographic source:** Brij Kishore Pandey — "What Happens When You Call Any LLM API"
