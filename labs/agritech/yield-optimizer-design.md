# Crop Yield Optimizer — design doc (plan mode, not yet built)

> Companion to the Farm Planner (`34_farm_planner_*.py`). Farm Planner produces a **multi-crop portfolio** for a farm. This Yield Optimizer goes deep on **one crop on a specific patch** — variety, agronomy, IPM, harvest, economics, devil's-advocate critique, all tuned to maximize yield.

**Status**: design only. No code written. Authoring complete; ready for build approval.

---

## Two tools, complementary

| Tool | Question it answers | Output |
|---|---|---|
| **Farm Planner** (existing) | "What should I grow on my 5 acres over 10 years?" | Multi-crop portfolio + cash flow + risk diversification |
| **Yield Optimizer** (this doc) | "How do I get the best possible yield from my 1 acre of Thailand Lemon?" | Deep playbook for one crop + one patch |

Both share the farmer profile + Telangana knowledge base. Different focus per tool.

---

## Crop_type discriminator (6 types, 6 priority crops)

Each crop type activates specific sub-schemas + deactivates irrelevant ones:

```python
crop_type: Literal[
    "annual_grain",       # paddy, corn
    "annual_fiber",       # cotton
    "perennial_fruit",    # mango, lemon, avocado
    "perennial_timber",   # eucalyptus
    "perennial_oilseed",  # palm oil
    "annual_oilseed",     # groundnut, sesame (future)
]
```

### Sub-schemas activated per crop_type

| Sub-schema | Annual grain | Annual fiber | Perennial fruit | Perennial timber | Perennial oilseed |
|---|---|---|---|---|---|
| `water_regime` (SRI/DSR/AWD/drip) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `nitrogen_split_protocol` | ✓ | ✓ | ✓ | – | ✓ |
| `pest_calendar_with_thresholds` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `fall_armyworm_protocol` (corn-specific) | ✓ (corn only) | – | – | – | – |
| `refuge_strategy` (Bt cotton) | – | ✓ | – | – | – |
| `paclobutrazol_protocol` (mango) | – | – | ✓ (fruit only) | – | – |
| `off_season_strategy` (premium pricing) | – | – | ✓ | – | – |
| `bee_pollination_strategy` | – | – | ✓ | – | – |
| `weevil_pollination_health` (palm) | – | – | – | – | ✓ |
| `clone_selection` (replaces variety) | – | – | – | ✓ | ✓ |
| `coppice_strategy` (multi-rotation) | – | – | – | ✓ | – |
| `rotation_cycle_years` | – | – | – | ✓ | – |
| `ganoderma_prevention_protocol` | – | – | – | – | ✓ |
| `buyback_contract_strategy` | – | – | – | – | ✓ |
| `decadal_cash_flow` (25-30 year horizon) | – | – | – | – | ✓ |
| `wildlife_deterrent_plan` | ✓ (corn especially) | – | ✓ (lemon, mango young) | ✓ (initial planting) | ✓ (first 3 years) |
| `carbon_credit_potential` | – | – | – | ✓ | – (debated) |

---

## Per-crop review highlights

### 1. Paddy

- **In KB**: BPT 5204 Sona Masuri + Telangana Sona. High-level only.
- **Yield baseline**: 4-5 t/ha typical; 7-8 t/ha best.
- **Key levers schema must surface**:
  - `water_regime` as primary decision (SRI / DSR / AWD / continuous flood)
  - Nitrogen splits (basal → tillering → panicle initiation → booting)
  - Young seedling transplanting (8-12 days for tiller-rich plants)
  - BPH + blast + sheath bight IPM
  - Drainage discipline at maturity
- **KB additions**: SRI/DSR/AWD protocols, N split schedules per variety, BPH thresholds (≥10/hill), blast/sheath blight sprays.

### 2. Mango

- **In KB**: Banganapalli, Himayat at portfolio level. Light on agronomy.
- **Yield baseline**: 6-10 t/acre alternate-bearing; 12-15 with PBZ + good pruning.
- **Key levers schema must surface**:
  - `paclobutrazol_protocol` — fixes alternate-year bearing
  - `off_season_strategy` — 5× pricing on off-season fruit
  - Pruning by age cohort (formative / center-opening / rejuvenation)
  - Bee placement (25-40% pollination boost)
  - Mealybug + thrips + fruit fly + hopper IPM
  - Anthracnose + powdery mildew at flowering
