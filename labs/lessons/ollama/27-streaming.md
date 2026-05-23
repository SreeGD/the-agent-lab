# 27 — Streaming (Session 16)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/27_streaming_ollama.py`.

> **Same compute. Different UX.** A 4-second answer feels broken if nothing renders for 4 seconds. The same answer feels fast if the first words land at 400 ms. Streaming is how AI apps stop feeling like they're hanging — and how production chat UIs surface "thinking…", tool calls, and live token feeds.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-15 (foundation + RAG + eval + cost)                 Track F: PRODUCTION
                                                             ✓ Session 14: Evaluation
                                                             ✓ Session 15: Cost Optimization
                                                             ▶ Session 16: STREAMING  ◄ HERE
                                                             ○ Session 17: Deploy + Observability
                                                           Track G: ○ Architect Skills
```

**Why this lesson now:** Session 15 cut your inference time. Session 16 cuts your perceived latency. Both move independently of quality (Session 14 keeps the floor honest).

---

## File involved

| File | Role |
|---|---|
| [`27_streaming_ollama.py`](../ollama/27_streaming_ollama.py) | Four runnable demos: raw Ollama streaming with TTFT measurement, LangChain `.stream()` over LCEL, LangGraph stream modes (values/updates/messages), and the tool-use streaming gotcha. |

---

## What problem it solves

Imagine your RAG pipeline takes 4 seconds end-to-end. The LLM call itself is ~3.5s; retrieval is ~0.5s.

**Without streaming:**
```
[user clicks send]
[blank screen, blinking cursor for 4 seconds]
[full answer appears at once]
```
Users hit refresh at ~2 seconds because they think it's broken.

**With streaming:**
```
[user clicks send]
[400 ms later: first words appear]
[next 3 seconds: rest of the answer unrolls at reading speed]
[total: 4 seconds, but it FEELS like it started immediately]
```
Same total compute. Completely different product.

Beyond raw latency, streaming is the only way to surface what an agent is *doing*:
- Calling a tool → render *"searching weather…"*
- Planning → render *"thinking through your request…"*
- Retrieving → render *"checking knowledge base…"*

Production agent UIs use streaming for both halves: token-by-token text AND structured "status" events.

---

## The analogy

**A bartender pouring you a beer.**

**Non-streamed:** the bartender disappears for 4 minutes, comes back with a full pint glass. You think they forgot about you. You ask if they got your order. They glare.

**Streamed:** the bartender turns the tap on at the bar in front of you. The glass starts filling at 5 seconds. It takes 4 minutes to fill (slow tap), but you can see it filling and you know your order is being made. You wait happily.

Same physical pour. Different psychological experience.

---

## Visual

```
                       NON-STREAMED                    STREAMED
                       ────────────                    ────────

   t=0 ms     [user submits]              [user submits]

   t=400 ms   [empty UI]                  [first tokens render]    ← TTFT win
              [user wonders if broken]    [user starts reading]

   t=2000 ms  [still empty]               [halfway through reading]
              [user clicks refresh?]      [tokens still arriving]

   t=4000 ms  [full answer appears        [last tokens land just as
              all at once — too late]      user finishes reading]


             Total wall time: 4 s          Total wall time: 4 s
             Perceived: ~~~~ FROZEN        Perceived: ~~~~ FAST
```

---

## Concept walk-through

### Demo 1 — Ollama streaming with TTFT measurement

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

import time
start = time.perf_counter()
first_token_at = None

for chunk in model.stream("Explain what LangChain LCEL is in 3 sentences."):
    if first_token_at is None:
        first_token_at = time.perf_counter()
        ttft_ms = (first_token_at - start) * 1000
        print(f"TTFT: {ttft_ms:.0f}ms")
    print(chunk.content, end="", flush=True)
```

The `flush=True` matters — otherwise stdout buffers and you don't actually see the streaming effect.

Typical numbers with Ollama locally:
- TTFT: 200-600 ms (varies by hardware, model load)
- Total: 2-5 s (depends on output length)

The TTFT win is the whole point — users perceive the response starting almost immediately.

### Demo 2 — LangChain `.stream()` over LCEL

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

chain = ChatPromptTemplate.from_template("Write about {topic}") | model | StrOutputParser()
for chunk in chain.stream({"topic": "LangChain streaming"}):
    print(chunk, end="", flush=True)
