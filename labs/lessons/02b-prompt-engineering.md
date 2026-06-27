# Session 02b — Prompt Engineering Deep Dive

> **Goal:** Move from "just ask the model" to deliberate prompt design. By the end of this session you can measure the quality difference between five strategies using token cost and an LLM-judge score.

---

## 1. System Prompt Anatomy

Every Claude call is assembled from three layers:

```
┌─────────────────────────────────────────────────┐
│  SYSTEM PROMPT                                  │
│  • Role & persona ("You are a sentiment expert")│
│  • Output format contract (JSON schema)         │
│  • Constraints (no prose, max 200 tokens)       │
│  • Examples (optional — see few-shot section)   │
├─────────────────────────────────────────────────┤
│  HUMAN TURN (user message)                      │
│  • The actual task / input data                 │
├─────────────────────────────────────────────────┤
│  ASSISTANT TURN (optional pre-fill)             │
│  • Constrain the reply start: '{"sentiment":'   │
└─────────────────────────────────────────────────┘
```

**Why it matters:** The system prompt is cached separately by Claude's prompt-caching layer (Session 04). Keep the static scaffold in the system prompt and inject only the variable input in the human turn. This keeps cache hit rates high and costs low.

---

## 2. Zero-Shot Prompting

The simplest strategy: hand the raw task to the model with no guidance.

```python
messages = [{"role": "user", "content": task}]
```

**Strengths:** minimal tokens, fast to write.  
**Weaknesses:** output format is unpredictable — the model may add prose, change key names, or omit fields.

**When to use:** prototyping; tasks where format doesn't matter.

---

## 3. Few-Shot Prompting

Prepend worked examples before the live input. This acts as an implicit format spec.

```
Example 1:
Input: "Loved the fast shipping and the item works perfectly!"
Output: {"sentiment": "positive", "urgency": "low", "one_line_summary": "Happy customer"}

Example 2:
Input: "Received wrong item, very disappointed."
Output: {"sentiment": "negative", "urgency": "medium", "one_line_summary": "Wrong item"}

Now classify:
<live input here>
```

**Rules for good few-shot examples:**
1. Cover the full range of label values (positive / negative / neutral; low / medium / high).
2. Match the exact output schema you want — the model copies it.
3. Keep examples short; 2–4 is usually enough.
4. Place examples *before* the live input, never after.

**Cost trade-off:** Examples add input tokens. With prompt caching, recurring example blocks become nearly free after the first call.

---

## 4. Chain-of-Thought (CoT) Prompting

Ask the model to reason aloud before giving the final answer.

```python
content = (
    f"{task}\n\n"
    "Think step by step: first identify emotional tone, "
    "then assess urgency from the described situation, then summarize."
)
```

### CoT Reasoning Flow

```
User Input
    │
    ▼
Step 1: Identify Tone
    │  "broken product" → negative signal
    │  "ignored for 2 weeks" → frustration signal
    ▼
Step 2: Assess Urgency
    │  2-week delay + broken product → high urgency
    ▼
Step 3: Compose Summary
    │  one-line human-readable label
    ▼
Final JSON Output
```

**When CoT helps most:** multi-step reasoning, arithmetic, classification with nuanced edge cases.  
**When CoT hurts:** simple lookups (wastes tokens and adds latency).

**Zero-Shot CoT shortcut:** append `"Think step by step."` to any prompt without writing explicit reasoning steps. Works surprisingly well.

---

## 5. XML Structuring for Claude

Claude is trained on vast amounts of XML-tagged data. Wrapping task components in semantic tags dramatically improves instruction following.

```python
content = (
    "<task>Classify the customer message below.</task>\n"
    "<message>The product arrived broken and support ignored me.</message>\n"
    "<instructions>Output JSON only, no prose.</instructions>"
)
```

### XML Tag Best Practices

| Tag pattern | Purpose |
|---|---|
| `<task>...</task>` | High-level goal |
| `<instructions>...</instructions>` | Format / constraint rules |
| `<example>...</example>` | Few-shot examples |
| `<document>...</document>` | Long reference content |
| `<thinking>` (reserved) | Extended thinking output block |

**Why XML beats prose headers:** Claude treats XML tags as structural boundaries, not natural language. Instruction leakage (the model blending task and instructions) is significantly reduced.

**Tip:** Never use `<system>` — Claude reserves that for its own system prompt; using it in a user turn can cause unexpected behavior.

---

## 6. Extended Thinking (`budget_tokens`)