- **KB additions**: PBZ dosage per tree age, off-season pruning timing, pheromone trap protocols, bagging for fruit fly.

### 3. Corn (Maize)

- **In KB**: passing mention only.
- **Yield baseline**: 25-30 q/acre commercial; 40-50 q/acre best hybrid.
- **Key levers schema must surface**:
  - **Fall armyworm protocol** (Cat-5 issue since 2018) — ICAR monitoring + neem + Bt sprays + intercrop pulse
  - `wildlife_deterrent_plan` elevated to primary section (monkey + wild boar can destroy 30-60%)
  - Hybrid vs OPV decision (NK-6240, DKC-9081 dominant hybrids)
  - Stem borer at vegetative
  - N-hungry: basal → knee-high → tasseling splits
- **KB additions**: fall armyworm threshold + spray windows, hybrid catalog AP/Telangana, wildlife deterrent options.

### 4. Cotton

- **In KB**: Bt cotton NHH 44 / Ankur 651. Price volatility noted.
- **Yield baseline**: 8-12 q/acre seed cotton; 18-20 q/acre with drip + HDPS.
- **Key levers schema must surface**:
  - `refuge_strategy` — pink bollworm Bt resistance management (now mandatory in 2026)
  - HDPS (High-Density Planting System) — 15-30% yield boost
  - Drip fertigation — biggest single lever for irrigated cotton
  - Pink bollworm + bollworm + whitefly + thrips IPM
  - Defoliation + multi-pick harvest timing
- **KB additions**: refuge crop specifics (5-10% non-Bt cotton border), HDPS spacing (60-70cm row × 10-15cm plant), pink bollworm resistance management.

### 5. Eucalyptus (NEW — not in current KB)

- **In KB**: passing windbreak mention; NO real coverage.
- **Yield baseline**: 100-150 tons/acre over 5-year rotation = ₹2-3 lakh gross. Coppice cycles 2 and 3 yield ~80-85% and ~70% of original.
- **Key levers schema must surface**:
  - `clone_selection` (matters more than variety — 1316, 526, 411 for AP/Telangana pulp)
  - Buyer-specific contracts (ITC Bhadrachalam, JK Paper, APPM)
  - `rotation_cycle_years` (4-5 pulp / 7-8 pole / 15+ timber)
  - `coppice_strategy` (3 productive rotation cycles, total 12-15 years)
  - Gall wasp (Leptocybe invasa) — clone resistance + Quadrastichus biocontrol
  - Water consumption controversy → avoid near water tables
  - Allelopathy → intercropping limited
  - `carbon_credit_potential` — emerging revenue (~5-8 tCO2e/acre/year via Verra/NABARD pilots)
- **KB additions** (~400 lines, large gap):
  - Clone catalog with buyer-fit (ITC Bhadrachalam prefers 1316; JK Paper prefers 526)
  - Rotation economics across 3 coppice cycles
  - Gall wasp identification + clone resistance table
  - Water-table regulations per Telangana district
  - NABARD carbon credit pilot scheme details

### 6. Palm Oil (NEW — not in current KB)

- **In KB**: NOT THERE.
- **Yield baseline**: 4-6 t FFB/acre/year mature; 8-10 best. Bearing Year 3-4, peak Year 7-8, productive 25-30 years.
- **Key levers schema must surface**:
  - `buyback_contract_strategy` — 25-yr contract with one of (Patanjali, Godrej Agrovet, Ruchi Soya/Patanjali, 3F Industries). Mandi-pricing doesn't apply. Contract terms ARE the economics.
  - `weevil_pollination_health` — Elaeidobius kamerunicus introduced from Africa; pesticide misuse collapses population
  - Drip irrigation MANDATORY (~150-250 L/tree/day)
  - `ganoderma_prevention_protocol` — basal stem rot, multi-decade asset destroyer
  - Year-round bunch harvest every 10-12 days (not seasonal)
  - Rhinoceros beetle + leaf miner IPM
  - 30-year `decadal_cash_flow` (not 10-year)
