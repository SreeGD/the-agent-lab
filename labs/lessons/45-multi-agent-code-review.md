# 45 — Multi-Agent Code Review Pipeline (Session 45)

> **Drop a PR — four specialist agents fan out in parallel and label every finding critical/major/minor/low.** Scale code reviews without scaling headcount. This session mirrors the architecture of Claude Code's own `/code-review` skill.

---

## Roadmap — where this lesson sits in the journey

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ✓ Session 39: Claude Code Hooks
  ✓ Session 40: Autonomous Workflows
  ✓ Session 41: Codebase Archaeology
  ✓ Session 42: Browser Automation
  ✓ Session 43: Scheduled Cloud Routines
  ✓ Session 44: Document & Slide Generation
  ▶ Session 45: MULTI-AGENT CODE REVIEW  ◄ HERE
```

**Maps to "12 Insane Claude Features" #10 — Run Multi-Agent Code Reviews in Parallel.**

---

## Files involved

| File | Role |
|---|---|
| [`review_orchestrator.py`](../review_orchestrator.py) | Fans out to specialist reviewers, merges findings, posts to GitHub |
| [`reviewer_security.py`](../reviewer_security.py) | Security-focused reviewer (OWASP, injection, auth) |
| [`reviewer_logic.py`](../reviewer_logic.py) | Logic & correctness reviewer (bugs, edge cases, invariants) |
| [`reviewer_style.py`](../reviewer_style.py) | Style & maintainability reviewer (naming, complexity, DRY) |
| [`reviewer_docs.py`](../reviewer_docs.py) | Documentation reviewer (docstrings, comments, changelog) |

---

## What problem it solves

Human code review has two failure modes:

1. **Coverage.** One reviewer can't hold security, logic, style, and docs in mind simultaneously. Something gets missed.
2. **Scale.** As team size grows, reviews become the bottleneck. Reviewers fatigue; standards drift.

Multi-agent code review solves both: each agent has a single focus and unlimited stamina. Four agents reviewing in parallel cover more ground than one human reviewing sequentially — and each agent maintains its own context window, so they don't interfere.

---

## The analogy

A senior engineering team does this already:

- **Security engineer** reviews for vulnerabilities
- **Tech lead** reviews logic and design
- **Senior dev** reviews style and readability
- **Tech writer** reviews docs and changelog

The difference: hiring four specialists per PR is expensive. Running four Claude agents per PR costs cents.

---

## Visual

```
  Pull Request (diff)
         │
         ▼
  ┌──────────────────────────────────────┐
  │  review_orchestrator.py              │
  │  Fan out to 4 specialists in parallel│
  └──┬─────────┬──────────┬──────────┬──┘
     │         │          │          │
     ▼         ▼          ▼          ▼
 Security   Logic      Style      Docs
 Agent      Agent      Agent      Agent
     │         │          │          │
     ▼         ▼          ▼          ▼
  Findings  Findings   Findings   Findings
  (CRITICAL) (MAJOR)   (MINOR)    (LOW)
     │         │          │          │
     └────┬────┴────┬──────┘
          │         │
          ▼         ▼
     Dedup +     GitHub PR
     Merge       Annotations
```

---

## Key patterns

### 1. Structured finding schema

All agents return findings in the same schema:

```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    LOW = "LOW"

class Finding(BaseModel):
    file: str
    line_start: int
    line_end: int
    severity: Severity
    category: str          # "security", "logic", "style", "docs"
    title: str             # one-line summary
    description: str       # detailed explanation
    suggestion: str        # concrete fix
    confidence: float      # 0.0-1.0
