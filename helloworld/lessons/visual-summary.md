# Visual Summary — the whole course in one place

Use this as a single-page map to navigate, recall, or onboard someone new.

This is a **reference page**, not part of the linear lesson sequence. Land here when you want the overview.

---

## The architecture stack (what builds on what)

```
                ┌──────────────────────────────────────────────┐
                │  production_chatbot.py                       │  ← composes everything
                │  (RAG + memory + caching + guardrails)       │
                └─────────────────┬────────────────────────────┘
                                  │
                ┌─────────────────┼─────────────────────┐
                ▼                 ▼                     ▼
        ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐
        │  Guardrails  │   │     RAG      │   │  Stateful Agent    │
        │  in / out    │   │ retrieve-as- │   │  memory +          │
        │  middleware  │   │ a-tool       │   │  multi-step tools  │
        └──────┬───────┘   └──────┬───────┘   └─────────┬──────────┘
               │                  │                     │
               │           ┌──────┴──────┐              │
               │           ▼             ▼              │
               │     ┌──────────┐ ┌──────────────┐      │
               │     │ Document │ │ Embeddings + │      │
               │     │ loaders, │ │ Vector store │      │
               │     │ splitters│ │ + retriever  │      │
               │     └────┬─────┘ └──────┬───────┘      │
               │          │              │              │
               └──────────┴──────────────┴──────────────┘
                                  │
                                  ▼
        ┌────────────────────────────────────────────────────┐
        │  LCEL chains                                       │
        │   prompt | model | parser    (sequential)          │
        │   {"a": chain_a, "b": chain_b}  (parallel)         │
        │   model.with_structured_output(MyModel) (typed)    │
        │   output parsers, format_instructions              │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────────────┐
        │  Model wrapper                                     │
        │   ChatAnthropic, .invoke() / .stream() / .batch()  │
        │   SystemMessage / HumanMessage / AIMessage         │
        │   usage_metadata, cache_control                    │
        └────────────────────────────────────────────────────┘
```

Each layer up the stack is **just composition** of layers below. No new fundamental abstractions — only patterns of combining the basics.

---

## The 8 LCEL patterns at a glance

```
1.  model.invoke("...")                          [01 model wrapper]
        the lowest-level call

2.  chain = prompt | model | parser              [02 LCEL]
        the sequential pipe (LCEL primitive #1)

3.  {"a": chain_a, "b": chain_b} | next_step     [06 parallel]
        parallel fan-out (LCEL primitive #2)

4.  while not msg.tool_calls:                    [03 agent loop]
       msg = model.invoke(history)
        propose-execute-feedback loop
        (or: create_react_agent does it for you)

5.  model.with_structured_output(MyModel)        [05 structured output]
        typed objects out of unstructured text

6.  create_react_agent(model, tools=[...],       [08 chatbot memory]
                       checkpointer=MemorySaver())
        stateful agent — memory by thread_id

7.  retriever | prompt | model | parser          [09 RAG]
       (retriever ← embed → vector store)        [11 capstone]
        RAG — answer grounded in your documents

8.  input_guards → agent → output_guards         [10 guardrails]
        guardrails — middleware around the LLM   [11 capstone]
```

---

## The complete production architecture

```
                ┌────────────── production_chatbot.py ──────────────────┐
                │                                                       │
  user input    │  INPUT GUARDS  [PII regex | Injection regex | OnTopic]│
       │        │       │ pass                                          │
       └───────►│       ▼                                               │
                │   create_react_agent                                  │
                │      ├── CACHED SystemMessage (long, cache_control)   │   ← caching
                │      ├── checkpointer=MemorySaver()                   │   ← memory
                │      └── tools=[retrieve_docs, ...]                   │   ← RAG-as-tool
                │              │                                        │
                │              ▼ (may loop: model ↔ tool ↔ model)       │
                │            answer                                     │
                │              │                                        │
                │              ▼                                        │
                │  OUTPUT GUARDS [PII output | Faithfulness]            │
                │       │ pass                                          │
                └───────┼───────────────────────────────────────────────┘
                        ▼
                   user sees answer (or polite refusal)
```

---

## The two-phase shape of RAG

```
INDEXING (once, at startup):
   raw source ──► Loader ──► Documents
                              │
                              ▼
                        Splitter ──► chunks (smaller Documents)
                              │
                              ▼
                        Embedder ──► (chunk + vector) stored together
                              │
                              ▼
                          Vector Store
                          (4-field rows: id, text, metadata, vector)

QUERYING (every request):
   question  ──► Embedder  ──►  query vector
                                     │
                                     ▼
                            cosine vs all stored vectors
                                     │
                                     ▼
                             top-k chunks (text + metadata)
                                     │
                                     ▼
                             prompt + chunks → LLM → answer
```

---

## The agent loop, visualized

```
   ┌─► model.invoke(history)
   │        │
   │        ├── tool_calls? ──no──► return answer (loop exits)
   │        │
   │        yes
   │        │
   │        ▼
   │   for each tool_call:
   │       run the function (← YOU run this, not the LLM)
   │       append ToolMessage to history
   │        │
   └────────┘
         continue loop
```

---

## The guardrail wrapper