- **KB additions** (~400 lines):
  - NMEO-OP scheme + ₹29,000/ha Year-1 subsidy + assistance Years 2-4
  - DxP hybrid catalog (Murugappa, ICAR-IIOPR Pedavegi)
  - Contract terms comparison across 4 buyers
  - Ganoderma early detection + soil sanitation
  - Weevil population management

---

## Schema (proposed)

### Inputs — `YieldOptimizationProfile`

```python
class YieldOptimizationProfile(BaseModel):
    farmer_id: str
    focused_acres: float
    parcel_notes: str | None              # soil pocket, slope, water distance
    focused_crop: str                     # "lemon" / "mango" / "paddy" / etc.
    focused_variety: str | None            # advisor recommends if blank
    crop_type: Literal[
        "annual_grain", "annual_fiber", "annual_oilseed",
        "perennial_fruit", "perennial_timber", "perennial_oilseed",
    ]
    current_stage: Literal["planning", "planted_y1", "planted_y2_y4", "mature_bearing"]
    existing_inputs: dict[str, str] | None  # current fertilizer/water/spacing if not greenfield
    yield_goal_pct_improvement: float | None
    yield_goal_absolute_per_acre: str | None  # "kg/acre" or "tons/acre"
    organic_required: bool
    avoid_chemical_pesticides: bool
    investment_cap_inr: int | None
    labor_cap: Literal["family_only", "seasonal", "year_round"] | None
    notes: str | None
```

### Output — `YieldOptimizationPlan` (sub-schemas activated per crop_type)

```python
class YieldOptimizationPlan(BaseModel):
    plan_id: str
    farmer_id: str
    crop_type: str
    focused_crop: str
    focused_variety: str
    focused_acres: float
    current_stage: str

    # 1. Variety + land
    variety_rationale: str
    clone_selection: CloneSelection | None        # timber + oilseed (palm)
    land_preparation: LandPrep                    # soil test, amendments, raised beds, drainage

    # 2. Geometry + water
    spacing_and_density: SpacingDensity
    water_regime: WaterRegime                     # SRI/DSR/AWD for grain; drip for fruit/timber
    irrigation_schedule: IrrigationSchedule       # by month + by growth stage

    # 3. Nutrition (per growth stage)
    nutrition_program: list[NutritionStage]
    nitrogen_split_protocol: NitrogenSplits | None  # grain, fiber, oilseed

    # 4. Crop protection
    pest_calendar: list[PestEvent]                # by month + threshold + action
    fall_armyworm_protocol: FallArmywormProtocol | None  # corn-specific
    refuge_strategy: RefugeStrategy | None        # Bt cotton-specific
    ganoderma_prevention_protocol: GanodermaProtocol | None  # palm oil-specific
    wildlife_deterrent_plan: WildlifeDeterrent | None

    # 5. Crop-stage specifics
    canopy_management: CanopyManagement | None    # perennial fruit pruning
    coppice_strategy: CoppiceStrategy | None      # eucalyptus
    paclobutrazol_protocol: PBZProtocol | None    # mango
    off_season_strategy: OffSeasonStrategy | None # mango premium pricing
    pollination_strategy: PollinationStrategy | None  # bee for fruit; weevil for palm

    # 6. Harvest + post-harvest
    harvest_and_postharvest: HarvestPlan
    buyback_contract_strategy: BuybackContract | None  # palm oil-specific

    # 7. Economics
    yield_benchmarks: list[YearlyYieldBenchmark]
    decadal_cash_flow: list[YearlyCashFlow]       # 5-30 years depending on crop_type
    production_costs: list[CostLineItem]
    carbon_credit_potential: CarbonCredit | None  # eucalyptus mainly

    # 8. Risks + levers
    risk_register: list[YieldRisk]
    optimization_levers: list[OptimizationLever]  # ranked 1-5 by impact × ease
    benchmark_comparison: BenchmarkComparison

    # 9. Confidence + disclaimers
    confidence_self: float
    confidence_meta: float
    critique: YieldCritique                       # devil's advocate
    disclaimers: list[str]
```

