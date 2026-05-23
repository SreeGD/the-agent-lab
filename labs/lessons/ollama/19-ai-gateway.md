# 19 — AI Gateway (Session 8)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/19_ai_gateway_ollama.py`.

> **One Python API → 100+ LLM providers.** LiteLLM (and its hosted siblings OpenRouter, Vercel AI Gateway) put a unified control plane between your app and the multiplying LLM ecosystem. Same call shape regardless of provider. Fallbacks, retries, cost tracking, and auth all live in one layer — so your app code stays clean even when your model mix doesn't.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: ✓ all 3 done
                                                           Track B: ✓ all 3 done
                                                           Track C: Alt Architectures
                                                             ✓ Session 7: Native SDK
                                                             ▶ Session 8: AI GATEWAY  ◄ HERE  (Track C COMPLETE)
                                                           Track D: ○ Files & Doc AI
                                                           Track E: ○ Custom Graphs
                                                           Track E.5: ○ RAG Architectures (Hybrid/Graph/CRAG)
                                                           Track F: ○ Production
```

**Why this lesson now:** Session 7 showed how to drop LangChain. Session 8 shows how to **drop provider lock-in**. After this you can pair any framework choice with any provider mix — independently.

---

## Files involved

| File | Role |
|---|---|
| [`19_ai_gateway_ollama.py`](../ollama/19_ai_gateway_ollama.py) | Three LiteLLM demos: provider abstraction, model bake-off, fallback chain |

---

## What problem it solves

You ship an AI feature on Ollama. Six months later, you need cloud burst capacity. Or your CFO says a smaller model is cheaper for guardrail judges. Or your enterprise customer wants GPT-4 specifically. Three real scenarios; three reasons your code shouldn't have `from langchain_ollama import ChatOllama` hardwired into every endpoint.

**AI Gateway centralizes the provider decision** — one config flip swaps Ollama for GPT, or routes 10% of traffic to a new model, or fails over Ollama → Groq → OpenAI on capacity limits. Your application code never knew the provider changed.

Without a gateway, every team that wants to add a provider rewrites every call site.

---

## The analogy

**A power strip with surge protection.**

Without a gateway: every appliance plugs directly into a different wall outlet. Different voltages, different plugs. Want to swap your toaster's electricity supplier? Rewire the kitchen.

With a gateway: appliances plug into one power strip. The strip handles voltage conversion (provider auth), surge protection (rate limits + retries), and you can switch the upstream supplier without touching any appliance.

LiteLLM is the power strip. Ollama, GPT, Gemini, Mistral, Bedrock are the suppliers. Your app is the appliance.

---

## Visual

```
                    YOUR APP CODE
                          │
                          ▼
   ┌────────────────────────────────────────────┐
   │   AI GATEWAY (LiteLLM / OpenRouter / ...)  │
   │                                            │
   │   ┌──────────────────────────────────┐    │
   │   │  litellm.completion(             │    │
   │   │    model="ollama/llama3.2",      │    │
   │   │    messages=[...],               │    │
   │   │    fallbacks=[...],              │    │
   │   │  )                               │    │
   │   └──────────────────────────────────┘    │
   │                                            │
   │   - Per-provider auth (env vars)           │
   │   - Retry on transient errors              │
   │   - Fallback chain on hard failures        │
   ���   - Cost tracking (per call + aggregate)   │
   │   - Rate limit enforcement                 ��
   │   - Optional self-hosted proxy             │
   └────┬───────┬───────┬───────┬───────────────┘
        │       │       │       │
        ▼       ▼       ▼       ▼
      Ollama  OpenAI  Gemini  Bedrock  ... 100+ providers
```

---

## Three demos (run via `python ollama/19_ai_gateway_ollama.py`)

### Demo 1 — Provider abstraction (same code, switchable provider)

```python
response = litellm.completion(
    model="ollama/llama3.2",              # ← change this line, done
    messages=[{"role": "user", "content": prompt}],
    max_tokens=300,
    api_base="http://localhost:11434",
)
```

To swap to GPT-4o: `model="openai/gpt-4o"`. To Gemini: `model="gemini/gemini-1.5-pro"`. Same return shape, same `response.choices[0].message.content`, same `response.usage.prompt_tokens`. **One-line change is the entire migration.**

### Demo 2 — Model bake-off (the latency lever, made empirical)

Same prompt, three local model sizes:

```
model                       in   out    latency
────────────────────────────────────────────────
ollama/llama3.2:3b          36   148    2.94s
ollama/llama3.2             36   149    6.05s
ollama/llama3.2:70b         57   280    8.12s
────────────────────────────────────────────────
                                   Latency ratio: ~2.8×
                                   (no API cost — runs locally)
