# 34 — Suryapet Farm Planner (Session 22)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_openai.ChatOpenAI`, model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/34_farm_planner_engine_openai.py`.

> **The largest single session in the curriculum so far — a small product, not a lab demo.** Knowledge-grounded farm-planning advisor for Telangana's Suryapet / Jangaon / Nalgonda triangle: pick a farmer profile, set goals + constraints, and the LLM generates a multi-year crop plan with mixed-farming options (dairy, apiary, poultry, fish, sericulture, mushroom), exotic crop integration (avocado, dragon fruit, pomegranate, etc.), sustainability practices, a 10-year cash flow, and concrete next steps — wrapped in a Streamlit UI with PDF export and a FastAPI stub for the future React frontend.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 3: VERTICALS ═══════

  ✓ 01-21 (foundation + RAG + production + architect)      Track H: AGRICULTURE
                                                              ▶ Session 22: FARM PLANNER  ◄ HERE
                                                              ○ Session 23: Crop Diagnostic (vision)
                                                              ○ Session 24: Vernacular Bot (WhatsApp)
                                                            Track J: ○ Finance
                                                            Track K: ○ Vidya Karana
                                                            Track L: ○ Family AI
                                                            Track M: ○ Claude Code Mastery
```

**Why this lesson now:** Phase 1 + 2 built the LLM toolkit (LangChain, RAG, eval, cost, governance, UX). Phase 3 turns the toolkit on real vertical domains. Agriculture is the chosen first vertical because the three constraints — multi-modal, offline-tolerant, ₹-paise unit economics — force the most interesting architectural choices in the entire curriculum.

This session focuses on the **knowledge-grounded LLM pattern**: embed 7-8K tokens of regional expertise into the system prompt so the advisor stops giving generic "grow tomatoes" answers and starts giving real Suryapet-specific guidance with variety-level economics, govt scheme references, and supplier contacts.

---

## Files involved

| File | Role |
|---|---|
| [`openai/34_farm_planner_engine_openai.py`](../../openai/34_farm_planner_engine_openai.py) | **Pure Python engine** — no UI imports. All business logic: profile + plan I/O, LLM call with knowledge-base-grounded system prompt, sustainability scoring (deterministic), markdown + PDF rendering. Reusable from any UI. |
| [`34_farm_planner_ui.py`](../34_farm_planner_ui.py) | **Streamlit UI** — multi-page form-driven app. Calls engine functions; no business logic of its own. Run with `streamlit run 34_farm_planner_ui.py`. (Swap engine import to use this OpenAI variant.) |
| [`34_farm_planner_api.py`](../34_farm_planner_api.py) | **FastAPI stub** — REST endpoints wrapping the same engine. Proves the future React-frontend migration path is a swap, not a rewrite. Run with `uvicorn 34_farm_planner_api:app`. |
| [`agritech/landscape.md`](../agritech/landscape.md) | Slim AgriTech AI landscape (stakeholders, why this is uniquely demanding, use-case taxonomy) |
| [`agritech/telangana_knowledge_base.md`](../agritech/telangana_knowledge_base.md) | **The 7K-token knowledge base** embedded into the system prompt. Districts, soils, variety economics, mixed farming, sustainability, govt schemes, suppliers, market channels, wildlife matrix, sustainability scoring rubric. |
| [`farm_profiles/sample_*.json`](../farm_profiles/) | Three sample profiles — Suryapet (5 ac, mixed regenerative), Jangaon (8 ac, black cotton commercial), Nalgonda (12 ac, alluvial canal command commercial+perennials). |

---

## What problem it solves

Default LLM farm advisors fail in three predictable ways:

1. **Climate-blind recommendations.** "Try Hass avocado!" — except Suryapet summer hits 38-40°C, which kills Hass. Fuerte / Pollock / Ettinger are the green-skin varieties that work; a generic LLM doesn't know to recommend them.

2. **Variety-agnostic economics.** "Lemon is profitable!" — except Thailand Lemon fetches +40-50% vs Kagzi, Vikram Seedless +60-80%, Pramalini is the disease-resistant backup. Variety-level guidance is where the actual value is, and generic LLMs operate at crop level.

3. **No regional supply chain knowledge.** "Sell at the local mandi!" — except Jangaon's primary wholesale is Warangal (60 km), Nalgonda's is Miryalaguda, Suryapet routes to Hyderabad Monda (120 km). And the suppliers (SKLTSHU Rajendranagar, Deccan Exotics in Kukatpally, Indo Israel for Ashdot 17 rootstock) are public-domain regional knowledge that's missing from default training.

The advisor fixes all three by embedding the [Telangana Knowledge Base](../agritech/telangana_knowledge_base.md) into the system prompt. OpenAI automatically caches qualifying prefixes (1024+ tokens), so repeated planning runs are cheap — no explicit cache field is needed. Same LLM, dramatically better output.

---

## The analogy

**A doctor with the local case notebook vs a doctor with only textbook knowledge.**

A doctor at a tertiary-care city hospital has textbook knowledge of cardiac disease. A district doctor in Nalgonda has the same textbook knowledge *plus* the local case notebook: "this kind of MI pattern is unusual in our patient demographic," "the nearest cath lab is 80 km in Hyderabad, plan retrieval accordingly," "this medication has supply issues in the district pharmacies — use the alternative."

Same training. Different outcomes. The local notebook is the difference.

The Telangana Knowledge Base is the local case notebook for farm planning. The LLM has the textbook (training data); the knowledge base is the Suryapet-specific notebook.

---

## Visual

```
┌────────────────────────────────────────────────────────────────────────┐
│                            STREAMLIT UI                                │
│                                                                        │
│  Home → Farm Profile → Goals & Constraints → Generate Plan             │
│             ↓                ↓                       ↓                 │
│   farm_profiles/      session state           View Plan + Download     │
│   sample_*.json                               (Markdown / PDF)         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ calls engine functions
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│             ENGINE (34_farm_planner_engine_openai.py)                  │
│                                                                        │
│  generate_farm_plan(profile, goals) ─┐                                 │
│                                      ▼                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  System prompt (stable 7K-token prefix, auto-cached by OpenAI)  │  │
│  │   • 7K-token Telangana Knowledge Base inlined                   │  │
│  │   • Per-district: Suryapet / Jangaon / Nalgonda                 │  │
│  │   • Variety economics + suppliers + govt schemes                │  │
│  │   • Sustainability rubric + wildlife matrix                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              +                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  User prompt = profile JSON + goals JSON + planning directive   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                         │
│  gpt-4o with_structured_output(FarmPlan)                               │
│  max_tokens=8192, timeout=240s, retry x3 with exponential backoff      │
│                              ↓                                         │
│  FarmPlan (Pydantic):                                                  │
│    - crops[] (variety-level, with confidence)                          │
│    - livestock[] (dairy / poultry / fish)                              │
│    - apiary (species + boxes + placement strategy)                     │
│    - sustainability_practices[]                                        │
│    - year_by_year_cash_flow[] (10 years)                               │
│    - subsidies + suppliers + market channels                           │
│    - immediate_next_steps + pilot recommendation                       │
│                              ↓                                         │
│  score_sustainability(plan) → composite + 5-axis breakdown             │
│  (deterministic, no LLM)                                               │
│                              ↓                                         │
│  save_plan() → farm_plans/<farmer_id>/<plan_id>.json                   │
│  render_plan_markdown() / render_plan_pdf() — both available           │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ same engine functions
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│           FASTAPI STUB (34_farm_planner_api.py — future)               │
│                                                                        │
│  POST /profile · GET /profile/{id} · POST /plan · GET /plan/{id}.pdf   │
│  → wraps same engine functions as REST. Swap UI to React when ready.   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Concept walk-through