Extended thinking gives Claude a scratchpad for multi-step reasoning before it writes its final response. The scratchpad content appears in `content` blocks of `type="thinking"`.

```python
response = client.messages.create(
    model="claude-opus-4-8",   # Opus required; no temperature param
    max_tokens=1024,
    thinking={"type": "enabled", "budget_tokens": 2000},
    betas=["interleaved-thinking-2025-05-14"],
    messages=[{"role": "user", "content": task}],
)
```

### Thinking Budget Diagram

```
max_tokens = 1024
budget_tokens = 2000
                                          ┌──────────────────────────────┐
Request ──────────────────────────────▶   │  Thinking scratchpad         │
                                          │  (up to 2000 tokens)         │
                                          │  NOT returned in output_tokens│
                                          └──────────────────────────────┘
                                                        │
                                                        ▼
                                          ┌──────────────────────────────┐
                                          │  Final answer                │
                                          │  (up to 1024 tokens)         │
                                          └──────────────────────────────┘
```

**Important constraints:**
- `budget_tokens` must be ≥ 1024 and < `max_tokens` for the thinking pass.
- Do **not** pass `temperature` when using `claude-opus-4-8` — it is deprecated in Opus 4.x.
- The `betas` flag enables interleaved thinking (thinking blocks woven between text blocks).
- Thinking tokens are billed at the same rate as output tokens.

**When to use extended thinking:** tasks requiring deliberation — legal reasoning, code architecture, multi-hop inference. Overkill for simple classification.

---

## 7. Workbench Walk-Through — Comparing All Five Strategies

Run the lab to produce a comparison table:

```bash
python labs/02b_prompt_engineering.py
```

Expected output shape:

```
PROMPT ENGINEERING WORKBENCH
Task: A customer writes: 'The product arrived broken and support ignored...

Strategy               Score  In tok  Out tok   Cost USD
---------------------------------------------------------
zero_shot                  3     102       38  $0.000876
few_shot                   4     215       35  $0.001170
cot                        4     142       85  $0.001701
xml_structured             5     118       38  $0.000924
extended_thinking          5     102     1024  $0.015666
```

### Reading the Table

| Column | What it tells you |
|---|---|
| Score | LLM-judge rating 1–5 (see `score_output`) |
| In tok | Prompt tokens sent to the model |
| Out tok | Completion tokens returned |
| Cost USD | Calculated at Sonnet ($3/$15 per M tokens) |

**Pattern:** few-shot and XML-structured typically score highest at low cost. CoT adds tokens for marginal gain on simple tasks. Extended thinking is the most expensive but most reliable for complex reasoning — justified only when accuracy is critical and budget allows.

---

## 8. LLM-as-Judge (`score_output`)

Rather than hard-coding expected outputs, we ask a second Claude call to score each result:

```python
def score_output(task: str, output: str, client: anthropic.Anthropic) -> int:
    prompt = (
        f"Task: {task}\n\nOutput to grade:\n{output}\n\n"
        "Rate the output quality 1–5 (5=perfect JSON with correct fields). "
        "Reply with a single digit only."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    return max(1, min(5, int(response.content[0].text.strip()[0])))
```

**Why LLM-as-judge works for this use-case:**
- The expected output schema is well-defined (JSON with three specific keys).
- A 1–5 rubric is simpler than exact-match — resilient to whitespace / key-order differences.
- For production, cache the system prompt of the judge call to reduce judge overhead.

**Caveats:** LLM judges can be biased toward longer outputs. For high-stakes evaluations, use a jury of models (average scores) or structured rubrics with explicit criteria per point.

---

## 9. Connecting to Adjacent Sessions

| Session | Connection |
|---|---|
| 02 (LCEL Chains) | Prompt templates in LangChain wrap these same patterns in a composable interface |
| 04 (Prompt Caching) | System prompts and few-shot examples are prime caching candidates |
| 05 (Structured Output) | `with_structured_output()` enforces schema — XML structuring is its manual equivalent |
| 07 (Output Parsers) | Fallback parsing for when XML/few-shot still produces prose |

---

## Key Takeaways

1. **Default to XML structuring** for Claude — it is the most token-efficient way to enforce output format.
2. **Few-shot beats zero-shot** almost always when you control the example quality.
3. **CoT is situational** — run it only when reasoning steps actually matter for the answer.
4. **Extended thinking is a budget knob** — set `budget_tokens` proportional to task complexity.
5. **LLM-as-judge** closes the evaluation loop so you can compare strategies programmatically.
6. **Never pass `temperature` to `claude-opus-4-8`** — it is a deprecated parameter in Opus 4.x.