```

**The 3b variant is ~2.8× faster than the 70b for nearly-identical output on a simple task.** That's the "model selection per role" latency lever. Use the 3b variant for guardrail judges, on-topic classification, format-validation — anywhere quality is good enough but speed matters.

### Demo 3 — Fallback chain (resilience without app code knowing)

```python
response = litellm.completion(
    model="ollama/llama3.2:NONEXISTENT-MODEL",   # primary (deliberately broken)
    fallbacks=[
        "ollama/llama3.2",                       # fallback 1
        "ollama/llama3.2:3b",                    # fallback 2
    ],
    messages=[...],
    api_base="http://localhost:11434",
)
print(response.model)  # → "llama3.2" (the one that actually served the request)
```

LiteLLM catches the error from the primary, transparently retries against the next model in the list, returns the first successful response. **Your app code never sees the failure** — just gets a successful `response` back.

In production: replace the broken primary with a real model that's temporarily unavailable, or add cloud fallbacks (`openai/gpt-4o`) for when local GPU is saturated.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
cd labs
./.venv/bin/python -m pip install litellm   # one-time
python ollama/19_ai_gateway_ollama.py
```

No API key needed for the Ollama demos. For real multi-provider routing, add `OPENAI_API_KEY` / `GEMINI_API_KEY` / etc.

---

## When to use which AI gateway

| Gateway | When to pick |
|---|---|
| **LiteLLM (Python lib in-process)** | Single Python app, prototyping, libraries you're shipping |
| **LiteLLM (self-hosted proxy)** | Multi-app organization, central credentials + audit + rate limits |
| **OpenRouter** | Don't want to manage credentials yourself; pay-as-you-go; willing to add a service to your stack |
| **Vercel AI Gateway** | Already on Vercel; want zero-ops fallbacks + analytics; OK with Vercel-specific |
| **Portkey** | Enterprise tier with org-level governance, GDPR controls |
| **No gateway** | Single-provider, low-volume, never going to swap. Don't add complexity you won't use. |

---

## Production deployment patterns

### Pattern 1 — In-process library

```python
import litellm
response = litellm.completion(model="ollama/llama3.2", messages=[...], api_base="http://localhost:11434")
```

Simplest. Use in scripts and small services. Auth via env vars per provider (none needed for local Ollama).

### Pattern 2 — Self-hosted proxy

```bash
litellm --port 4000 --config /path/to/litellm_config.yaml
```

Then point all apps at `http://localhost:4000/v1` using the OpenAI SDK conventions. **One credential vault, one audit log, one rate-limit policy.** This is the production deployment most teams want once they have 3+ services calling LLMs.

### Pattern 3 — Cost-by-feature tags

```python
response = litellm.completion(
    model="ollama/llama3.2",
    messages=[...],
    metadata={"feature": "guardrail_judge", "user_tier": "free"},
    api_base="http://localhost:11434",
)
# Aggregated daily: inference time by feature, by user_tier, by model
```

The metadata is logged with each call. Query it later to see exactly which features consume the most local GPU time. Useful unit-economics analysis even without dollar costs.

---

## What an AI gateway does NOT replace

- **Authentication** — your app's user-auth still happens at the edge
- **Application-layer rate limiting** — gateway protects you from upstream; you protect your users
- **Token budget enforcement** — gateway tracks; you decide when to cut off a user
- **The system prompt + tools** — those are still yours to design
- **Quality / faithfulness eval** — gateway doesn't know if the model's answer was correct

The gateway is **infrastructure**, not architecture.

---

## Production patterns this unlocks