### 1. The knowledge base is the system prompt

```python
from langchain_openai import ChatOpenAI

SYSTEM_PROMPT_TEMPLATE = """You are a senior farm-planning advisor for the
Suryapet / Jangaon / Nalgonda region of Telangana, India...

KNOWLEDGE BASE (authoritative, do not contradict):
==================================================
{knowledge_base}
==================================================
"""

def _build_system_prompt() -> str:
    knowledge = _load_knowledge_base()
    return SYSTEM_PROMPT_TEMPLATE.format(knowledge_base=knowledge)
```

The 7K-token knowledge base is inlined into the system prompt as a plain string. OpenAI automatically caches qualifying prefixes (1024+ tokens) that are reused across requests — no explicit `cache_control` field is needed. After the first call, subsequent planning requests that reuse the same stable system prompt prefix benefit from cached pricing. Check `usage.prompt_tokens_details.cached_tokens` in the response to confirm cache hits.

**Note:** Unlike the Anthropic version, OpenAI's prefix caching is fully automatic — there is no `cache_control: {"type": "ephemeral"}` field to set. Just reuse the same stable system prompt and the caching happens transparently.

### 2. Pydantic schemas are the contract

```python
class CropInPlan(BaseModel):
    crop_name: str
    variety: str | None
    local_name: str | None
    role: Literal["short_term_cash_crop", "medium_term_crop",
                  "perennial_anchor", "intercrop", "boundary_crop"]
    acres_allocated: float
    time_to_first_yield_years: float
    peak_production_year_start: int
    peak_production_year_end: int
    revenue_per_acre_at_peak_inr: str
    year_1_investment_inr: str
    breakeven_year: int
    # ... 20+ fields total
    is_exotic_high_value: bool
    pollinator_friendly: bool
    confidence_self: float
    confidence_meta: float
```

