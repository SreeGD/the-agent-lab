# 17 — Claude Skills (Session 6)

> **Package agentic-course knowledge as reusable Claude Skills.** Each `SKILL.md` is a self-contained instruction bundle with YAML frontmatter; Claude (or any MCP/skill-aware client) auto-discovers and loads it on demand by matching its `description` against user intent. The description IS the triggering mechanism.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: Agentic Patterns
                                                             ✓ S1/2/3 (lessons 12-14)
                                                           Track B: Workflow & Skill
                                                             ✓ Session 4: SDD
                                                             ✓ Session 5: Vibe Coding
                                                             ▶ Session 6: CLAUDE SKILLS  ◄ HERE
                                                           Track C-F + Phase 3 verticals
                                                           Track M: Claude Code Mastery (optional)
```

**Why this lesson now:** Sessions 4 + 5 covered *workflows* for getting code out (SDD + Vibe). Session 6 covers *knowledge packaging* — how to make domain expertise reusable across all your Claude-powered tools. Closes Track B (Workflow & Skill).

---

## Files involved

| File | Role |
|---|---|
| [`skills/agenticcourse-rag/SKILL.md`](../skills/agenticcourse-rag/SKILL.md) | RAG canonical pattern + pitfalls — loaded when user asks about retrieval |
| [`skills/agenticcourse-caching/SKILL.md`](../skills/agenticcourse-caching/SKILL.md) | Prompt caching rules + economics — loaded for caching questions |
| [`skills/agenticcourse-guardrails/SKILL.md`](../skills/agenticcourse-guardrails/SKILL.md) | Input + output guardrails patterns — loaded for safety questions |
| [`17_claude_skills_router.py`](../17_claude_skills_router.py) | Simulates Claude's triggering: cosine-similarity match between query embedding and skill descriptions |

---

## What problem it solves

You've built up real domain expertise — your `NOTES.md`, `LEARNINGS.md`, the 16 lessons. **How do you make that expertise accessible to your future LLM calls?**

Three options:
1. **Stuff everything into a system prompt.** Always loaded. Always pays tokens. Bloats context. The LLM "spreads its attention" — knowing nothing better.
2. **RAG over the docs.** Right text for the right query, but you pay for retrieval infrastructure (vector store, embedding model, chunking). Overkill for small focused topics.
3. **Skills.** Modular instruction bundles. Loaded *on demand* by matching the description to user intent. Lightweight; no vector store; bundles can include scripts + templates.

Skills are the **middle ground** between system prompts (always-on, fat) and RAG (always-needed, infrastructure-heavy).

---

## The analogy

**Recipe cards in a kitchen drawer.**

System prompt = the chef has every recipe memorized, recites them all whenever you walk in. Exhausting.

RAG = the chef searches a giant cookbook indexed by ingredient. Powerful but slow, and the cookbook needs to be built.

Skills = the chef has a small drawer of recipe cards. Each card has a one-line description on top: *"Use when the user wants pasta carbonara."* When you order, the chef glances at the cards, pulls the right one, follows it. The rest of the cards stay in the drawer.

**The description is the title on the card.** Bad title → card never gets pulled. Good title → card gets pulled exactly when needed.

---

## Visual

```
   user intent ────────────►  Claude
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Available skills:    │
                  │   • agenticcourse-rag │
                  │     desc: "Use when..."│
                  │   • agenticcourse-cache│
                  │     desc: "Use when..."│
                  │   • agenticcourse-guard│
                  │     desc: "Use when..."│
                  └─────────┬─────────────┘
                            │
              Claude matches intent → description
              (semantic similarity)
                            │
                            ▼
                  ┌───────────────────────┐
                  │  Load matching skill's │
                  │  body into context     │
                  └─────────┬─────────────┘
                            │
                            ▼
                       LLM response
                  (informed by skill body)
```

Crucially: **skills are loaded on-demand, not always.** The model's context stays lean.

---

## The skill format

```markdown
---
name: agenticcourse-rag
description: Use when the user asks about Retrieval-Augmented Generation, vector
  stores, chunking, embeddings, similarity search, or grounding LLM answers in
  private documents. Provides the canonical 6-stage pipeline, the chunk-embedding
  link, what the LLM actually sees, and common pitfalls.
---

