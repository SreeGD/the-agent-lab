# 27 — Streaming (Session 16)

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

**Why this lesson now:** Session 15 cut your bill. Session 16 cuts your perceived latency. Cost and latency are the two production axes; both move independently of quality (Session 14 keeps the floor honest).

---

## File involved

| File | Role |
|---|---|
| [`27_streaming.py`](../27_streaming.py) | Four runnable demos: raw SDK streaming with TTFT measurement, LangChain `.stream()` over LCEL, LangGraph stream modes (values/updates/messages), and the tool-use streaming gotcha. |

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

### Demo 1 — Raw SDK streaming, TTFT measurement

```python
with raw_client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=200,
    messages=[{"role": "user", "content": "..."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)   # render as it arrives
```

The `stream.text_stream` iterator yields string deltas as they come off the wire. `flush=True` matters — otherwise stdout buffers and you don't actually see the streaming effect.

**Real numbers from the live run:**
```
Non-streamed:  TTFT: 3629 ms   total: 3629 ms
Streamed:      TTFT:  847 ms   total: 3224 ms
```

Same prompt, same model, same answer. **Time to first byte dropped 77%.** Total wall time is comparable (slightly faster streamed because the SDK can start downloading before generation finishes). The win is entirely in perception.

**Important measurement note:** TTFT for streamed calls measures *time to first delta event*. For non-streamed calls, the entire response IS the "first byte" — there's no streaming, so TTFT = total. Both are valid measurements; the comparison is the point.

### Demo 2 — LangChain `.stream()` over LCEL

```python
chain = prompt | model | StrOutputParser()
for chunk in chain.stream({"topic": "..."}):
    print(chunk, end="", flush=True)
```

LangChain wraps the SDK stream behind LCEL's familiar pipe syntax. Each yielded chunk is a string fragment.

**The parser matters:**
- `StrOutputParser` — passes string chunks through unchanged. Streams cleanly.
- `JsonOutputParser` — **cannot** yield partial chunks (partial JSON is invalid). It buffers until the full object is parseable. So with JsonOutputParser, you don't *really* get streaming; you get one big chunk at the end.
- Custom output parsers — depends on whether they can handle partial input. The contract is: each `chunk` you yield must be a valid value of the parser's output type.

For *true* streaming over structured output, see the streaming-aware Pydantic patterns in newer LangChain releases — they emit *partial* Pydantic objects with optional fields. But the default JSON parser is buffered.

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

This is the one production trap that's not obvious from the API:

