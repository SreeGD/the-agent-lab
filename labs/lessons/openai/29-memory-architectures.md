# 29 — Memory Architectures (Session 17.5)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_openai.ChatOpenAI`, model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/29_memory_architectures_openai.py`.

> **Five distinct shapes of memory, one survey lesson.** Working, episodic, semantic, procedural, hierarchical — each has a different data structure, lookup mechanism, and cost profile. Real production agents combine them; the most expensive mistake is jamming everything into working memory and watching context (and the bill) explode.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-17 (foundation + RAG + production)                  Track F: ✓ complete
                                                           Bonus: Memory Architectures
                                                             ▶ Session 17.5: 5-PATTERN SURVEY  ◄ HERE
                                                           Track G: ○ Architect Skills
                                                             ○ Session 18: System Design Interview
                                                             ○ Session 19-21: Red-team / Governance / UX
```

**Why this lesson now:** Brij Kishore Pandey's "Top 5 Agent Memory Architectures" infographic (2026) lists five distinct shapes. The curriculum *partially* covers four of them across Sessions 8 (working), 3 (episodic), 12 (semantic-graph), 17 (skills); the fifth (hierarchical) was missing entirely. This is the unifying survey lesson — one runnable demo per pattern, side-by-side, so you can pick the right shape for a problem instead of defaulting to one and paying for it.

---

## File involved

| File | Role |
|---|---|
| [`openai/29_memory_architectures_openai.py`](../../openai/29_memory_architectures_openai.py) | Five self-contained demos, one per architecture: FIFO-evicted working memory, vector-store episodic, entity-attribute fact store, learning-loop skill library, hot/warm/cold paging. ~280 lines, runs in ~30 s, costs ~$0.05. |

---

## What problem it solves

When someone says "give my agent memory," they could mean five entirely different things:

| Phrasing | Actual need | Pattern |
|---|---|---|
| "Remember what I just said" | Hold current turn in context | Working |
| "Remember what we discussed last week" | Retrieve past specific events | Episodic |
| "Remember that I prefer dark mode" | Look up structured user facts | Semantic |
| "Remember how to do this task" | Reuse learned workflows | Procedural |
| "Remember everything but stay under the token budget" | Tier storage, page on demand | Hierarchical |

Pick the wrong shape and you over-pay (working memory for everything → bloated context), miss the recall (FIFO eviction with no backing store → forgotten 'San Francisco'), or hit confusion failures (raw history when you needed structured facts).

This lesson is the **picker** — one paragraph per pattern, one demo per pattern, one decision tree to match shape to problem.

---

## The analogy

**Human memory has the same five shapes.**

| Brij's name | Human equivalent |
|---|---|
| Working | Short-term memory (what you're holding in your head right now) |
| Episodic | "What happened on my birthday last year" |
| Semantic | "What I know is true" (Paris is the capital of France) |
| Procedural | "How to ride a bike" — encoded as motor habit |
| Hierarchical | Conscious vs. background recall vs. long-buried-but-retrievable |

When a friend asks *"do you remember when we…"* you don't search your entire life history — you retrieve from episodic memory (event-shaped). When they ask *"what's your favorite restaurant?"* you don't replay episodes — you look up a fact. Same brain, different memory modules. Agents need the same separation.

---

## Visual

```
                              ┌─────────────────┐
                              │  Current turn   │   WORKING MEMORY
                              │  + recent N     │   (FIFO eviction at token budget)
                              │  turns          │   list[Message]
                              └────────┬────────┘
                                       │  overflow
                                       ▼
                          ┌─────────────────────────┐
                          │     Recall buffer       │   HIERARCHICAL (warm tier)
                          │  in-RAM, free until      │   list[str]
                          │  paged back to hot      │
                          └────────────┬────────────┘
                                       │  overflow
                                       ▼
                          ┌─────────────────────────┐
                          │      Archival store     │   HIERARCHICAL (cold tier)
                          │  on disk, unlimited     │   SQLite / Postgres
                          └─────────────────────────┘

         ┌──────────────────────────────┐  ┌──────────────────────────────┐
         │      Episodic store          │  │    Semantic fact store       │
         │  vector store of past Q/A    │  │  dict[key, value]            │
         │  with timestamps + outcomes  │  │  favorite_city → san fran    │
         │  retrieve kNN at query time  │  │  pet_name → Pixel            │
         │                              │  │  O(1) lookup, no LLM         │
         │  EPISODIC MEMORY             │  │  SEMANTIC MEMORY             │
         └──────────────────────────────┘  └──────────────────────────────┘

                       ┌────────────────────────────┐
                       │      Skill library         │   PROCEDURAL MEMORY
                       │  list of SkillEntry        │   (description-matched workflows)
                       │  build_fraud_pipeline()    │
                       │  learns from successes     │
                       └────────────────────────────┘
