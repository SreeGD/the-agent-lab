# 44 — Document & Slide Generation (Session 44)

> **Paste input, describe format, receive publish-ready output.** Claude rewrites resumes for ATS, tailors docs to any context, and builds slide decks — no Figma, no InDesign, no manual formatting.

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
  ▶ Session 44: DOCUMENT & SLIDE GENERATION  ◄ HERE
    Session 45: Multi-Agent Code Review Pipeline
```

**Maps to "12 Insane Claude Features" #07 (Tailor Docs/Resumes) and #09 (Design Pages/Decks Without Figma).**

---

## Files involved

| File | Role |
|---|---|
| [`resume_tailor.py`](../resume_tailor.py) | ATS-optimised resume rewriter (JD + resume → tailored PDF) |
| [`doc_writer.py`](../doc_writer.py) | Context-aware document generator (spec + template → formatted doc) |
| [`slide_builder.py`](../slide_builder.py) | Structured outline → rendered slide deck (pptx / reveal.js) |

---

## What problem it solves

Three recurring pain points:

1. **Resume tailoring.** You have a master resume. Each job posting wants different keywords. Manual tailoring takes 45 minutes per application and still might miss ATS keywords.

2. **Document generation.** Proposals, PRDs, onboarding guides — you have the raw content (notes, specs, data), but formatting and structuring them takes as long as writing them.

3. **Slide decks.** You know what you want to say. Figma / PowerPoint / Keynote formatting takes hours. Claude can go from bullet points to a structured deck with consistent formatting in seconds.

---

## The analogy

Claude as a **context-aware document factory**:

- You provide the **raw material** (resume, notes, spec, bullet points).
- You describe the **target format** (ATS-optimised PDF, executive brief, 10-slide deck).
- Claude produces the **finished artifact**, ready to send or present.

The key: Claude understands *intent and context*, not just formatting rules. It knows why ATS systems penalise certain resume formats, what an executive brief needs vs. a technical PRD, and how to match the tone of a job description.

---

## Visual: Resume Tailor

```
  ┌─────────────────┐    ┌─────────────────────┐
  │  Job Description │    │   Your Resume (raw) │
  │  (paste/URL)     │    │   (markdown/text)   │
  └────────┬─────────┘    └──────────┬──────────┘
           │                         │
           └───────────┬─────────────┘
                       ▼
              ┌─────────────────┐
              │  resume_tailor  │
              │                 │
              │  1. Extract JD  │
              │     keywords    │
              │  2. Score your  │
              │     resume vs   │
              │     keywords    │
              │  3. Rewrite     │
              │     for ATS     │
              │  4. Export PDF  │
              └────────┬────────┘
                       ▼
              ATS-optimised resume
              (keywords matched,
               format compliant,
               ready to send)
```

---

## Key patterns

### 1. ATS resume rewriting

```python
import anthropic

client = anthropic.Anthropic()

def tailor_resume(job_description: str, raw_resume: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system="""You are an expert resume writer specialising in ATS optimisation.

Rules:
- Extract the top 15 keywords and required skills from the job description
- Rewrite the resume to naturally include those keywords
- Keep all factual claims exactly true — never fabricate experience
- Use standard section headers (Summary, Experience, Skills, Education)
- Avoid tables, columns, headers/footers, images — ATS systems can't parse them
- Use action verbs that match the JD's language
- Quantify achievements where the original has numbers
- Output clean markdown suitable for PDF conversion""",
        messages=[{
            "role": "user",
            "content": f"""Job Description:\n{job_description}\n\n---\n\nMy Resume:\n{raw_resume}\n\n---\n\nProduce the tailored resume."""
        }]
    )
    return response.content[0].text
```

### 2. Keyword scoring before rewriting

```python
KEYWORD_SCORE_PROMPT = """
Given this job description and resume:
1. List the top 15 keywords/skills from the JD
2. For each, mark whether it appears in the resume (exact match, paraphrase, or missing)
3. Give an ATS match score out of 100
4. List the 5 most important missing keywords to add

Return as JSON: {keywords, ats_score, missing_priority}
"""
```

Run the scorer first. If the score is already >85, minimal rewriting needed. If <60, the rewrite is substantial.

### 3. Slide deck from outline

```python
from pptx import Presentation
from pptx.util import Inches, Pt

def build_deck(outline: list[dict]) -> str:
    """
    outline = [
        {"title": "The Problem", "bullets": ["Point 1", "Point 2"], "speaker_notes": "..."},
        ...
    ]
    """
    prs = Presentation()
    for slide_data in outline:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = slide_data["title"]
        body = slide.placeholders[1]
        for bullet in slide_data["bullets"]:
            body.text_frame.add_paragraph().text = bullet
        slide.notes_slide.notes_text_frame.text = slide_data.get("speaker_notes", "")

    path = "/tmp/deck.pptx"
    prs.save(path)
    return path