The schema *forces the LLM to generate variety-level detail*. Without a `variety` field, the LLM would say "lemon"; with the field, it says "Thailand Lemon" because the schema asks for it. The `confidence_self` and `confidence_meta` fields (Session 20 pattern) carry honest uncertainty through to the UI.

### 3. The engine is a swap point, not a tangle

```python
# Public API of 34_farm_planner_engine_openai.py
list_profiles() -> list[ProfileSummary]
load_profile(farmer_id) -> FarmProfile
save_profile(profile) -> Path
delete_profile(farmer_id) -> None

generate_farm_plan(profile, goals) -> FarmPlan
score_sustainability(plan) -> SustainabilityScore
save_plan(plan) -> Path
load_plans_for_farmer(farmer_id) -> list[PlanSummary]

render_plan_markdown(plan) -> str
render_plan_pdf(plan, path) -> Path
```

Streamlit UI imports these. FastAPI stub imports these. A future React frontend will call the FastAPI endpoints which call these. Tests would import these directly. **The engine never imports anything from the UI side.** That's the architecture decision that makes the Streamlit→React swap painless.

### 4. Sustainability scoring is deterministic post-LLM

```python
def score_sustainability(plan: FarmPlan) -> SustainabilityScore:
    practices = {p.practice for p in plan.sustainability_practices}

    # 1. Soil health (0-20)
    soil = 0.0
    if "crop_rotation" in practices: soil += 5
    if any(p in practices for p in ("intercropping", "cover_crops")): soil += 5
    if any(p in practices for p in ("composting", "vermicomposting")): soil += 5
    if "zbnf_practices" in practices: soil += 5
    soil = min(soil, 20)
    # ... 4 more axes
```

The score is computed from the plan structure deterministically — not by asking the LLM. This matters because:
- **Reproducible**: same plan → same score, every time
- **Cheaper**: no extra LLM call
- **Auditable**: the rubric is in the code, not in a prompt
- **Tuneable**: change the weights and re-score every saved plan instantly

The composite is 0-100; per-axis scores out of 20; recommendations to lift the score are surfaced as concrete actions.

### 5. The Streamlit → FastAPI migration path

`34_farm_planner_api.py` is ~150 lines of FastAPI that wraps the same engine functions as REST endpoints:

```python
@app.post("/plan", response_model=FarmPlan)
def generate_plan(req: GeneratePlanRequest) -> FarmPlan:
    plan = engine.generate_farm_plan(req.profile, req.goals)
    if req.save:
        engine.save_plan(plan)
    return plan

@app.get("/plan/{farmer_id}/{plan_id}.pdf")
def get_plan_pdf(farmer_id: str, plan_id: str):
    plan = engine.load_plan(farmer_id, plan_id)
    with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        out = Path(tmp.name)
    engine.render_plan_pdf(plan, out)
    return FileResponse(out, media_type="application/pdf", ...)
```