When an agent decides to call a tool, the LLM stream produces a `tool_use` block and **stops**. The tool then runs (locally — that's a non-LLM operation). Then the agent issues a **second LLM call**, which streams the final answer.

**Real timeline from the run:**
```
[t= 1721ms] AIMessage      → tool_call: get_weather({'city': 'Hyderabad'})
[t= 1723ms] ToolMessage    ← tool result: 'It is 18°C and partly cloudy in Hyderabad.'
[t= 3768ms] AIMessage        answer: 'The current weather in Hyderabad is 18°C and partly cloudy...'
```

Notice the gap: tool result at 1723 ms, final answer at 3768 ms. **That 2-second pause is a second LLM round-trip** — the LLM has to re-read the tool result and generate the actual user-facing answer.

**Production UX pattern:**
1. Stream the first pass to the chat → render "I'll check the weather…"
2. Detect the `tool_call` event → render a status indicator: "🌡️ Checking weather in Hyderabad…"
3. Tool runs locally (usually fast)
4. Stream the second pass to the chat → tokens of the final answer appear after the indicator

Without this UX, the user sees "I'll check the weather…" and then nothing for 2 seconds. That's the same frozen-screen feeling streaming was supposed to fix.

---

## Run it

```
cd labs
./.venv/bin/python 27_streaming.py
```

Takes ~20 seconds, costs ~$0.02. The most important thing to watch is Demo 1 — the visible difference between blocking and streaming when both are running back-to-back.

---

## Real output highlights

**Demo 1 latency table:**

| | TTFT | Total | Perception |
|---|---|---|---|
| Non-streamed | 3629 ms | 3629 ms | "is it broken?" |
| Streamed | 847 ms | 3224 ms | "instant, smooth" |

**Demo 3 mode contrast** (same input, three views):
- `values` mode emitted 3 events (one per state mutation)
- `updates` mode emitted 2 events (one per node, showing only the diff)
- `messages` mode emitted dozens of token-delta events (one per LLM-output token)

**Demo 4 timing breakdown:**
- Pass 1 (decide tool call): 0 → 1721 ms
- Tool execution: 1721 → 1723 ms (effectively instant for a stub)
- Pass 2 (compose final answer): 1723 → 3768 ms

That 2-second second-pass is where production agent UIs must render a status indicator.

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

### Streaming with structured output

If your endpoint returns JSON (not raw text), the streaming contract is different:
- Buffer tokens server-side until JSON is parseable
- Emit *partial Pydantic objects* as fields fill in (advanced)
- OR: switch to a different shape — stream `events` (typed envelope objects) instead of a single big object

For agent UIs the typed-events approach is much cleaner:
```python
yield {"type": "thinking", "text": "Let me check..."}
yield {"type": "tool_call", "tool": "get_weather", "args": {"city": "Hyderabad"}}
yield {"type": "tool_result", "result": "..."}
yield {"type": "token", "delta": "The"}
yield {"type": "token", "delta": " weather"}
# ...
yield {"type": "done"}
```

Browser decodes each event by type and renders accordingly. This is what Claude.ai, ChatGPT, and most production agent UIs actually do.

### Streaming + the cost levers (Session 15)

These compose:
- **Caching**: streaming and cache_control are independent — the cache_read tokens still come back in the streamed usage. Both at once is fine.
- **Model selection**: Haiku streams FASTER than Sonnet (smaller model = lower per-token latency). For perceived-latency-critical paths (welcome message, first answer), Haiku is often the right call.
- **Compression**: shorter system prompts → faster TTFT (less to process before generation starts). A 50% compressed prompt typically gives ~30% faster TTFT.
- **Batches API**: incompatible with streaming. Batches is for offline workloads where streaming doesn't help anyway.

### Latency budget for chat UI

A typical "feels instant" chat UI budget:
- **TTFT < 800 ms** — anything more and the user notices the pause
- **Inter-token interval < 100 ms** — tokens should arrive at faster than reading speed
- **Total response < 6 s** — beyond this even with streaming, users lose patience

Sonnet typically meets the first two. The total-time budget is where retrieval / tool calls / multi-step agents start to matter.

### Where streaming breaks down

- **Re-ranking, summarization** — can't stream because the LLM needs to read everything before producing output. Mitigate with a "thinking…" indicator.
- **JsonOutputParser endpoints** — already covered. Switch to events architecture.
- **Long-context reads** — the *prefill* phase (reading the long context) doesn't stream. Mitigate with caching + showing a "reading documents…" indicator during prefill.
- **Tool-heavy agents** — every tool call pauses the stream. Render each tool call as a discrete UI event.

### Monitoring streaming

Log per-call:
- `ttft_ms` (when first delta arrived)
- `total_ms` (when stream ended)
- `tokens_per_second` (output_tokens / total_ms)
- `delta_count` (number of stream events)

Alert when:
- p95 TTFT > 1500 ms (something's wrong with the prefill)
- tokens/sec < 30 (model is overloaded or networked badly)

---

## Try this

1. **Compare Sonnet vs Haiku TTFT.** Swap `MODEL` to `claude-haiku-4-5-20251001` in Demo 1. Re-run. TTFT typically drops ~30%. For greeting messages or first-impression endpoints, this matters.

2. **Add `cache_control` to Demo 1's system prompt.** Pad the prompt to >1024 tokens. Run once (cache write), then immediately again (cache read). Does TTFT drop further on the second run?

3. **Build an SSE endpoint.** Wrap Demo 2's chain in a FastAPI `StreamingResponse`. Hit it from `curl -N http://localhost:8000/chat` and watch tokens arrive in your terminal.

4. **Capture `updates` mode for a real agent.** Use `create_react_agent` from Demo 4, stream with `mode="updates"`, and print each update as JSON. This is what your activity-log sidebar would render.

5. **Measure tool-call overhead.** Add a deliberately slow tool (`time.sleep(2)` inside the tool function). Watch the total time. The pause between passes grows — and your UI MUST render a status indicator during that window.

---

## Mental model

> **Streaming is a UX feature, not a performance feature.** Total compute doesn't change. What changes is the user's experience of waiting.

The mental separation is critical: if you want to make answers *actually* faster, use cost optimization tricks (Session 15) and smaller models. If you want to make answers *feel* faster, stream.

The two work together — Haiku + streaming + caching gives you sub-300ms TTFT on a chatbot, which is the latency ceiling under which users stop perceiving wait time at all.

---

## FAQ

**Q: Why does the streamed version still have a noticeable TTFT (~800 ms)?**
Because the model still has to do *prefill* — read your prompt, build the KV cache, start generating. The output streams; the input doesn't. With prompt caching (Session 4), the prefill cost on cache hits drops to ~10% — TTFT drops correspondingly.

**Q: Is streaming always cheaper / faster overall?**
Marginally faster (you save the TCP round-trip wait between request end and full response). Not cheaper (same tokens billed). The whole point is *perceived* latency, not real latency.

**Q: Can I cancel a stream mid-flight?**
Yes — close the stream context. The SDK sends a cancel signal; you stop being billed for further tokens. Useful for "stop" buttons in chat UIs.

**Q: Does streaming work with tool use?**
Yes, but the stream stops at each tool boundary (Demo 4). You handle this by streaming each "pass" separately and rendering tool-call events in between.

**Q: Does streaming work with structured output?**
Tricky. Partial JSON is invalid, so the JSON parser must buffer. Modern LangChain has `with_structured_output(..., include_raw=True)` that lets you stream the *raw* text while parsing in parallel — partial Pydantic-with-Optional-fields can emit intermediate values.

**Q: What's the relationship between `messages` mode (LangGraph) and `text_stream` (SDK)?**
`text_stream` is the raw SDK iterator. `messages` mode is LangGraph wrapping that across all LLM calls in a graph — same per-token deltas, but tagged with which node produced them. For single-LLM-call apps the two are essentially equivalent; for multi-node graphs `messages` is the right abstraction.

**Q: SSE vs WebSocket?**
SSE for one-way server → browser (chat token feed). WebSocket if you need bidirectional (interrupt the LLM, send mid-stream user input, etc.). 95% of streaming chat UIs use SSE. The remaining 5% are doing something special.

**Q: How do I render `tool_call` events in the chat UI?**
Distinct visual treatment. The user shouldn't have to read the JSON. Render as a colored chip: 🌡️ *"Checking weather in Hyderabad…"*, with the chip turning green when the tool returns. This is what makes agent UIs feel polished vs. raw.

**Q: What about streaming TTS (audio out)?**
Same idea, different medium. Modern voice agents stream audio chunks as they're synthesized — first audio plays before the full response is generated. The TTFT-equivalent for voice is *time to first audio frame*; ~400 ms is the sweet spot.

**Q: Does the `create_react_agent` deprecation warning matter?**
Not for this lab. LangGraph V1.0 moved `create_react_agent` to `langchain.agents.create_agent`. The current import still works; the new import is `from langchain.agents import create_agent`. We'll switch when LangGraph V2.0 ships.

---

## Related

- **Previous:** [26 — Cost Optimization](26-cost-optimization.md) — total latency lever (real time saved)
- **Next:** Session 17 — Deploy + Observability (production wiring, tracing, alerts — Track F finale)
- **Builds on:** [18 — Anthropic SDK](18-anthropic-sdk.md) (Demo 1 uses the raw stream API), [21 — Custom LangGraph](21-custom-langgraph.md) (Demo 3 graph patterns), [03 — Agent tool loop](03-agent-tool-loop.md) (Demo 4 is that loop, streamed)
- **Track F status:** ▶ 3/4 complete. Eval → Cost → Streaming. Next: Deploy + Observability.
