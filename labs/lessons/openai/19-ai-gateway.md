# 19 — AI Gateway (Session 8)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_openai.ChatOpenAI`, model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/19_ai_gateway_openai.py`.

> **One Python API → 100+ LLM providers.** LiteLLM (and its hosted siblings OpenRouter, Vercel AI Gateway) put a unified control plane between your app and the multiplying LLM ecosystem. Same call shape regardless of provider. Fallbacks, retries, cost tracking, and auth all live in one layer — so your app code stays clean even when your model mix doesn't.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: ✓ all 3 done
                                                           Track B: ✓ all 3 done
                                                           Track C: Alt Architectures
                                                             ✓ Session 7: Anthropic SDK
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
| [`19_ai_gateway_openai.py`](../../openai/19_ai_gateway_openai.py) | Three LiteLLM demos: provider abstraction, model bake-off, fallback chain |

---

## What problem it solves

You ship an AI feature on GPT-4o. Six months later, OpenAI is briefly down. Or your CFO says gpt-4o-mini is cheaper than gpt-4o for guardrail judges. Or your enterprise customer wants Claude specifically. Three real scenarios; three reasons your code shouldn't have `from langchain_openai import ChatOpenAI` hardwired into every endpoint.

**AI Gateway centralizes the provider decision** — one config flip swaps GPT-4o for Claude, or routes 10% of traffic to a new model, or fails over GPT-4o → Claude → Gemini on outages. Your application code never knew the provider changed.

Without a gateway, every team that wants to add a provider rewrites every call site.

---

## The analogy

**A power strip with surge protection.**

Without a gateway: every appliance plugs directly into a different wall outlet. Different voltages, different plugs. Want to swap your toaster's electricity supplier? Rewire the kitchen.

With a gateway: appliances plug into one power strip. The strip handles voltage conversion (provider auth), surge protection (rate limits + retries), and you can switch the upstream supplier without touching any appliance.

LiteLLM is the power strip. Claude, GPT, Gemini, Mistral, Bedrock are the suppliers. Your app is the appliance.

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
   │   │    model="openai/gpt-4o",        │    │
   │   │    messages=[...],               │    │
   │   │    fallbacks=[...],              │    │
   │   │  )                               │    │
   │   └──────────────────────────────────┘    │
   │                                            │
   │   - Per-provider auth (env vars)           │
   │   - Retry on transient errors              │
   │   - Fallback chain on hard failures        │
   │   - Cost tracking (per call + aggregate)   │
   │   - Rate limit enforcement                 │
   │   - Optional self-hosted proxy             │
   └────┬───────┬───────┬───────┬───────────────┘
        │       │       │       │
        ▼       ▼       ▼       ▼
     OpenAI  Anthropic Gemini  Bedrock  ... 100+ providers
```

---

## Three demos (run via `python openai/19_ai_gateway_openai.py`)

### Demo 1 — Provider abstraction (same code, switchable provider)

```python
response = litellm.completion(
    model="openai/gpt-4o",                   # ← change this line, done
    messages=[{"role": "user", "content": prompt}],
    max_tokens=300,
)
```

To swap to Claude: `model="anthropic/claude-sonnet-4-6"`. To Gemini: `model="gemini/gemini-1.5-pro"`. Same return shape, same `response.choices[0].message.content`, same `response.usage.prompt_tokens`. **One-line change is the entire migration.**

### Demo 2 — Model bake-off (the cost lever, made empirical)

Same prompt, three OpenAI tiers:

```
model                    in   out    latency      cost
──────────────────────────────────────────────────────
gpt-4o-mini             36   148    2.94s    $0.000776
gpt-4o                  36   149    6.05s    $0.002343
gpt-4o                  57   280    8.12s    $0.007285
──────────────────────────────────────────────────────
```

Use gpt-4o-mini for guardrail judges, on-topic classification, format-validation — anywhere quality is good enough but volume is high.

### Demo 3 — Fallback chain (resilience without app code knowing)

```python
response = litellm.completion(
    model="openai/gpt-4o-NONEXISTENT-MODEL",   # primary (deliberately broken)
    fallbacks=[
        "openai/gpt-4o",                       # fallback 1
        "openai/gpt-4o-mini",                  # fallback 2
    ],
    messages=[...],
)
print(response.model)  # → "gpt-4o" (the one that actually served the request)
```

LiteLLM catches the 404 from the primary, transparently retries against the next model in the list, returns the first successful response. **Your app code never sees the failure** — just gets a successful `response` back.

In production: replace the bogus primary with a real model that occasionally rate-limits. Fallback chain absorbs the brief blip. Real high-availability without a circuit breaker library.

---

## Run it

```bash
cd labs
./.venv/bin/python -m pip install litellm   # one-time
python openai/19_ai_gateway_openai.py
```

Requires only `OPENAI_API_KEY` for the demo. For real multi-provider routing, add `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / etc.

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
response = litellm.completion(model="...", messages=[...])
```

Simplest. Use in scripts and small services. Auth via env vars per provider.

### Pattern 2 — Self-hosted proxy

```bash
litellm --port 4000 --config /path/to/litellm_config.yaml
```

Then point all apps at `http://localhost:4000/v1` using the OpenAI SDK conventions. **One credential vault, one audit log, one rate-limit policy.**