When you decide to swap UI from Streamlit to React/mobile:
1. Run this file in production via uvicorn (Session 17 deploy pattern)
2. Expand with auth + Postgres (replace JSON file storage)
3. Frontend talks to the API; engine unchanged

Streamlit keeps running locally for power users / KVK staff. Both UIs can coexist on the same engine.

---

## Run it

### Streamlit UI (recommended for first run)

```bash
cd labs
./.venv/bin/python -m streamlit run 34_farm_planner_ui.py
```

Browser opens at `http://localhost:8501`. Pick `sample_suryapet` from the Home page → look at the auto-loaded profile → go to Goals & Constraints → tick `Include dairy` and `Include apiary` → Generate Plan → watch the spinner (~30-120s) → View Plan → explore tabs → Download as PDF.

### FastAPI stub (future migration preview)

```bash
cd labs
./.venv/bin/python -m uvicorn 34_farm_planner_api:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the auto-generated Swagger UI. Try:
- `GET /profile` to list samples
- `GET /profile/sample_suryapet` to see the JSON
- `GET /health` for liveness/readiness
- `POST /plan` with a body containing profile + goals to generate

### Engine sanity check

```bash
OPENAI_API_KEY=sk-... ./.venv/bin/python openai/34_farm_planner_engine_openai.py
```

Prints: knowledge base size, profile directory, list of loaded profiles. No LLM call.

---

## What a generated plan looks like (real output)

The committed [`farm_plans/sample_plan_suryapet.json`](../farm_plans/sample_plan_suryapet.json) is an **actual saved plan** generated against the Suryapet sample profile with `diversification_resilience` + dairy + apiary + exotic crops of interest = avocado/dragon fruit/moringa. Highlights below; the full JSON has every field populated.

**Runtime: ~5.5-6 minutes** for the full plan (system prompt embedding the 7K-token KB + 8K-token structured output). Cost ~$0.20-0.30 with gpt-4o. The engine's timeout is set to 600s for this reason; first request writes a cache, subsequent calls with the same prefix benefit from automatic caching.

### Plan summary (LLM-generated)

> A 10-year diversification-resilience plan for Ravi Kumar's 5-acre farm in Kethepally, Suryapet. The plan retains the existing cotton (2 ac) and pigeonpea (1 ac) as short-term cash anchors, then progressively converts 2 acres into high-value perennials — **Thailand Lemon (1 ac) and Dragon Fruit (0.5 ac pilot)** — with commercial Moringa on the boundary. A **Fuerte/Pollock Avocado micro-pilot (0.25 ac)** is introduced in Year 2 after lemon establishment is confirmed. Dairy is upgraded from 1 local cross to **2 Sahiwal cows**, and a **10-box Apis mellifera apiary** is added for pollination synergy and honey income. ZBNF transition begins in Year 1 via Jeevamruta and vermicomposting, targeting organic certification by Year 4. Total Year 1 investment is kept within ₹4 lakh. By Year 6+, projected net farm income is **₹6–10 lakh/year** across all enterprises.

### 6 crops (variety-level granularity)

| Crop | Variety | Role | Acres | Y1 Investment | Confidence |
|---|---|---|---|---|---|
| Cotton | **Bt Cotton (NHH 44 or Ankur 651)** | short_term_cash_crop | 2.0 | ₹25-35K | 0.88 |
| Pigeonpea | **ICPL 87119 (Asha) or PRG 158** | intercrop | 1.0 | ₹10-15K | 0.88 |
| Thailand Lemon | **Thailand Lemon (Citrus limon — Thai selection)** | perennial_anchor | 1.0 | ₹45-60K | (high) |
| Dragon Fruit | **Red-flesh Vietnamese (Hylocereus polyrhizus) — pilot** | medium_term_crop | 0.5 | ₹1.5-2L | (high) |
| Moringa | **PKM-1 (commercial Drumstick)** | boundary_crop | 0.25 | ₹8-12K | (high) |
| Avocado | **Fuerte (primary) + Pollock (pollinator pair)** | perennial_anchor (micro-pilot) | 0.25 | ₹40-60K | (medium) |

**Notice the depth**: NOT "lemon" but "Thailand Lemon (Citrus limon — Thai selection)". NOT "cotton" but "Bt Cotton (NHH 44 or Ankur 651)" with the Telugu local name "Patti". NOT "pigeonpea" but the specific ICAR cultivar "ICPL 87119 (Asha)". Suppliers named per crop: Ankur Seeds, Nuziveedu Seeds for cotton; SKLTSHU Rajendranagar for perennials; Indo Israel Avocado for the Ashdot 17 rootstock. This is what knowledge grounding looks like — the LLM is not making up generic plausible-sounding names; it's surfacing the actual ICAR / Telangana extension recommended cultivars from the knowledge base.

### Livestock

| Type | Breed | Count | Monthly net | Notes |
|---|---|---|---|---|
| Dairy cow | **Sahiwal** (upgrade from local cross) | 2 | ₹6,000-11,000 | NLM 25-50% subsidy on indigenous |

### Apiary

- **10 boxes of Apis mellifera** (Italian honey bee) for higher yield + Suryapet's intensive flowering crop calendar
- Placement near lemon + drumstick + cotton/pigeonpea flowering windows
- MIDH ₹2,000/box subsidy = ₹20,000 savings
- Expected: 25 kg/box/year × ₹250/kg = ₹62,500/year honey revenue
- Bonus: 25-40% pollination yield boost on lemon + drumstick (counted in main-plan revenue)

### Sustainability score: 31/100

This is **lower than expected** because the LLM omitted the `sustainability_practices` list in this run (output truncated against the 8K max_tokens budget — the schema is large). Without practices, the deterministic scorer falls back to what's structurally present:

- **Soil health: 0/20** (no practices listed; ZBNF mentioned in summary but not as a structured practice)
- **Water efficiency: 3/20** (drought-tolerant millet not in this plan; drip already exists)
- **Biodiversity: 20/20** (6 crops + apiary + livestock + boundary crop — max points)
- **Carbon: 3/20** (perennials present, but no solar/biogas/explicit agroforestry)
- **Input self-sufficiency: 5/20** (Sahiwal indigenous breed counts)

**Production lesson**: this is exactly the kind of incomplete-output failure mode Session 21's UX patterns are for. The UI should:
1. Surface the partial fill as "AI dropped sustainability practices — click to regenerate that section"
2. Recommend reframing the prompt (split into N calls)
3. NOT silently show a low sustainability score that's just due to LLM output truncation

### The multi-call refactor (built, shipped, partially verified)

The engine ships `generate_farm_plan_multicall` — three sequential structured-output calls instead of one:

| Call | Schema (subset of FarmPlan) | Output size |
|---|---|---|
| **1. Core plan** | `plan_summary` + `farmer_profile_inferred` + `crops` + `livestock` + `apiary` + `risk_diversification_strategy` | ~3-4K tokens |
| **2. Sustainability + logistics** | `sustainability_practices` + `organic_transition_path` + `govt_subsidies_to_pursue` + `suppliers_to_contact` + `market_channels_to_develop` | ~2-3K tokens |
| **3. Cash flow + actions** | `year_by_year_cash_flow` (N years) + `immediate_next_steps` + `pilot_recommendation` + `disclaimers` | ~2-3K tokens |

Each call passes prior calls' output as context, so the LLM stays consistent across sections. Each fits comfortably in 4-5K output tokens (no field-dropping). Same eval pattern as Session 13 CRAG applied to structured output. **`generate_farm_plan(profile, goals, use_multicall=True)` is the default**; pass `use_multicall=False` to revert to the single big call.

### langchain-openai + `with_structured_output()` note

The OpenAI version uses plain-string `SystemMessage` with the knowledge base inlined as text. Unlike the Anthropic adapter, `langchain-openai` does not require (or support) a `cache_control` block inside `SystemMessage` content — OpenAI's automatic prefix caching applies transparently. If you see `usage.prompt_tokens_details.cached_tokens > 0` in the response, the prefix was cached successfully.

### Markdown + PDF output sizes (real)

- Markdown render: **11,675 chars / 148 lines**
- PDF render: **8,809 bytes** (`fpdf2`, no images, structured tables)
- Both produced in <1 second after the plan is in memory

### Saved plan path

`labs/farm_plans/sample_suryapet/plan_adf3782f.json` — committed copy at `labs/farm_plans/sample_plan_suryapet.json` for reference.

> *Live output varies per run as the LLM rebalances the plan. The shape (variety-level granularity, specific subsidies, real supplier names, confidence per crop) is consistent because the schema + knowledge base enforce it.*

---

## Production patterns

### When to embed knowledge vs RAG

This session embeds the entire 7K-token knowledge base in the system prompt. That works because:
- The base is small enough to fit
- It changes slowly (district-level facts, not daily prices)
- It's used in every call (so automatic prefix caching pays off)

**Switch to RAG when** the knowledge base grows past ~30K tokens, or when different queries need different subsets (e.g., crop-specific datasheets, weather data, mandi price feeds). RAG retrieves only the relevant chunks per query; embedded is whole-base-every-call.

The pattern transfers: Session 9 (RAG) + Session 11 (Hybrid RAG) + Session 12 (GraphRAG) are the alternatives when this approach doesn't scale.

### Engine separation pays off repeatedly

The strict UI-engine separation is a one-time architectural decision that buys you:
- Testability (pytest the engine directly, no Streamlit fixture)
- Multi-UI support (Streamlit + FastAPI today, React tomorrow, mobile next month)
- Refactor safety (changing rendering doesn't touch business logic)
- Type safety (Pydantic schemas at the boundary catch errors at validation, not deep in the call stack)

The cost: zero runtime overhead. Just discipline.

### Sustainability scoring is deterministic by design

The composite score is **NOT** computed by the LLM. It's a deterministic function of the plan structure. This means:
- Auditors can replay the score on saved plans
- Score changes only when the rubric or the plan changes
- No LLM-judge non-determinism contaminates the metric

Same pattern as Session 14 (eval) — LLM generates content, deterministic Python computes metrics.

### The retry + backoff loop is mandatory

OpenAI's API has occasional overload (429 rate-limit or 5xx errors), connection drops, and timeouts. The engine's retry loop with exponential backoff (0s, 10s, 30s, 60s between retries) handles transients without manual intervention. Production should also:
- Surface "retrying due to overload..." to the user (Session 21 UX pattern)
- Track retry rates as a metric (Session 17 observability)
- Fail open to a manual-review queue if retries exhaust

```python
from openai import RateLimitError, APIConnectionError