```

LangChain wraps the Ollama stream behind LCEL's familiar pipe syntax. Each yielded chunk is a string fragment.

**The parser matters:**
- `StrOutputParser` — passes string chunks through unchanged. Streams cleanly.
- `JsonOutputParser` — **cannot** yield partial chunks (partial JSON is invalid). It buffers until the full object is parseable. So with JsonOutputParser, you don't *really* get streaming; you get one big chunk at the end.

### Demo 3 — LangGraph stream modes

LangGraph has three streaming modes for three different production needs:

**`stream_mode="values"`** — full state snapshot after each node.
```
state: {'question': True}
state: {'question': True, 'plan': True}
state: {'question': True, 'plan': True, 'answer': True}
```
Use for: debugging, persistence checkpoints, anything that needs the complete state.

**`stream_mode="updates"`** — only what each node changed.
```
[plan]   changed ['plan']    preview: '**Plan:** Explain the concept...'
[answer] changed ['answer']  preview: '## Structured Output in...'
```
Use for: sidebar status indicators ("planning…", "answering…"), activity logs, audit trails.

**`stream_mode="messages"`** — per-token deltas from LLM calls *inside* the graph.
```
[plan] **Plan:** Explain the concept of structured output in LangChain...
[answer] **Structured output** is a feature that lets you...
```
Use for: the actual chat UI token feed. This is what the user *sees*.

**Production pattern: stream all three to different consumers.**
- `messages` → WebSocket/SSE channel to the browser chat box (token feed)
- `updates` → WebSocket channel to the activity log ("planning…", "calling tool…")
- `values` → server-side log for debugging and replay

### Demo 4 — The tool-use streaming gotcha

When an agent decides to call a tool, the LLM stream produces a tool call and **stops**. The tool then runs (locally — that's a non-LLM operation). Then the agent issues a **second LLM call**, which streams the final answer.

**Timeline:**
```
[t= 1000ms] AIMessage → tool_call: get_weather({'city': 'Hyderabad'})
[t= 1002ms] ToolMessage ← tool result: 'It is 18°C and partly cloudy in Hyderabad.'
[t= 2800ms] AIMessage  answer: 'The current weather in Hyderabad is 18°C and partly cloudy...'
```

Notice the gap: tool result at 1002 ms, final answer at 2800 ms. **That ~1.8-second pause is a second LLM round-trip** — the LLM has to re-read the tool result and generate the actual user-facing answer.

**Production UX pattern:**
1. Stream the first pass to the chat → render "I'll check the weather…"
2. Detect the `tool_call` event → render a status indicator: "Checking weather in Hyderabad…"
3. Tool runs locally (usually fast)
4. Stream the second pass to the chat → tokens of the final answer appear after the indicator

Without this UX, the user sees "I'll check the weather…" and then nothing for ~2 seconds. That's the same frozen-screen feeling streaming was supposed to fix.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/27_streaming_ollama.py
```

Takes ~20 seconds. No API cost — Ollama runs locally. The most important thing to watch is Demo 1 — the visible difference between blocking and streaming when both are running back-to-back.

---

## Production patterns

### Streaming over HTTP — Server-Sent Events (SSE)