```

### 2. Specialist system prompts

```python
SECURITY_SYSTEM = """
You are a security-focused code reviewer. Your ONLY job is finding security vulnerabilities.

Look for:
- SQL injection (string concatenation into queries)
- Command injection (user input in shell commands)
- XSS (unescaped user output in HTML)
- Insecure deserialization
- Hardcoded secrets or credentials
- Missing authentication/authorization checks
- Path traversal vulnerabilities
- Insecure direct object references (IDOR)
- SSRF (user-controlled URLs fetched server-side)
- Missing input validation at API boundaries

For each finding, classify severity:
- CRITICAL: exploitable remotely without auth, data exposure risk
- MAJOR: requires auth or chaining, but genuinely exploitable
- MINOR: defense-in-depth issue, not directly exploitable
- LOW: informational, best practice gap

Return ONLY valid JSON matching the FindingList schema.
Only report findings you are confident about (confidence > 0.7).
"""

LOGIC_SYSTEM = """
You are a logic and correctness reviewer. Your ONLY job is finding bugs and incorrect behavior.

Look for:
- Off-by-one errors
- Null/None dereferences without checks
- Race conditions in concurrent code
- Integer overflow/underflow
- Incorrect error handling (swallowed exceptions, wrong status codes)
- Logical contradictions (condition that can never be true)
- Missing edge case handling (empty list, zero division, empty string)
- Incorrect algorithm implementation
- State machine violations
- API contract violations (calling methods in wrong order)

Severity:
- CRITICAL: causes data loss or corruption
- MAJOR: causes incorrect behavior for a common input
- MINOR: causes incorrect behavior for an edge case
- LOW: suboptimal but not incorrect

Return ONLY valid JSON matching the FindingList schema.
"""
```

### 3. Parallel fan-out

```python
import asyncio
import anthropic

client = anthropic.AsyncAnthropic()

async def run_specialist(system: str, diff: str, schema: type) -> list[Finding]:
    response = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Review this diff:\n\n```diff\n{diff}\n```\n\nReturn findings as JSON."
        }]
    )
    raw = response.content[0].text
    return [Finding(**f) for f in json.loads(raw)["findings"]]

async def review_pr(diff: str) -> list[Finding]:
    results = await asyncio.gather(
        run_specialist(SECURITY_SYSTEM, diff, Finding),
        run_specialist(LOGIC_SYSTEM, diff, Finding),
        run_specialist(STYLE_SYSTEM, diff, Finding),
        run_specialist(DOCS_SYSTEM, diff, Finding),
    )
    return deduplicate(merge_and_sort(results))
```

### 4. Deduplication

Multiple agents may catch the same issue. Deduplicate by file + line range + semantic similarity:

```python
def deduplicate(findings: list[Finding]) -> list[Finding]:
    seen: dict[str, Finding] = {}
    for f in sorted(findings, key=lambda x: x.severity):
        key = f"{f.file}:{f.line_start}-{f.line_end}"
        if key not in seen:
            seen[key] = f
        else:
            # Keep the higher severity if duplicate
            if severity_rank(f.severity) > severity_rank(seen[key].severity):
                seen[key] = f
    return list(seen.values())
```

### 5. GitHub PR annotation

```python
import subprocess

def post_review(pr_number: int, findings: list[Finding]):
    # Use `gh` CLI to post review comments
    for f in findings:
        subprocess.run([
            "gh", "pr", "review", str(pr_number),
            "--comment",
            "--body", f"**[{f.severity}] {f.title}**\n\n{f.description}\n\n**Suggestion:** {f.suggestion}",
        ])

    # Post summary as PR review
    summary = format_summary(findings)
    subprocess.run([
        "gh", "pr", "review", str(pr_number),
        "--request-changes" if any(f.severity == "CRITICAL" for f in findings) else "--comment",
        "--body", summary
    ])
```

---

## Run it

```bash
pip install anthropic pydantic

# Review a local diff
git diff main...HEAD | python review_orchestrator.py --output review.json

# Review a GitHub PR
python review_orchestrator.py --pr 123 --repo owner/repo --post-comments

# Review and get a formatted report
python review_orchestrator.py --pr 123 --repo owner/repo --format markdown > review_report.md
```

Expected output:

```
Fetching PR #123 diff (1,240 lines changed)...
Running 4 specialist reviewers in parallel...
  ✓ Security  (3.2s) → 2 findings
  ✓ Logic     (2.8s) → 4 findings
  ✓ Style     (2.1s) → 7 findings
  ✓ Docs      (1.9s) → 3 findings