for attempt in range(3):
    try:
        plan = llm.with_structured_output(FarmPlan).invoke(messages)
        break
    except (RateLimitError, APIConnectionError) as e:
        if attempt == 2:
            raise
        wait = [0, 10, 30][attempt]
        time.sleep(wait)
```

### PDF generation choice — fpdf2

Picked `fpdf2` because:
- Pure Python (no system deps like cairo/pango)
- Already in `requirements.txt` from earlier sessions
- Adequate for tabular plan output (cash flow tables, crop summaries)

`weasyprint` would render markdown→HTML→PDF with prettier typography but needs cairo + pango system libraries. Tradeoff: ship simpler today, swap later if needed.

### Knowledge base hygiene

Don't commit private farmer data. The `farm_profiles/.gitignore` excludes everything except `sample_*.json`. The sample profiles use fictional farmer names + sanitized data. Real Suryapet farmer profiles stay on the farmer's (or KVK officer's) local machine.

---

## Try this

1. **Edit `sample_suryapet.json`** to add 2 acres of black cotton soil. Re-run the planner. Does it now recommend raised beds for perennials? (It should — the knowledge base says perennials on black cotton need raised beds to prevent Phytophthora.)

2. **Toggle `include_sericulture: True`**. Run a plan. The advisor should now consider mulberry sericulture as a possible income stream — but only if labor is available (sericulture is labor-intensive). Confirm the plan respects the labor constraint.

3. **Set `organic_required: True`** on the Nalgonda profile. The plan should drop any crop that's hard to grow organic (cotton, intensive vegetables) and emphasize ZBNF transition, organic-friendly crops, and the PGS-India certification path.

4. **Add a new district** (e.g., Mahbubnagar) to the knowledge base. Update the district table with rainfall + soil + market + KVK. The advisor should now produce plans for that district without code changes. This proves the knowledge-grounded pattern scales.

5. **Build a `pytest` against the engine.** Test: profile round-trip (save → load → equal), sustainability scoring on a hand-built plan (known practices → known score), PDF rendering doesn't crash on a sample plan. Engines that aren't UI-coupled are unit-testable.

6. **Wire a real mandi price API** (Agmarknet or CommodityOnline). Add a tool that fetches today's price for the recommended crop variety. The advisor can then layer "current market = ₹X/kg above/below the long-term average" on top of the static economics.

7. **Run the FastAPI stub.** `uvicorn 34_farm_planner_api:app --reload`. Hit it from `curl`:
   ```bash
   curl -s http://localhost:8000/profile | jq .
   curl -X POST http://localhost:8000/plan -H "Content-Type: application/json" \
        -d '{"profile": {...}, "goals": {...}}' | jq .crops
   ```
   Compare the output to the Streamlit UI's rendering. Same engine, two transports.

8. **Add a new mixed-farming option** — say, mushroom cultivation. Extend the `PlanningGoals.include_mushroom` flow, add a `MushroomInPlan` schema to the engine, update the knowledge base section on mushroom (oyster ₹20-30K setup, 30-day cycle, urban demand). The advisor will start integrating mushroom in plans where it fits.

---

## Mental model

> **Vertical AI = generic LLM + knowledge base + structured output. The knowledge base is the moat; the LLM is interchangeable.**

Three slogans:

1. **"The local case notebook beats the textbook."** Embed regional expertise into the system prompt; outputs become district-specific instead of generic.
2. **"Engine separation pays for itself the first time you want a new UI."** Streamlit today, React tomorrow, mobile next month — the engine doesn't care.
3. **"Deterministic scoring + LLM generation = auditable AI."** LLMs generate the content; deterministic Python computes metrics on top. Auditors and regulators can replay the scoring forever.

---

## FAQ

**Q: Why Streamlit when the lesson says it's a "future migration to FastAPI"?**
Streamlit gets you a usable UI in ~600 LoC of form code. FastAPI + React would be 5x the code for the same product. The architecture (engine separation) means you can start with Streamlit, validate the product, then migrate the UI without rewriting business logic. Most production AI features should start this way.

**Q: Does the LLM hallucinate variety names or supplier contacts?**
The knowledge base explicitly lists varieties (Thailand Lemon, Fuerte avocado, Bhagwa pomegranate...) and suppliers (SKLTSHU, Deccan Exotics, Indo Israel Avocado). The system prompt instructs the LLM to use these — not invent. In practice you'll see occasional drift; the disclaimer + KVK escalation note is the safety net.

**Q: How does this differ from Session 12 (GraphRAG)?**
GraphRAG retrieves a subgraph at query time based on entities in the query. This session embeds the *whole* knowledge base every call. The trade-off: GraphRAG scales to larger knowledge bases; embedding is simpler and cheaper for small (≤30K token) bases. For ~7K tokens of regional farm knowledge, embedding wins.

**Q: Why three sample profiles instead of one?**
Each district has different soil + climate + market structure. A planner that works for Suryapet but fails on Jangaon's black cotton soil isn't generalizable. Three profiles stress-test the advisor across the dominant variations in the region.

**Q: How big can the schema get before the LLM starts hallucinating fields?**
At this schema (CropInPlan has ~20 fields, FarmPlan has nested CropInPlan + LivestockInPlan + ApiaryInPlan + ...), max_tokens=8192 and timeout=240s are needed. Larger schemas push past gpt-4o's effective context for structured output. Production move: split into multiple calls (one for crops, one for cash flow, one for sustainability) and stitch together. Same pattern as multi-step agents (Session 3 / Session 13).

**Q: Why timeout=240 and max_tokens=8192?**
The full FarmPlan output is ~3K-5K output tokens (60+ fields total, including nested lists). At gpt-4o's generation speed (~50-100 tokens/sec for structured output), that's 30-90 seconds. The 240s timeout gives headroom for network jitter + OpenAI load. max_tokens=8192 prevents the response from being truncated mid-generation.

**Q: How do I add a new crop to the knowledge base?**
Edit `agritech/telangana_knowledge_base.md`. Add a section under the right category (perennial / annual / exotic / mixed farming). Include: varieties, time to bearing, ₹/acre economics, soil + climate fit, suppliers, govt schemes, disease risks, market channels. The advisor picks it up on the next planning call (the knowledge base is reloaded each call; not import-time cached). No code changes needed.

**Q: Can the advisor recommend crops outside the knowledge base?**
Yes, the LLM can draw on training knowledge for crops not explicitly in the base. But confidence will be lower (the calibration guide in the KB says experimental crops get <0.65 confidence). The UI surfaces confidence, so users see when the advisor is reaching beyond authoritative knowledge.

**Q: What about offline operation?**
The advisor needs the OpenAI API to generate plans. The UI is local, the JSON state is local, but the LLM call is remote. For truly offline operation, you'd need a local LLM (llama.cpp + Qwen-32B or similar) — quality will drop but it works. Mention as a future extension; Session 24 (vernacular bot) revisits offline patterns.

**Q: How accurate are the ₹ projections?**
Calibrated to public market intelligence circa 2026 (the lemon report + avocado guide from the knowledge base). Ranges are wide intentionally (₹2-4 lakh, not ₹2.347 lakh) because real outcomes vary 30-50% depending on management quality + weather + market. The advisor returns ranges; users (and KVK officers) calibrate based on local context.

**Q: How does this scale to other states / regions?**
Build a knowledge base per region. Replace `agritech/telangana_knowledge_base.md` with `agritech/maharashtra_knowledge_base.md` (or whichever region) and the advisor immediately works there. The engine is region-agnostic; only the system prompt content is region-specific. This is the productization path: one engine, many regional knowledge packs.

**Q: What about OpenAI API overload (429 / rate-limit errors)?**
The retry loop in `generate_farm_plan` handles 429s and `APIConnectionError` with exponential backoff (0s, 10s, 30s, 60s). If all 3 retries fail, the error propagates. Production should: (1) surface "we're temporarily overloaded" to the user, (2) queue the request for async processing, (3) increase backoff for the next user during the same overload window. Same as Session 17's circuit breaker pattern.

**Q: How does PDF generation work, and what are its limits?**
`fpdf2` is pure Python; renders text + tables + basic layout. Limits: no Unicode support without bundled TTF fonts (we sanitize ₹ → `Rs.`, → → `->`, etc. via the `_safe()` helper). For prettier output, swap to `weasyprint` (HTML→PDF) or `reportlab` — both heavier, both produce nicer PDFs. The lab's fpdf2 output is functional, not beautiful.

**Q: Is the FastAPI stub production-ready?**
No. It's a *demonstration* of the architecture. Production needs: auth (Session 18 patterns), persistence in a real DB (not JSON files), observability (Session 17), rate limiting, audit logging (Session 20), governance (Session 19). All the Track F + G patterns layer on top of the same engine.

**Q: What's the next step in Track H?**
Session 23 — Crop Diagnostic + Advisory (vision-first agent). Take a photo of a diseased crop; the agent identifies the disease and recommends treatment in vernacular language. Multi-modal (image + Telugu text), offline-tolerant (edge inference for triage), and integrates with the farm plan ("the disease you have is X; your current plan has these crops at risk").

---

## Related

- **Previous:** [33 — UX Patterns](33-ux-patterns.md) (Track G complete)
- **Next:** Session 23 — Crop Diagnostic + Advisory (vision-first agent for Telugu-speaking farmers)
- **Builds on:** [05 — Structured output](05-structured-output.md) (with_structured_output for the FarmPlan schema), [09 — RAG](09-rag.md) (the knowledge-grounding alternative), [14 — Multi-agent + LTM](14-multi-agent-ltm.md) (saved profiles + plans = memory), [17 — Deploy + Observability](28-production-deploy.md) (FastAPI + uvicorn pattern), [20 — Governance](32-governance.md) (confidence scoring per recommendation), [21 — UX Patterns](33-ux-patterns.md) (disclaimers, escalation to KVK, trust calibration)
- **Track H status:** ▶ 1/3 complete. Next: Crop Diagnostic (vision) → Vernacular Bot (WhatsApp + Telugu).