# RAG — Canonical Pattern + Pitfalls

[the skill's actual content — instructions, examples, references]
```

**YAML frontmatter** (between `---` markers):
- `name` — the skill's identifier (used in logs, telemetry, the UI)
- `description` — **the entire triggering signal.** Write this carefully.

**Body** (after the second `---`):
- The actual instructions / knowledge that gets loaded when the skill fires
- Markdown, code blocks, tables — whatever helps Claude do the task

**Optional bundled files** (in the skill's directory next to `SKILL.md`):
- `scripts/` for helper scripts the skill references
- `templates/` for output templates
- `references/` for additional context the skill links to

---

## Run it

```bash
python 17_claude_skills_router.py
```

Expected output:

```
→ query: "How do I chunk and embed docs..."
  ► cos=0.5553  agenticcourse-rag
    cos=0.0891  agenticcourse-caching
    cos=0.0707  agenticcourse-guardrails
  → FIRES: agenticcourse-rag

→ query: "Why is prompt caching cheaper..."
  ► cos=0.5287  agenticcourse-caching
    cos=0.2312  agenticcourse-guardrails
    cos=0.0770  agenticcourse-rag
  → FIRES: agenticcourse-caching

→ query: "How do I stop my agent from leaking PII..."
  ► cos=0.3445  agenticcourse-guardrails
  → FIRES: agenticcourse-guardrails

→ query: "What's the weather in Tokyo today?"
  ► cos=-0.0069  agenticcourse-guardrails
  → NO SKILL FIRES (best score -0.0069 < threshold 0.30)
```

**Each on-topic query fires the right skill.** The off-topic query (weather) correctly triggers nothing — all skills' cosines are negative or near-zero.

---

## Walk-through

### How the matching actually works

```
1. At startup: embed every skill's `description` field, cache the vectors.
   (This is what Claude does internally too.)

2. Per user query: embed the query.

3. Compute cosine similarity between query vector and each skill's
   description vector.

4. If best match > threshold (typically 0.3-0.5): load that skill's body
   into the LLM's context for this turn.

5. If no match exceeds threshold: don't load any skill. Use the default
   system prompt only.
```

**The model never sees skills it doesn't load.** Token efficiency is the whole point.

### Why the descriptions are everything

Compare the two demo queries that fire `agenticcourse-rag`:

| Query | Wording | Description match |
|---|---|---|
| *"How do I chunk and embed docs so the model can answer questions about them?"* | technical-explicit | 0.555 |
| *"How do I make an AI bot answer questions from my company's wiki?"* (hypothetical) | conversational | ~0.40 (still fires) |
| *"How do I do RAG?"* (terse) | jargon | ~0.50 (fires) |

A well-written description **anticipates how users will ask**. It mentions both jargon (RAG, vector store, embeddings) AND lay descriptions (answering from private documents, grounding LLM answers). The model bridges between them.

### Writing good descriptions — the rubric

| Trait | Bad description | Good description |
|---|---|---|
| **Specific trigger words** | "Use this skill for RAG" | "Use when the user asks about Retrieval-Augmented Generation, vector stores, chunking, embeddings, similarity search, or grounding LLM answers..." |
| **Covers user vocabulary** | only jargon | jargon + lay phrasing |
| **States what it provides** | "Has RAG info" | "Provides the canonical 6-stage pipeline, the chunk-embedding link, common pitfalls..." |
| **Length** | 5 words | 30-80 words (sweet spot for embeddings) |

Your description's *signal* is at the trade-off: too specific = misses related queries; too vague = fires on everything and dilutes.

---

## Skills vs. system prompts vs. RAG — when to use which

| | System prompt | Skill | RAG |
|---|---|---|---|
| **When loaded** | Every call | Only when description matches | When semantic search picks the chunk |
| **Token cost** | Pays every call | Pays only when triggered | Pays per-query (top-k chunks) |
| **Granularity** | Coarse — one prompt for everything | Medium — discrete knowledge packets | Fine — chunks of any document |
| **Authoring effort** | Low (write once) | Medium (write SKILL.md + good description) | Higher (chunking, embedding, indexing) |
| **Update cadence** | Restart-app frequency | Edit file, reload | Re-index frequency |
| **Best for** | Persistent persona, style, hard rules | Domain knowledge that's needed sometimes | Searching across many docs |
| **Stakes** | Always shapes behavior | Loaded contextually | Retrieves contextually |

**A real production agent uses all three:**
- System prompt = base persona + universal rules
- Skills = domain expertise per topic
- RAG = the user's actual data + docs

---

## Production patterns this unlocks

| Pattern | Example |
|---|---|
| **Domain expertise libraries** | One skill per topic (RAG, caching, guardrails) — reusable across all your Claude-powered apps |
| **Per-team standards** | A skill captures your team's coding conventions, retrieved only when generating code |
| **Compliance triggers** | A skill that fires on financial/medical queries to inject regulatory disclaimers |
| **Tool-specific helpers** | A skill that knows how to use your company's CLI, fired when the user asks about deploys |
| **Curriculum / tutorial mode** | A skill that activates "step-by-step explanation mode" when the user is learning |
| **Author-once, use-everywhere** | The same SKILL.md works in Claude Code, Claude.ai, the Agent SDK, MCP-equipped clients |

---

## Try this

1. **Write a new skill from scratch** — pick a topic you know well (your favorite framework, a debugging pattern, a recipe). Author the SKILL.md, add it to `skills/`, re-run `17_claude_skills_router.py` with a relevant query. Watch it fire.
2. **Bad-description experiment** — change one of the existing skills' descriptions to be vague ("Use for AI stuff"). Re-run. Watch its triggering accuracy collapse.
3. **Threshold tuning** — change `SIMILARITY_THRESHOLD` from 0.30 to 0.50. Re-run. Some queries that previously fired now produce "no match." Observe the precision-vs-recall trade-off.
4. **Add a deliberately overlapping skill** — e.g., a `caching-redis` skill alongside `agenticcourse-caching`. Watch the model handle ambiguity (both might fire on a generic "caching" query).
5. **Verify with Claude Code** — copy a skill into `~/.claude/skills/` and ask Claude in the terminal a relevant question. Watch the real Claude Skill loader pick it up.

---

## Mental model in one line

> **A Claude Skill is a markdown file with a YAML frontmatter whose `description` is the entire triggering signal. The body loads into context only when the description semantically matches user intent. Skills sit between system prompts (always-on) and RAG (always-searched) — they're on-demand context.**

---

## FAQ

**Q: What's the difference between a skill and a system prompt?**

A: System prompts are **always loaded**, every single call. Skills are loaded **only when the description matches the user's intent**. So skills let you have a slim default context (cheap, fast) with rich on-demand expertise (when relevant). For knowledge you need *sometimes*, skills win. For persona/rules you need *always*, use the system prompt.

**Q: How is a skill different from RAG?**

A: A skill is **one self-contained instruction bundle**. RAG retrieves **chunks from many documents**. Skills are best for "here's how to do X" (instructions); RAG is best for "find the answer in our docs" (information retrieval). Real systems use both.

**Q: Where do I actually put skills for Claude Code?**

A: `~/.claude/skills/<skill-name>/SKILL.md` for user-level skills, or `.claude/skills/<skill-name>/SKILL.md` for project-level. Plugins also ship skills. Claude Code discovers them automatically.

**Q: What does Claude do with the skill's body?**

A: When the skill fires, its body is loaded into the LLM's context (effectively appended to the system prompt for that turn). The LLM then uses the body to inform its response — same way it would use any context.

**Q: How do I make a skill that always fires?**

A: You don't. Skills are designed to be conditional. If you need always-on behavior, use the system prompt. If you need behavior that's *almost always* on, write a description that matches almost any user intent — but then you've essentially recreated the system prompt with extra steps.

**Q: Can a skill call other skills?**

A: Skills don't directly invoke other skills (no skill-to-skill RPC). But a skill's body can reference other skills' content, link to other files in its directory, or instruct the LLM to use specific tools. The composition happens in the LLM's reasoning, not in the skill metadata.

**Q: How long should the body be?**

A: 50-500 lines is the sweet spot. Under 50 = probably not worth the manifest overhead. Over 500 = consider splitting into multiple skills with different descriptions, or moving long reference material to a file the skill links to.

**Q: Can a skill include code?**

A: Yes. The body is markdown — code blocks render normally. Skills can also include `scripts/` in their directory and instruct the LLM to use them. Common pattern: skill body says "use this template" and points to a file the LLM reads via a tool.

**Q: How do I version skills?**

A: Git the `skills/` directory like any code. Each skill is just a markdown file plus optional helpers. Production systems treat skills like microservices: versioned, reviewed, deployed.

**Q: What happens if two skills match equally?**

A: Both can be loaded — most skill loaders allow it. The LLM sees both bodies in context and decides how to combine them. For mutually exclusive skills, write descriptions that don't overlap.

**Q: Is this Anthropic-specific?**

A: The SKILL.md format is Anthropic's (used by Claude Code, Claude.ai, Claude Agent SDK). The *concept* — on-demand context loaded by semantic match — is general and could be implemented for any LLM. The format is converging across vendors but Anthropic's leading.

**Q: If a user query contains PII (like an SSN), does the matching skill block it from reaching the LLM?**

A: **No. Skills do not block anything.** A skill is markdown content that gets loaded into Claude's context when the description matches. It has no execution power — it cannot intercept, redact, or refuse a request. When you see `agenticcourse-guardrails` describe PII regex as the "free, ~1 ms" first defense, that's *advice* about how to design a block, not the block itself. The block lives in your application code (e.g., `contains_pii()` in `labs/32_governance.py`), not in the skill file.

**Q: What's the difference between a skill being TRIGGERED and a skill ENFORCING something?**

A: **Triggering** = the description matches the user's intent → the body is loaded into context. **Enforcement** = something at runtime actually rejects, sanitizes, or redirects the request. Skills only do triggering. Enforcement is always a separate layer — application code, hooks, middleware, or a gateway. The skill makes Claude *smarter when designing* the enforcement; it doesn't *become* the enforcement.

**Q: So where does enforcement actually happen — skill, hook, application code, or gateway?**

A: Different layers for different jobs:

| Concern | Mechanism | Where it lives |
|---|---|---|
| **Knowledge** about how to design a check | Skill (SKILL.md content) | `labs/skills/<name>/SKILL.md` — the *blueprint* |
| **Enforcement in your application** | Code (regex + pipeline) | Your service code (e.g., `governed_pipeline()` in Session 20) |
| **Enforcement at the Claude Code CLI** | UserPromptSubmit hook | `~/.claude/settings.json` hooks block + shell script |
| **Enforcement at the network edge** | Gateway / proxy filter | Cloudflare, AWS WAF, Envoy filter — before the API call |

The skill is the *blueprint*; code/hooks/gateways are the *machinery*. Skills travel with you across all of those layers (they teach Claude the right pattern wherever Claude is helping you build); the enforcement always lives in one of the runtime layers.

**Q: How do I make Claude Code itself refuse PII-containing prompts (so the CLI blocks even my own typos)?**

A: A `UserPromptSubmit` hook in `~/.claude/settings.json`. The hook is a shell command that runs before every prompt is sent; non-zero exit blocks the submission. Example:

```bash
#!/usr/bin/env bash
# ~/.claude/hooks/user-prompt-submit.sh
if echo "$CLAUDE_USER_PROMPT" | grep -qE '\b\d{3}-\d{2}-\d{4}\b'; then
  echo "ERROR: prompt contains SSN; refusing to send" >&2
  exit 1
fi
```

```jsonc
// ~/.claude/settings.json
{
  "hooks": {
    "UserPromptSubmit": [{ "command": "~/.claude/hooks/user-prompt-submit.sh" }]
  }
}
```

Now Claude Code blocks the prompt before it reaches the API — the hook is the enforcement; the `agenticcourse-guardrails` skill (when loaded by topic match) would teach Claude *what the hook should check for*, not perform the check.

---

## Related

- **Previous:** [16 — Vibe Coding](16-vibe-coding.md)
- **Next:** Session 7 — Anthropic SDK / Claude Agent SDK (Track C)
- **The triggering mechanism is similar to:** [09 — RAG](09-rag.md) (cosine over descriptions vs. cosine over chunks)
- **Contrast with always-loaded context:** [04 — Prompt caching](04-prompt-caching.md) (system prompt caching)
- **Track M Session 38** (optional) — CLAUDE.md best practices, the *other* persistent context layer
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 6 of 40