```

---

## Concept walk-through

### Pattern 1 — Working memory + FIFO eviction

**Data structure:** `list[Message]` — the conversation as a flat list.
**Lookup:** integer index (just read the list).
**Cost:** every token in working memory is billed on every LLM call.

```python
BUDGET = 100
history = []

def add_turn(user_msg, asst_msg):
    history.extend([{"role":"user", "content":user_msg},
                    {"role":"assistant", "content":asst_msg}])
    while count_tokens(history) > BUDGET and len(history) > 2:
        history.pop(0); history.pop(0)   # drop oldest user+asst pair
```

Real output:
```
turn 1: total=32 tokens   evicted=0
turn 2: total=72 tokens   evicted=0
turn 3: EVICTED oldest: user='My favorite city is San Francisco.'
turn 3: total=76 tokens   evicted=1
```

The 'San Francisco' message is now **gone**. The model literally cannot answer "what was my favorite city?" — working memory dropped it.

**When to use:** the current turn + a few recent ones, always. Default to FIFO eviction at your token budget.
**Where it breaks:** anything you need to recall after eviction. Without a backing store (episodic / semantic), evictions = lost facts.

### Pattern 2 — Episodic memory (vector store of past interactions)

**Data structure:** `VectorStore[Document]` with each document = (Q, A, timestamp, outcome).
**Lookup:** kNN over query embedding.
**Cost:** one embedding call per write + one per read.

```python
Episode = {"question": ..., "answer": ..., "timestamp": "2026-04-12T...", "outcome": "positive"}
store.add_documents([Document(page_content=f"Q: {q}\nA: {a}", metadata={...})])

# On a new query:
hits = store.similarity_search("what city did I say I prefer?", k=2)
```

Real output:
```
New query: 'Remind me — what city did I say I prefer?'
Retrieved top-2 relevant episodes:
  [1] timestamp=2026-04-12T14:32:00Z  outcome=positive
      Q: What's my favorite city?
      A: San Francisco — you've mentioned it several times.
```

The 'San Francisco' fact survived working-memory eviction because it was archived episodically. Working + episodic = robust recall.

**When to use:** session-scoped or cross-session recall of past *specific* exchanges. Audit trails. "We tried X and it failed for reason Y" memories.
**Where it breaks:** structured fact lookup ("what's the user's job?"). Episodic memory will retrieve the *conversation* where they mentioned their job, which is the wrong shape — you want the fact directly.

### Pattern 3 — Semantic memory (entity-attribute fact store)

**Data structure:** `dict[key, value]` keyed by canonical fact names.
**Lookup:** `dict.get('favorite_city')` — **O(1), no embedding, no LLM**.
**Cost:** one LLM call to *extract* facts from each turn (write). Reads are free.

```python
class UserFact(BaseModel):
    key: str        # 'favorite_city', 'job_role', 'pet_name' — canonical snake_case
    value: str
    confidence: float

# Extract from each turn
facts = model.with_structured_output(FactExtraction).invoke([
    SystemMessage("Extract STABLE facts only — preferences, jobs, names."),
    HumanMessage(turn)
]).facts
for f in facts:
    fact_store[f.key] = {"value": f.value, "confidence": f.confidence}
```

Real output:
```
turn 1: 'My favorite city is San Francisco.'
  [insert] favorite_city = 'san francisco'  (confidence=1.00)
turn 2: "I'm a data scientist at a fintech company."
  [insert] job_role = 'data scientist'  (confidence=1.00)
  [insert] industry = 'fintech'  (confidence=1.00)
turn 4: 'Today the weather is rainy.'
  → no stable facts extracted (correct for questions / weather chatter).