Deduplicating 16 findings → 14 unique
Sorted by severity:
  CRITICAL  1  (Security: SQL injection in user search)
  MAJOR     2  (Logic: null deref in pagination, auth bypass edge case)
  MINOR     5  (Style: 3 naming issues, Logic: 2 edge cases)
  LOW       6  (Docs: missing docstrings, style cleanup)

Posting 14 inline comments to PR #123...
  ✓ Posted review (requesting changes — 1 CRITICAL finding)
```

---

## Walk-through

### Why parallel, not sequential

Sequential review = each agent sees the prior agents' findings and might anchor on them (or duplicate-check reduces coverage). Parallel = each agent has a fresh, unbiased look at the same diff. You get more signal; the merge step handles duplicates.

### Confidence filtering

Each agent assigns a confidence score. Filter low-confidence findings before posting:

```python
MIN_CONFIDENCE = {
    Severity.CRITICAL: 0.7,
    Severity.MAJOR: 0.75,
    Severity.MINOR: 0.8,
    Severity.LOW: 0.85,
}

def filter_confident(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.confidence >= MIN_CONFIDENCE[f.severity]]
```

CRITICAL findings with low confidence still get surfaced, but flagged as "unverified — please review."

### Cost per review

| Diff size | Agents | ~Tokens | ~Cost (Opus 4.7) |
|---|---|---|---|
| Small (100 lines) | 4 | 20k | $0.75 |
| Medium (500 lines) | 4 | 80k | $3.00 |
| Large (2000 lines) | 4 | 300k | $11.25 |

For large PRs, consider chunking the diff and reviewing one file at a time, then merging findings.

### This session vs. the `/code-review` skill

| | `/code-review` skill | This session |
|---|---|---|
| How triggered | `/code-review` in Claude Code | Python script / CI pipeline |
| Reviewers | Dynamically spawned subagents | Explicit specialist agents |
| Output | Inline findings in session | JSON + GitHub annotations |
| Configuration | Skill parameters | Python constants |
| Use case | Interactive, developer-driven | Automated, CI-integrated |

Build this session's pipeline for your CI/CD — it runs on every PR without human intervention.

---

## Try this

1. **Run on your own code** — pick a recent PR or branch, generate the diff, run the pipeline, see what the agents catch that human reviewers missed.
2. **Confidence calibration** — lower `MIN_CONFIDENCE` to 0.5 and re-run. How many more findings appear? Are they signal or noise?
3. **Add a fifth agent** — write a `reviewer_performance.py` that looks for N+1 queries, missing indexes, O(n²) loops, and unnecessary allocations. Add it to the parallel fan-out.
4. **CI integration** — add a GitHub Action that runs this pipeline on every PR and posts findings as review comments. Block merges if any CRITICAL finding is unresolved.
5. **Compare to human review** — run the pipeline on a PR that's already been human-reviewed. Compare findings. Where does Claude add coverage? Where does it false-positive?

---

## Mental model in one line

> **Multi-agent code review is a structured fan-out: each specialist agent gets the same diff, a single-focus system prompt, and returns typed findings — parallel execution gives full coverage in the time of one review, and dedup-merge combines the signals.**

---

## Related

- **Previous:** [44 — Document & Slide Generation](44-document-slide-generation.md)
- **The architecture mirrors:** [14 — Multi-Agent + Long-term Memory](14-multi-agent-ltm.md) (supervisor + specialist pattern)
- **Structured output from:** [05 — Structured Output](05-structured-output.md) (Pydantic finding schema)
- **CI integration uses:** [39 — Claude Code Hooks](39-claude-code-hooks.md) (hooks trigger the pipeline)
- **In production:** Claude Code's own `/code-review` and `/code-review ultra` skills use this same multi-agent architecture
- **Maps to image feature:** #10 — Run Multi-Agent Code Reviews in Parallel
- **Curriculum tracker:** Session 45 of 45 — Track M capstone