| Pattern | Example |
|---|---|
| Multi-provider failover | Ollama → Groq → OpenAI fallback chain; handles local GPU downtime |
| Latency-tier routing | Low-priority tasks → smallest local model; high-priority → largest local model |
| A/B testing models | Route 10% of traffic to new model; compare quality metrics |
| Local/cloud hybrid | Sensitive data → local Ollama; non-sensitive → cloud for better quality |
| Inference time reporting | Tag each call; aggregate; spot expensive features early |
| Dev/prod separation | Local dev → `llama3.2:3b` (fast); prod → `llama3.2` or cloud; one env var |

---

## Try this

1. **Add a fourth model** to the bake-off — if you have additional Ollama models pulled, compare their latency on the same prompt.
2. **Configure max retries** — `litellm.completion(..., num_retries=3)`. Force a timeout (use `timeout=0.001`) and watch the retry behavior.
3. **Add metadata tags** — pass `metadata={"feature": "demo"}` to a call; in production you'd query `litellm.success_callback` logs for inference-time-by-feature.
4. **Run the LiteLLM proxy** — `litellm --port 4000 --model ollama/llama3.2` then call it via the OpenAI SDK at `base_url="http://localhost:4000"`. Demonstrates the self-hosted proxy pattern.
5. **Wrap `11_production_chatbot_ollama.py` with LiteLLM** — replace `ChatOllama` with `from langchain_litellm import ChatLiteLLM`. Same chain, gateway-routed.

---

## Mental model in one line

> **An AI gateway separates *which provider* from *what the app does*. Your app code calls one function; the gateway routes, fails over, retries, and tracks usage across many providers. It's HTTP-layer infrastructure for the LLM ecosystem — like a load balancer is for backend servers.**

---

## FAQ

**Q: I'm only using Ollama. Do I still need a gateway?**

A: For one app calling one local provider — no, don't add complexity you won't use. The gateway pays off when you have (a) multiple apps/services calling LLMs, (b) plans to add cloud providers for fallback capacity, (c) need centralized credential/audit/rate-limit policies, or (d) want inference-time-by-feature analytics.

**Q: Does LiteLLM add latency?**

A: In-process library: negligible (single Python function call + a dict construction). Self-hosted proxy: adds one network hop, typically <10ms inside a data center. For latency-critical paths, profile before adding any abstraction.

**Q: How does LiteLLM authenticate to multiple providers?**

A: Env vars per provider. No env var needed for local Ollama (`api_base="http://localhost:11434"` is sufficient). `OPENAI_API_KEY` → OpenAI. `GEMINI_API_KEY` → Gemini. The library reads the right one based on the `model` argument's prefix.

**Q: What's the difference between LiteLLM and the OpenAI SDK?**

A: LiteLLM is **API-compatible** with the OpenAI SDK — its responses match OpenAI's shape. You can use the OpenAI SDK pointed at LiteLLM's proxy URL and it just works. Most apps using OpenAI's SDK can drop in LiteLLM without code changes.

**Q: Does the gateway handle streaming?**

A: Yes — `litellm.completion(model=..., stream=True)` yields chunks like the OpenAI SDK. The chunk format is normalized across providers.

**Q: Does it support tool use / function calling?**

A: Yes — pass `tools=[...]` (OpenAI-style schemas). LiteLLM translates to each provider's tool format.

**Q: Can I use LangChain *and* LiteLLM?**

A: Yes. `langchain-litellm` provides `ChatLiteLLM` which is a drop-in replacement for `ChatOllama` / `ChatOpenAI`. You get LangChain's composition primitives AND LiteLLM's provider routing.

**Q: Is the inference tracking accurate?**

A: LiteLLM maintains a pricing table per model (input cost, output cost). For Ollama local models, there is no dollar cost — LiteLLM still tracks token counts which you can use for latency correlation.

**Q: When does the gateway actively hurt me?**

A: When you have a single-provider app and you add the gateway preemptively. The complexity tax (config files, learning the gateway's quirks, debugging through an extra layer) is real. **Add a gateway when you have a real reason** (multi-provider, multi-app, multi-tier, multi-region). Not before.

---

## Related

- **Previous:** [18 — Native SDK](../18-anthropic-sdk.md)
- **Next:** Session 9 — Files & Document AI (Track D)
- **Builds on:** [01 — Model wrapper](01-model-wrapper.md) (LangChain's provider-portability for free) and [11 — Production capstone](11-production-capstone.md) (where centralized provider control gets real value)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 8 of 40 (Track C complete)