```
   user input
       │
       ▼
   [cheap regex checks]      ← refuse here = $0 cost
       │ pass
       ▼
   [LLM-judge: on-topic?]    ← 1 small LLM call (Sonnet ~100 in / 1 out)
       │ pass
       ▼
   ┌──────────────────────┐
   │   the actual chain   │  ← the expensive part
   └──────────┬───────────┘
              ▼
   [output PII regex]
       │ pass
       ▼
   [LLM-judge: faithful?]    ← only if retrieval happened
       │ pass
       ▼
   user sees answer
```

---

## Concept → lesson index

| Concept | Lesson |
|---|---|
| Model wrapper, `.invoke()`, `AIMessage` | [01](01-model-wrapper.md) |
| Prompts (System / Human / Template / `ChatPromptTemplate`) | [02](02-lcel-composition.md) |
| LCEL pipe operator (`\|`) | [02](02-lcel-composition.md) |
| Output parsers (Str / Json / Pydantic / etc.) | [07](07-output-parsers.md) |
| Tool calling, `@tool`, `bind_tools`, `tool_calls`, `ToolMessage` | [03](03-agent-tool-loop.md) |
| `create_react_agent`, framework agent | [03](03-agent-tool-loop.md) |
| Token usage tracking, growth per turn | [04](04-prompt-caching.md), [08](08-chatbot-memory.md) |
| Prompt caching, `cache_control`, KV cache, prefill vs decode | [04](04-prompt-caching.md) |
| Memory, `MemorySaver`, `thread_id`, checkpointers | [08](08-chatbot-memory.md) |
| Structured output, `with_structured_output` | [05](05-structured-output.md) |
| Parallel chains, `RunnableParallel` | [06](06-parallel-chains.md) |
| Loaders, `Document`, `page_content`, `metadata` | [09](09-rag.md) |
| Splitters, `chunk_size`, `chunk_overlap` | [09](09-rag.md) |
| Embeddings, vectors, cosine similarity | [09](09-rag.md) |
| Vector stores, the 4-field record | [09](09-rag.md) |
| Retrieval, `as_retriever`, top-k | [09](09-rag.md) |
| What the LLM actually sees in RAG | [09](09-rag.md) |
| Input/output guardrails, faithfulness | [10](10-guardrails.md) |
| Production composition | [11](11-production-capstone.md) |
| MCP / tool sharing protocol | [12](12-mcp.md) |
| The agent patterns (ReAct / Reflection / PE) | [reference-agentic-patterns](reference-agentic-patterns.md) |

---

## Mental models, distilled

The seven one-liners that compress the whole course:

1. **The LLM never calls anything. The LLM Client does.** *(Tool calling, MCP, agents — all variations of one dance.)*

2. **A prompt is the input. A prompt template is a recipe for building a prompt.** *(System/Human/AI/Tool are message *roles*; templates produce typed messages from variables.)*

3. **An output parser adapts text (what the LLM emits) into typed values (what your code wants).** *(`with_structured_output` is the modern alternative: tool-calling instead of text-parsing.)*

4. **`prompt | model | parser` is sequential. `{"a": chain_a, "b": chain_b}` is parallel. Together they cover almost every LCEL pattern.**

5. **Each turn carries the whole conversation. Memory adds state. Caching keeps cost bounded.** *(Stateless model + growing history → token cost grows linearly unless caching is enabled.)*

6. **The cache discount is real because the server skips prefill — the most expensive 80% of inference — not because Anthropic is being nice.** *(The KV cache for the cached prefix is reused rather than recomputed.)*

7. **RAG = "I pick the right text client-side, the LLM reads only that text." Faithfulness asks whether the answer could be reconstructed from those chunks alone.** *(The LLM never sees vectors or the retriever; it sees a normal prompt.)*

---

## One-glance decision tree

```
"I want to..."
   │
   ├── "send one prompt, get one answer"         → pattern 1 (model.invoke) — lesson 01
   ├── "format a prompt and parse output"        → pattern 2 (prompt|model|parser) — 02
   ├── "run several prompts in parallel"         → pattern 3 (RunnableParallel) — 06
   ├── "let the model use tools"                 → pattern 4 (create_react_agent) — 03
   ├── "get a typed Python object back"          → pattern 5 (with_structured_output) — 05
   ├── "remember conversation across calls"      → pattern 6 (MemorySaver) — 08
   ├── "answer from my own documents"            → pattern 7 (RAG) — 09
   ├── "validate inputs and outputs"             → pattern 8 (guardrails) — 10
   └── "all of the above in one app"             → production_chatbot.py — 11
```

---

## One-glance economics

For Sonnet 4.6 ($3/M input, $15/M output, $0.30/M cache read, $3.75/M cache write):

| Pattern | Per-call shape | Cost driver |
|---|---|---|
| Direct call | 1 model call | ~$0.001-0.01 per call |
| Agent w/ tools | 1-N model calls per turn (N = tool steps) | grows with steps |
| Chat with memory, no cache | every turn re-sends history | grows linearly with turns |
| Chat with memory + caching | system prompt re-used at 0.1× | grows sublinearly |
| RAG | model call + embed query (cheap, local) | ~constant per query |
| Guardrails | extra cheap calls + LLM judges | +20-50% over base |
| Production capstone | all of above | ~$0.005-0.020 per turn |

---

## Related

- **Linear lessons:** [01](01-model-wrapper.md) → [02](02-lcel-composition.md) → ... → [12](12-mcp.md)
- **Pattern reference:** [reference-agentic-patterns](reference-agentic-patterns.md)
- **Full 32-session curriculum:** [`../CURRICULUM.md`](../CURRICULUM.md)