Final fact store:
{
    "favorite_city": "san francisco",
    "job_role": "data scientist",
    "industry": "fintech",
    "pet_type": "cat",
    "pet_name": "pixel"
}
```

The extractor correctly **rejected** "the weather is rainy" (transient) and "what's the weather like in Seattle?" (a question, not a fact).

**When to use:** user preferences, profile attributes, anything that fits "{user} {is/has/prefers} {value}". The dict is small (10-200 facts per user), portable across sessions, queryable without an LLM.
**Where it breaks:** anything that requires the *narrative* — "why did you recommend that book?" needs episodic, not semantic.

> **Semantic = who the user IS. Episodic = what we've DONE together.** Run them in parallel; both feed the same prompt.

### Pattern 4 — Procedural memory + learning loop

**Data structure:** `list[SkillEntry]` where each skill has `name`, `when_to_use`, `steps`.
**Lookup:** an LLM matcher picks the best-matching skill (or returns "no match").
**Cost:** one LLM call to extract a skill after success; one LLM call to match on each new query. Reads are not free, but skip the costly re-derivation.

```python
class SkillEntry(BaseModel):
    name: str           # 'build_fraud_detection_pipeline'
    when_to_use: str    # one-sentence match description
    steps: list[str]    # generalized, reusable steps

# After a successful solve:
skill = model.with_structured_output(SkillEntry).invoke([
    "Distill this successful solution into a reusable skill...",
    f"Query: {q}\nTrace: {steps}"
])
library.append(skill)
```

Real output:
```
Round 1 (no skills yet):
  query: Build a fraud-detection pipeline.
  matched skill: (none — derive from scratch)
  agent derived solution in 5 steps. Distilling into a skill...
  [SKILL LEARNED] build_fraud_detection_pipeline

Round 2 (skill library has 1 entry):
  query: I need a system to catch credit-card fraud in real time.
  matched skill: 'build_fraud_detection_pipeline'
  agent EXECUTES stored steps instead of re-deriving.

Round 3:
  query: Help me pick a wedding venue in Hyderabad.
  matched skill: (none — correctly rejects unrelated query)
```

The library **grew at runtime**. The next fraud-detection query skips re-derivation entirely. The wedding-venue query correctly matched nothing.

**When to use:** repeatable multi-step tasks. Agents that solve customer-support tickets, ETL workflows, code-refactor patterns. Anywhere the steps generalize.
**Where it breaks:** truly novel queries (no skill matches → fall back to free derivation). Quality control matters — gate skill admission on `outcome=positive` so you don't learn bad patterns.

> **Session 17 (Claude Code skills) was the deploy-time mechanism — author SKILL.md files yourself. This pattern is the *runtime learning loop* that grows the library from experience.** Combine them: hand-author core skills, let the loop add specialized variants.

### Pattern 5 — Hierarchical memory (MemGPT-style)

**Data structure:** three tiers — `hot` (in context, tiny), `warm` (RAM, medium), `cold` (disk, unlimited).
**Lookup:** check hot first; on miss, scan warm/cold and **page back to hot**.
**Cost:** only `hot` costs tokens at inference time. Warm + cold are effectively free until something is paged in.

```python
class HierarchicalMemory:
    def add_to_hot(self, item):
        self.hot.append(item)
        while len(self.hot) > 2:    self.warm.append(self.hot.pop(0))
        while len(self.warm) > 4:   self.cold.append(self.warm.pop(0))

    def page_in(self, query):
        for tier in (self.warm, self.cold):
            for item in tier:
                if query.lower() in item.lower():
                    tier.remove(item)
                    self.add_to_hot(item)
                    return item
```

Real output:
```
After 7 inserts:
  hot (2/2):   ['user_dietary: vegetarian', 'user_languages: English, Hindi, Telugu']
  warm (4/4): ['user_job: ...', 'user_pet: ...', 'user_book_pref: ...', 'user_timezone: PST']
  cold (1/∞): ['user_favorite_city: San Francisco']

Query references the user's favorite city (now in COLD).
page_in result: 'user_favorite_city: San Francisco'

After paging in:
  hot (2/2):   ['user_languages_spoken: ...', 'user_favorite_city: San Francisco']