### Pattern 3 — Cost-by-feature tags

```python
response = litellm.completion(
    model="...",
    messages=[...],
    metadata={"feature": "guardrail_judge", "user_tier": "free"},
)
# Aggregated daily: cost by feature, by user_tier, by model
```

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
| Multi-provider failover | GPT-4o → Claude → Gemini fallback chain; 99.9%+ availability |
| Cost-tier routing | Anonymous users → gpt-4o-mini; paid users → gpt-4o; enterprise → gpt-4o |
| A/B testing models | Route 10% of traffic to new model; compare quality metrics |
| Regional routing | EU users → EU-hosted model; US → US-hosted; for compliance |
| Cost-by-feature reporting | Tag each call; aggregate; spot expensive features early |
| Dev/prod separation | Local dev → gpt-4o-mini (cheap); prod → gpt-4o; one env var |

---

## Try this

1. **Add a fourth model** to the bake-off — `claude-sonnet-4-6` if you have an Anthropic key; compare cross-provider quality and cost.
2. **Configure max retries** — `litellm.completion(..., num_retries=3)`. Force a timeout and watch the retry behavior.
3. **Add metadata tags** — pass `metadata={"feature": "demo"}` to a call; in production you'd query `litellm.success_callback` logs for cost-by-feature.
4. **Run the LiteLLM proxy** — `litellm --port 4000 --model openai/gpt-4o` then call it via the OpenAI SDK at `base_url="http://localhost:4000"`. Demonstrates the self-hosted proxy pattern.
5. **Wrap `11_production_chatbot_openai.py` with LiteLLM** — replace `ChatOpenAI` with `from langchain_litellm import ChatLiteLLM`. Same chain, gateway-routed.

---

## Mental model in one line

> **An AI gateway separates *which provider* from *what the app does*. Your app code calls one function; the gateway routes, fails over, retries, and tracks cost across many providers. It's HTTP-layer infrastructure for the LLM ecosystem — like a load balancer is for backend servers.**

---

## FAQ

**Q: I'm only using OpenAI. Do I still need a gateway?**

A: For one app calling one provider — no, don't add complexity you won't use. The gateway pays off when you have (a) multiple apps/services calling LLMs, (b) plans to add a second provider for failover, (c) need centralized credential/audit/rate-limit policies, or (d) want cost-by-feature analytics.

**Q: Does LiteLLM add latency?**

A: In-process library: negligible (single Python function call + a dict construction). Self-hosted proxy: adds one network hop, typically <10ms inside a data center.

**Q: How does LiteLLM authenticate to multiple providers?**

A: Env vars per provider. `OPENAI_API_KEY` → OpenAI. `ANTHROPIC_API_KEY` → Anthropic. `GEMINI_API_KEY` → Gemini. The library reads the right one based on the `model` argument's prefix.

**Q: Does the gateway handle streaming?**

A: Yes — `litellm.completion(model=..., stream=True)` yields chunks like the OpenAI SDK. The chunk format is normalized across providers.

**Q: Does it support tool use / function calling?**

A: Yes — pass `tools=[...]` (OpenAI-style schemas). LiteLLM translates to each provider's tool format.

**Q: Can I use LangChain *and* LiteLLM?**

A: Yes. `langchain-litellm` provides `ChatLiteLLM` which is a drop-in replacement for `ChatOpenAI` / `ChatAnthropic`. You get LangChain's composition primitives AND LiteLLM's provider routing.

---

## Related

- **Previous:** [18 — Anthropic SDK / Agent SDK](18-anthropic-sdk.md)
- **Next:** Session 9 — Files & Document AI (Track D)
- **Builds on:** [01 — Model wrapper](01-model-wrapper.md) (LangChain's provider-portability for free) and [11 — Production capstone](11-production-capstone.md) (where centralized provider control gets real value)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 8 of 40 (Track C complete)