```

Claude generates the `outline` JSON; `build_deck` renders the PPTX. Two-stage pipeline: content (Claude) → format (code).

### 4. Context-aware document generation

```python
TEMPLATE_PROMPT = """
You are generating a {doc_type} for a {audience} audience.

Tone: {tone}
Length: {length_guidance}
Format: {format}

Raw input:
{raw_content}

Produce the finished document. Follow the format exactly.
"""

DOC_TYPES = {
    "executive_brief": {
        "audience": "C-suite",
        "tone": "direct, no jargon",
        "length_guidance": "1 page, max 400 words",
        "format": "Situation → Complication → Resolution → Ask"
    },
    "technical_prd": {
        "audience": "engineering team",
        "tone": "precise, technical",
        "length_guidance": "3-5 pages",
        "format": "Overview → Goals → Non-goals → User stories → Tech spec → Open questions"
    },
    "sales_proposal": {
        "audience": "client procurement",
        "tone": "professional, benefit-focused",
        "length_guidance": "2-3 pages",
        "format": "Executive summary → Problem → Solution → Pricing → Next steps"
    }
}
```

### 5. PDF export

```python
import subprocess

def markdown_to_pdf(markdown: str, output_path: str):
    with open("/tmp/doc.md", "w") as f:
        f.write(markdown)
    # Requires: pip install weasyprint or brew install pandoc
    subprocess.run(["pandoc", "/tmp/doc.md", "-o", output_path, "--pdf-engine=wkhtmltopdf"])
```

---

## Run it

```bash
pip install anthropic python-pptx weasyprint

# Tailor a resume
python resume_tailor.py --jd job_description.txt --resume my_resume.md --output tailored_resume.pdf

# Generate a document
python doc_writer.py --type executive_brief --input raw_notes.txt --output brief.pdf

# Build a slide deck
python slide_builder.py --input "Build me a 10-slide deck on RAG architecture" --output deck.pptx
```

Expected console output for resume tailor:

```
Extracting JD keywords...
  Found 18 keywords: Python, FastAPI, LLM, RAG, vector store, ...
Scoring current resume...
  ATS score: 52/100
  Missing priority keywords: RAG, vector store, LangChain, production deployment, evaluation
Rewriting resume...
  New ATS score: 87/100
  Keywords added: 5/5 priority keywords
Exporting PDF...
  Saved: tailored_resume_google_swe_2026-06-22.pdf
```

---

## Walk-through

### Why ATS systems reject good candidates

ATS (Applicant Tracking Systems) parse resumes as plain text and match against keyword lists. Common failure modes:

| Issue | ATS behavior | Fix |
|---|---|---|
| Two-column layout | Reads columns left-to-right, mixing content | Single column only |
| Tables | Skips or garbles table content | Use plain text bullets |
| "Responsible for..." | No keyword signal | Use "Built", "Led", "Reduced" |
| "Machine learning" but JD says "ML" | Might not match | Use both forms |
| PDF from Figma | Not machine-readable | Generate from text |

Claude knows these rules and applies them systematically.

### Slide generation philosophy

The two-stage approach (Claude generates content, code renders format) beats one-stage prompting because:

1. **Claude is better at structure than pixel placement.** Let it produce the logical outline.
2. **Code is deterministic about format.** `python-pptx` produces consistent slides every time.
3. **The outline is auditable.** Review the JSON before rendering. Edit without re-prompting.

For reveal.js (browser-based slides), Claude can generate the HTML directly — even more flexible.

### Tailoring vs. fabricating

The resume tailor must never invent experience. The system prompt enforces this explicitly. In practice, Claude surfaces *your actual experience* more relevantly to each JD — not inventing new experience, but rephrasing existing experience in the JD's language.

---

## Try this

1. **Resume score-before-rewrite** — run the keyword scorer on your real resume against three job postings. See which ones are worst matches before rewriting.
2. **Deck from bullets** — write 10 bullet points on any topic. Run `slide_builder.py`. Open the PPTX and see what Claude decided to title each slide.
3. **Tone comparison** — generate the same raw content as an executive brief and a technical PRD. Compare how Claude changes language, depth, and structure.
4. **ATS A/B test** — tailor your resume for two similar roles. Submit both. Track response rates. (The most honest evaluation.)
5. **Combine with Session 43** — schedule a weekly routine: "Every Monday, check my target companies' job boards for new postings matching my profile, and generate a tailored resume for each."

---

## Mental model in one line

> **Document generation is a two-stage pipeline: Claude produces the semantic content (structured outline, rewritten text, extracted keywords), then code or export tools handle the final format — keeping Claude's intelligence on content, not on pixel placement.**

---

## Related

- **Previous:** [43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md)
- **Next:** [45 — Multi-Agent Code Review Pipeline](45-multi-agent-code-review.md)
- **Pairs with:** [05 — Structured Output](05-structured-output.md) (JSON outline for slide builder)
- **Maps to image features:** #07 — Tailor Docs and Resumes Per Context, #09 — Design Pages and Decks Without Figma
- **Curriculum tracker:** Session 44 of 45