```

The favorite-city fact was paged back into hot. The model now sees it in context for the next call.

**When to use:** long-running agents (days, weeks) where total memory exceeds any reasonable context budget. Personal assistants. Therapy-like apps. Code-review bots that accumulate codebase knowledge.
**Where it breaks:** simple chatbots that don't need the complexity. Use working + semantic instead — hierarchical is for genuinely large memory footprints.

The real MemGPT paper backs `cold` with SQLite (or any DB), uses an LLM to decide when to page (rather than keyword match), and lets the agent issue explicit "search archive" tool calls. This demo shows the *shape*; production wires it more carefully.

---

## Run it

```
cd labs
./.venv/bin/python openai/29_memory_architectures_openai.py
```

~30 seconds, ~$0.05. The five demos are independent — you can run individual `demo_N_*()` functions interactively in a REPL if you want to poke at one.

---

## Real output highlights

The full run shows all 5 patterns. The single most pedagogically interesting moment:

```
DEMO 1 (working memory):    'San Francisco' EVICTED at turn 3.
DEMO 2 (episodic memory):   Same query recovers it from the vector store.
```

That two-demo arc captures the whole point: **no single memory pattern is sufficient**. Working memory provides recency; episodic provides depth; semantic provides structured recall; procedural provides reusable how-to; hierarchical provides the budget shape that lets them all coexist.

---

## Production patterns — how to combine them

### The default agent memory stack (the 80% case)

```
┌─ working ──┐   list[Message], FIFO at 8K-token budget
├─ semantic ──┤   dict[key, value], extracted on every substantive turn
├─ episodic ─┤   vector store, written async, retrieved when query is "have we..."
└─ procedural ─┘  hand-authored skills + optional runtime growth
```

Each LLM call's prompt looks like:
```
SYSTEM: You are <agent>. Here is what you know about the user:
        {semantic fact dump}    ← from dict, ~200 tokens

        Relevant past interactions:
        {top-3 episodic hits}   ← from vector store, ~600 tokens