### Nested critical sub-schemas

```python
class WaterRegime(BaseModel):
    """For paddy / water-intensive crops — names the method explicitly."""
    primary_method: Literal[
        "continuous_flood", "AWD", "DSR", "SRI", "drip_irrigated",
        "rainfed", "weekly_irrigation",
    ]
    rationale: str
    water_savings_pct: float | None  # vs baseline method
    yield_impact_pct: float | None   # +/- vs baseline
    setup_investment_inr: str | None

class NitrogenSplits(BaseModel):
    """Split N application schedule — major lever for grain/fiber/oilseed."""
    total_n_kg_per_acre: float
    splits: list[dict]  # [{stage: "basal", pct: 25, days_after_sowing: 0}, ...]
    foliar_corrections: list[str]

class FallArmywormProtocol(BaseModel):
    """Corn-specific — Cat 5 issue since 2018 in India."""
    monitoring_protocol: str  # pheromone traps every X meters
    threshold_for_action: str  # "≥5% damaged whorls"
    organic_first_options: list[str]  # neem oil 5%, hand-removal, Bt sprays
    chemical_options_if_severe: list[str]  # last resort
    intercrop_recommendation: str  # pulse intercrop to disrupt
    expected_damage_without_intervention: str  # "30-50% yield loss"

class RefugeStrategy(BaseModel):
    """Cotton-specific — Bt resistance management is now mandatory."""
    refuge_acres: float  # 5-10% of total
    refuge_crop: str  # "non-Bt cotton border"
    rationale: str
    pheromone_traps: int
    expected_resistance_reduction: str

class PBZProtocol(BaseModel):
    """Mango — alternate-year bearing fix."""
    application_timing: str  # "September, 2 months before flush"
    dose_per_tree_g: float  # e.g., 5g/year-of-tree-age × variety multiplier
    application_method: Literal["soil_drench", "foliar_spray"]
    expected_off_season_yield_pct: float
    risks: list[str]  # over-application reduces vigor

class OffSeasonStrategy(BaseModel):
    """Mango — chase 5x off-season pricing."""
    target_off_season_window: str
    techniques: list[str]  # PBZ + pruning + nutrition timing + ethrel ripening
    expected_price_premium_pct: float
    additional_investment_inr: str

class CloneSelection(BaseModel):
    """Eucalyptus + Palm Oil — clone matters more than variety."""
    recommended_clones: list[str]  # ["1316", "526"]
    source_organization: str  # ITC Bhadrachalam, ICAR-IIOPR
    expected_yield_per_acre_per_rotation: str  # eucalyptus
    expected_yield_t_ffb_per_acre_per_year: float | None  # palm oil
    rotation_years: int | None  # eucalyptus
    productive_lifetime_years: int  # 12-15 for euc; 25-30 for palm

class CoppiceStrategy(BaseModel):
    """Eucalyptus — multi-rotation economics."""
    rotation_cycle_years: int
    coppice_cycles: int  # typical 3
    yield_per_cycle_pct: list[float]  # [100, 85, 70]
    coppice_practices: list[str]  # cut height, sprout selection
    total_productive_years: int

class BuybackContract(BaseModel):
    """Palm Oil — contracts replace mandi pricing."""
    recommended_buyer: str  # "Patanjali" / "Godrej Agrovet" / "Ruchi Soya/Patanjali" / "3F"
    contract_duration_years: int  # typically 25
    pricing_mechanism: str  # FFB price formula vs CPO/PFAD international
    advance_recovery_terms: str  # how planting advance is recovered
    rationale: str

class GanodermaProtocol(BaseModel):
    """Palm Oil — basal stem rot prevention."""
    early_detection_indicators: list[str]
    soil_sanitation_practices: list[str]
    drainage_requirements: str
    quarantine_protocol: str  # for infected trees

class YieldCritique(BaseModel):
    """Devil's advocate — honest about why yield target might not be hit."""
    why_target_is_realistic: list[str]
    why_target_might_NOT_be_realistic: list[str]
    biggest_yield_gap_driver: str
    overall_confidence: float

class OptimizationLever(BaseModel):
    lever: str
    yield_uplift_pct: float
    investment_inr: str
    payback: str
    difficulty: Literal["easy", "moderate", "hard"]
    ranked_priority: int
```