```python
# FastAPI server
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat")
async def chat(req: ChatRequest):
    async def event_stream():
        async for chunk in chain.astream({"question": req.question}):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

```javascript
// Browser
const source = new EventSource("/chat");
source.onmessage = (e) => {
    if (e.data === "[DONE]") return source.close();
    const { delta } = JSON.parse(e.data);
    chatDiv.innerText += delta;
};
```

That's ~20 lines for end-to-end streaming. WebSocket variant is similar; pick SSE for one-way streaming (server → browser), WebSocket if you need to interrupt or send mid-stream signals.

### Streaming + the optimization levers (Session 15)

These compose:
- **Model selection**: `llama3.2:3b` streams FASTER than `llama3.2` full (smaller model = lower per-token latency). For perceived-latency-critical paths (welcome message, first answer), `llama3.2:3b` is often the right call.
- **Compression**: shorter system prompts → faster TTFT (less to process before generation starts). A 50% compressed prompt typically gives ~30% faster TTFT.

### Latency budget for chat UI

A typical "feels instant" chat UI budget:
- **TTFT < 800 ms** — anything more and the user notices the pause
- **Inter-token interval < 100 ms** — tokens should arrive at faster than reading speed
- **Total response < 6 s** — beyond this even with streaming, users lose patience

With Ollama locally these numbers depend heavily on hardware. On a modern laptop with Apple Silicon or a decent GPU, these targets are achievable.

### Where streaming breaks down

- **Re-ranking, summarization** — can't stream because the LLM needs to read everything before producing output. Mitigate with a "thinking…" indicator.
- **JsonOutputParser endpoints** — already covered. Switch to events architecture.
- **Long-context reads** — the *prefill* phase (reading the long context) doesn't stream. Mitigate with showing a "reading documents…" indicator during prefill.
- **Tool-heavy agents** — every tool call pauses the stream. Render each tool call as a discrete UI event.

---

## Try this

1. **Compare llama3.2 vs llama3.2:3b TTFT.** Swap `MODEL` to `llama3.2:3b` in Demo 1. Re-run. TTFT typically drops ~30-50% on a small model. For greeting messages or first-impression endpoints, this matters.

2. **Add compression to Demo 1's system prompt.** Apply the Lever 2 techniques from Session 15. Run once with the verbose prompt, then with the compressed prompt. Does TTFT drop?

3. **Build an SSE endpoint.** Wrap Demo 2's chain in a FastAPI `StreamingResponse`. Hit it from `curl -N http://localhost:8000/chat` and watch tokens arrive in your terminal.

4. **Capture `updates` mode for a real agent.** Use `create_react_agent` from Demo 4, stream with `mode="updates"`, and print each update as JSON. This is what your activity-log sidebar would render.

5. **Measure tool-call overhead.** Add a deliberately slow tool (`time.sleep(2)` inside the tool function). Watch the total time. The pause between passes grows — and your UI MUST render a status indicator during that window.

---

## Mental model

> **Streaming is a UX feature, not a performance feature.** Total compute doesn't change. What changes is the user's experience of waiting.

The mental separation is critical: if you want to make answers *actually* faster, use optimization tricks (Session 15) and smaller models. If you want to make answers *feel* faster, stream.

The two work together — `llama3.2:3b` + streaming gives you sub-400ms TTFT on a chatbot, which is the latency ceiling under which users stop perceiving wait time at all.

---

## FAQ

**Q: Why does the streamed version still have a noticeable TTFT (~400-600 ms)?**
Because the model still has to do *prefill* — read your prompt, build the KV cache, start generating. The output streams; the input doesn't. Prompt compression (Session 15) reduces prefill time.

**Q: Is streaming always faster overall?**
Marginally faster (you save the wait between request end and full response). Not faster per se (same tokens generated). The whole point is *perceived* latency, not real latency.

**Q: Can I cancel a stream mid-flight?**
Yes — close the stream context. The generator stops; no further inference runs.

**Q: Does streaming work with tool use?**
Yes, but the stream stops at each tool boundary (Demo 4). You handle this by streaming each "pass" separately and rendering tool-call events in between.

**Q: Does streaming work with structured output?**
Tricky. Partial JSON is invalid, so the JSON parser must buffer. Modern LangChain has `with_structured_output(..., include_raw=True)` that lets you stream the *raw* text while parsing in parallel.

**Q: What's the relationship between `messages` mode (LangGraph) and `.stream()` (LangChain)?**
`.stream()` is the raw per-token iterator on a single chain. `messages` mode is LangGraph wrapping that across all LLM calls in a graph — same per-token deltas, but tagged with which node produced them.

**Q: SSE vs WebSocket?**
SSE for one-way server → browser (chat token feed). WebSocket if you need bidirectional (interrupt the LLM, send mid-stream user input, etc.). 95% of streaming chat UIs use SSE.

---

## Related

- **Previous:** [26 — Cost Optimization](26-cost-optimization.md) — inference time lever (real time saved)
- **Next:** Session 17 — Deploy + Observability (production wiring, tracing, alerts — Track F finale)
- **Builds on:** [21 — Custom LangGraph](21-custom-langgraph.md) (Demo 3 graph patterns), [03 — Agent tool loop](03-agent-tool-loop.md) (Demo 4 is that loop, streamed)
- **Track F status:** ▶ 3/4 complete. Eval → Cost → Streaming. Next: Deploy + Observability.