USER (current turn) + history (last 5 working turns, ~400 tokens)
```

The agent doesn't know which memory store fed what — it just sees a coherent prompt with the right info.

### When to add hierarchical

Add it when:
- Total accumulated semantic facts exceed ~5K tokens (too much for every prompt)
- Episodic store is large enough that retrieving top-k still misses recent context
- You want LLM-controlled paging ("look in archive for X") as an agent tool

For most apps, hierarchical is overkill. For a personal assistant that's been with one user for 2 years — essential.

### Memory writes — when to fire

| Memory | Trigger | Frequency |
|---|---|---|
| Working | Every turn | Per turn (it IS the history) |
| Semantic | After every user message | Per turn (cheap extraction) |
| Episodic | After substantive exchanges (skip greetings) | Per ~5 turns |
| Procedural | After confirmed-success multi-step solves | Per ~10-50 successes |

Async-write everything except working memory — don't block the response on writes.

### Memory reads — when to fire

| Memory | Read trigger | Cost |
|---|---|---|
| Working | Every prompt (it's just the message list) | Free (already in prompt) |
| Semantic | Every prompt (small dict dump) | Free |
| Episodic | Every prompt for "have we / did I..." queries; skip for greetings | ~50ms embed + retrieve |
| Procedural | When agent enters a multi-step task | 1 matcher LLM call |
| Hierarchical | On a cache miss in hot — agent issues explicit `search_archive(query)` tool call | 1 lookup |

Smart routing: don't retrieve episodic on a greeting. Don't extract semantic facts from a one-word reply. The cheapest read is the one you don't do.

### Eviction policies — picking the right one

- **FIFO** — simplest, default. Drop oldest first.
- **LRU** — drop least-recently-accessed. Useful when re-references happen out of order.
- **Importance-weighted** — keep high-importance items even if old (e.g., "I'm allergic to peanuts" never gets evicted).
- **LLM-judged** — periodically ask the LLM "which turns are safe to drop?" Most expensive, also highest quality.

Start with FIFO. Move to importance-weighted when you've shipped and watched users get burned by lost facts.

### Privacy + retention

Every memory store is a privacy surface:
- **Working** — ephemeral, in-session, low risk
- **Semantic** — small structured PII (job, location, preferences). Treat as user-profile data. GDPR / DSAR endpoints needed.
- **Episodic** — full conversation log. **High risk.** Encrypt at rest. Implement retention windows. Implement per-user deletion.
- **Procedural** — workflow templates, low risk if not user-specific. High risk if a user-specific skill leaks ("how to bypass tenant X's quota check").
- **Hierarchical** — same risk profile as the underlying tiers.

---

## Try this

1. **Combine working + semantic + episodic in one demo.** Build a 10-turn conversation. After each turn: update semantic fact store; write substantive turns to episodic; cap working at 500 tokens. Then on turn 11, ask a question about turn 1. Show that the system recovers correctly (semantic / episodic backfill).

2. **Add importance weighting to FIFO.** Mark some messages as `important=True` (e.g., "I'm allergic to peanuts"). Modify the eviction loop to prefer dropping unimportant messages first.

3. **Wire hierarchical's `page_in` to use embeddings instead of keyword match.** Embed each item; on `page_in(query)`, do kNN over warm + cold. More accurate, more expensive.

4. **Build a procedural-memory CI.** Persist `library: list[SkillEntry]` to disk. Run a scheduled job that scans past episodic memory for high-success patterns and proposes new skills. Human reviews before adding. This is *automated skill mining*.

5. **Memory-bound stress test.** Run a chatbot for 100 simulated turns. Track total tokens billed, recall accuracy on facts from turn 1, response latency. Then introduce each memory pattern one at a time and watch the metrics change. Best demo of "why architecture matters".

---

## Mental model

> **Memory is not one thing — it's at least five things. Pick the shape that matches the data shape.**

| If you're trying to remember… | Reach for… |
|---|---|
| What I just said | Working |
| What we did last Tuesday | Episodic |
| That I prefer dark mode | Semantic |
| How to do this task | Procedural |
| Everything, under a budget | Hierarchical |

The cost of getting this wrong is **everything cascades into working memory**, the context bloats, and you pay 10x the necessary tokens for retrieval that an O(1) dict lookup would have handled for free.

---

## FAQ

**Q: Don't I just need MemorySaver?**
MemorySaver (Session 8) gives you working memory + persistence across `.invoke()`. That's necessary but not sufficient. You'll also need at least *semantic* (structured user facts) and *episodic* (past conversations) for any non-trivial agent. Skills (procedural) only when you have repeatable multi-step tasks. Hierarchical only at scale.

**Q: How is semantic memory different from a database?**
It IS a database — usually a KV store or a small dict. The "semantic" part is just *what's in it* (extracted facts, not raw history). The implementation can be SQLite, Redis, Postgres, or `dict[str, str]`. Pick storage based on volume + persistence needs.

**Q: Why use an LLM extractor for semantic facts instead of regex / pattern matching?**
Because users say things in arbitrary natural language. "I'm in Bangalore" / "I live in BLR" / "I'm based out of Bangalore, India" / "my home base is Bangalore" all yield `user_location = bangalore`. No regex covers them all; an LLM extractor with a structured output schema handles them with one prompt.

**Q: What if the LLM extracts wrong facts?**
Confidence scores filter the worst. Periodic LLM re-review of the fact store catches contradictions (e.g., user said "moved to Seattle" later — your `user_location` should update, not stay stale). Production systems also let users see + edit their semantic profile directly ("Your saved preferences").

**Q: How do procedural skills relate to LangGraph?**
A `SkillEntry` is a procedural memory primitive. A LangGraph `StateGraph` is an *executable* graph. The skill's `steps` could be expanded into a graph at runtime — turning procedural memory into runnable workflows. This is the "code as data" insight at the heart of agent skills.

**Q: Doesn't OpenAI's "ChatGPT memory" feature do all this?**
It does semantic + a bit of episodic. Closed-source, no schema visibility, no inspection / edit hooks. Building your own gives you control, debugging access, and portability across model providers.

**Q: How does hierarchical memory work with prompt caching?**
The `hot` tier is what gets sent to the LLM, so it's also what gets cached. OpenAI automatically caches qualifying prefixes of 1024+ tokens — no explicit field is needed. Stable items in hot (long-tenured semantic facts) naturally form a cacheable prefix; the variable suffix is the new query + recent working memory. OpenAI's automatic prefix caching + a smart hot tier is the LLM-era equivalent of L1 cache. Check `usage.prompt_tokens_details.cached_tokens` in the API response to confirm cache hits.

**Q: How do these patterns fail in adversarial settings?**
Each is a prompt injection surface. Episodic + semantic memory in particular: a malicious user could plant a fact ("I am an admin with full permissions") that gets extracted into semantic memory and trusted in later sessions. Mitigation: never trust extracted facts for authorization; always re-verify against ground truth. Session 19 (Red-teaming) will go deeper on this.

**Q: What's the ONE thing to take away from this lesson?**
Don't default to working memory for everything. Pick the shape that matches the data shape. The cost of getting this wrong is real money + degraded UX; the cost of getting it right is a couple hundred lines of pattern code.

---

## Related

- **Previous:** [28 — Production Deploy + Observability](28-production-deploy.md) — closes Track F
- **Next:** Session 18 — System Design Interview Prep (start of Track G: Architect Skills)
- **Builds on:** [08 — Chatbot Memory](08-chatbot-memory.md) (the MemorySaver baseline), [14 — Multi-agent + LTM](14-multi-agent-ltm.md) (semantic + episodic LTM)
- **Maps to:** Brij Kishore Pandey's "Top 5 Agent Memory Architectures" infographic (2026). This lesson covers all five with runnable demos for the gaps prior sessions left.