---

## LangGraph wiring

Same 5-LLM-call shape as Farm Planner, with crop-type-branched prompts inside each node:

```
START
  ↓
variety_and_land             (call 1)
  ├──→ spacing_water_nutrition  (call 2: parallel)
  └──→ protection               (call 3: parallel)
                              join↓
                       harvest_economics_risks  (call 4)
                                      ↓
                             assemble (deterministic)
                                      ↓
                           critique (call 5 — devil's advocate)
                                      ↓
                                    END
```

Each LLM node's prompt branches on `crop_type`:

- **variety_and_land** — paddy gets water_regime + N strategy emphasis; eucalyptus gets clone selection; palm oil gets clone + buyer contract intro; mango gets variety + age cohort.
- **spacing_water_nutrition** — paddy SRI/DSR/AWD spec; cotton HDPS spacing; eucalyptus clonal spacing; palm oil drip with 150-250 L/tree/day.
- **protection** — corn fall armyworm protocol mandatory; cotton refuge + Bt resistance mgmt; mango PBZ + bee placement; eucalyptus gall wasp; palm oil Ganoderma + weevil.
- **harvest_economics_risks** — paddy/corn/cotton single-cycle; mango annual; eucalyptus multi-rotation w/ coppice; palm oil decadal year-round w/ buyback contract.

---

## Knowledge base additions (~1900 lines total)

| Crop | Existing KB coverage | New section size | Priority |
|---|---|---|---|
| Paddy | 30 lines (variety + net ₹) | +250 (SRI/DSR/AWD, BPH IPM, N splits) | High |
| Mango | 40 lines (variety table + net ₹) | +250 (PBZ, alt-year, off-season, pruning) | High |
| Corn | 5 lines (passing mention) | +250 (fall armyworm protocol, hybrid catalog, wildlife) | High — fall armyworm urgent |
| Cotton | 30 lines (variety + price volatility) | +250 (refuge, HDPS, Bt resistance, drip fertigation) | High |
| Eucalyptus | 5 lines (windbreak mention) | **+400 (new — full coverage)** | High — biggest gap |
| Palm Oil | NONE | **+400 (new — full coverage)** | High — NMEO-OP active |

---

## UI changes

New top-level sidebar entry between **Generate Plan** and **View Plan**:

```
Home
Farm Profile
Goals & Constraints
Generate Plan          (existing — multi-crop)
Yield Optimizer        ← NEW (single-crop deep dive)
View Plan
Sustainability Audit
About
```

Page layout:
1. Farmer profile selector (or use current)
2. Crop type radio → drives the form
3. Focus inputs: acres + crop + variety (variety dropdown filtered by crop_type)
4. Stage selector + goal slider
5. Constraint checkboxes
6. **Optimize** button → status with per-node progress (7 nodes if you split, 5 nodes for this design)
7. Output: 9 expandable sections (variety / land / spacing+water / nutrition / IPM+canopy / pollination / harvest / economics / critique) + Download MD + Generate PDF

---

## Time estimate (6-crop scope)

| Component | Hours |
|---|---|
| Crop_type discriminator + 6 conditional sub-schemas + nested schemas | 1.0 |
| LangGraph nodes with crop-type-branched prompts | 0.75 |
| UI: crop-type-aware form fields + output rendering | 0.75 |
| KB additions for 6 crops (eucalyptus + palm oil are largest) | 2.5 |
| Smoke test (1 LLM run per crop × 6, ~5 min each) | 0.75 |
| Lesson update | 0.5 |
| **Total** | **~6.25 hours** |

Cost: ~$1.00-1.50 per full optimize run (5 LLM calls + critique). Smoke testing 6 crops at ~$1 each = ~$6.

---

## Devil's advocate on this feature itself

**Why it might work:**
- 6 crops cover ~85% of Telangana farmer use cases (cotton + paddy + corn + mango widespread; eucalyptus growing fast; palm oil NMEO-OP push 2021+)
- Each crop has well-documented agronomy in ICAR/CRIDA + crop-specific institute literature → KB research not guessing
- Crop_type abstraction generalizes — adding a 7th crop (sugarcane, banana) = KB add, not code change
- Per-stage agronomy is exactly where most LLM crop advisors are too generic; this fixes that

**Why it might NOT work:**
- **Per-region nuance** — fall armyworm severity differs Jangaon vs Adilabad; SRI adoption uneven; eucalyptus water regulation per district varies. KB defaults will miss local truth in some pockets.
- **Yield projections sound precise but are estimates** — "+20% with HDPS" is a real published number, but variance is 5-40%. Users may over-trust.
- **Fast staleness** — fall armyworm protocols evolve year-on-year; pink bollworm Bt resistance updates; palm oil contract terms change. KB needs annual refresh discipline.
- **IPM liability** — wrong pesticide × wrong dose × wrong stage = wasted ₹ + soil damage + possible regulatory exposure. **Every chemical recommendation must lead with non-chemical IPM alternative + KVK-validate disclaimer.**
- **Behavioral gap** — recommending Bt cotton refuge strategy is one thing; getting farmers to plant non-Bt borders is another. Compliance is the bottleneck, not advice. The advisor can recommend; it can't enforce.
- **Buyback contract risk** (palm oil) — 25-year lock-in to one buyer. If we recommend the wrong buyer or terms change unfavorably, farmer is stuck. Conservative framing required.
- **Eucalyptus water regulation** — some panchayats restrict it; some districts ban planting near water tables. Need a "check local regulations" disclaimer prominent.

**Biggest risks (ranked):**
1. **IPM chemical recommendation liability** (highest)
2. **Palm oil buyback contract lock-in** — wrong buyer = 25-year suboptimal
3. **Yield over-projection** — "+30% with proper agronomy" can become a promise
4. **Eucalyptus + water regulation in dry districts**
5. **Knowledge base staleness** — fall armyworm protocol obsolete in 18 months

**Mitigations baked into design:**
- Every chemical IPM recommendation must list a non-chemical alternative FIRST
- Buyback contract recommendation must list all 4 major buyers with terms comparison
- Yield benchmarks must show ranges (5-40%), not point estimates
- "Validate with local KVK officer" disclaimer mandatory on every plan
- KB version-tagged with last-reviewed date

---

## Decisions for build (open)

1. **Scope confirm** — full 6-crop coverage as designed, or trim to 3 (paddy + cotton + mango first; eucalyptus + corn + palm oil in v2)?
2. **First crop to validate on** — picking paddy for the first end-to-end smoke (well-studied, broad applicability). Or different?
3. **UI placement** — new sidebar page (designed above), or sub-mode under Generate Plan with toggle?
4. **KB live updates** — bake in a "knowledge base last-reviewed" date string per crop, prominent in UI?
5. **Go for full build (~6.25 hours), MVP (~3 hours, 3 crops), or hold?**

---

## What this design does NOT cover

- Per-tree-level recommendations (needs sensor data, drone imagery, soil mapping — Session 23+ territory)
- Live yield monitoring with IoT (out of scope)
- Drone / satellite imagery analysis (Session 23 vision-first agent)
- A/B yield experiment framework (separate lab)
- Per-farmer historical yield tracking (would need a yield log feature)
- Multi-crop yield optimization (use Farm Planner for that)
- Carbon credit revenue *modeling* with specific ₹ values (regulatory uncertainty; surface option only)

---

## File location

This design doc lives at `labs/agritech/yield-optimizer-design.md`. Committed to the repo so it survives between sessions and can be opened by future-Sree or shared with the team.

When build approval comes, the build phases will be:
1. Schemas + crop_type discriminator
2. LangGraph nodes with branched prompts
3. KB additions (largest chunk — 1900 lines across 6 crops)
4. UI page
5. Smoke test per crop
6. Lesson update

Status: **plan only, no code written. Awaiting build approval.**
