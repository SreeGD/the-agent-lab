"""Yield Optimizer engine — single-crop deep-dive advisor.

Companion to the Farm Planner. Where the Farm Planner produces a multi-crop
portfolio for a farm, this tool goes deep on one crop on one patch.

Public API:
    generate_yield_plan(profile) -> YieldOptimizationPlan
    stream_yield_plan(profile) -> generator of per-node events
"""

from __future__ import annotations

import operator
import time
from pathlib import Path
from typing import Annotated as _Annotated
from typing import Generator, Literal
from uuid import uuid4

from fpdf import FPDF, FontFace
from fpdf.enums import TableBordersLayout, TableCellFillMode

import anthropic as _anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")  # labs/.env

ANSWER_MODEL = "claude-sonnet-4-6"
KNOWLEDGE_BASE_PATH = HERE / "telangana_knowledge_base.md"

_raw_anthropic_client = _anthropic.Anthropic()


# =====================================================================
# Input schema
# =====================================================================


class YieldOptimizationProfile(BaseModel):
    farmer_id: str
    focused_acres: float
    parcel_notes: str | None = None              # soil pocket, slope, water distance
    focused_crop: str                            # "lemon" / "mango" / "paddy" / etc.
    focused_variety: str | None = None           # advisor recommends if blank
    crop_type: Literal[
        "annual_grain", "annual_fiber", "annual_oilseed",
        "perennial_fruit", "perennial_timber", "perennial_oilseed",
    ]
    current_stage: Literal["planning", "planted_y1", "planted_y2_y4", "mature_bearing"]
    existing_inputs: dict[str, str] | None = None  # current fertilizer/water/spacing if not greenfield
    yield_goal_pct_improvement: float | None = None
    yield_goal_absolute_per_acre: str | None = None  # "kg/acre" or "tons/acre"
    organic_required: bool = False
    avoid_chemical_pesticides: bool = False
    investment_cap_inr: int | None = None
    labor_cap: Literal["family_only", "seasonal", "year_round"] | None = None
    notes: str | None = None


# =====================================================================
# Sub-schemas
# =====================================================================


class WaterRegime(BaseModel):
    primary_method: Literal[
        "continuous_flood", "AWD", "DSR", "SRI", "drip_irrigated",
        "rainfed", "weekly_irrigation",
    ]
    rationale: str
    water_savings_pct: float | None = None
    yield_impact_pct: float | None = None
    setup_investment_inr: str | None = None


class NitrogenSplitEntry(BaseModel):
    stage: str = Field(description="Growth stage, e.g. 'basal', 'tillering', 'panicle_initiation'.")
    pct: float = Field(description="Percentage of total N applied at this stage.")
    days_after_sowing: int = Field(description="Days after sowing / transplanting.")


class NitrogenSplits(BaseModel):
    total_n_kg_per_acre: float
    splits: list[NitrogenSplitEntry]
    foliar_corrections: list[str]


class FallArmywormProtocol(BaseModel):
    monitoring_protocol: str
    threshold_for_action: str
    organic_first_options: list[str]
    chemical_options_if_severe: list[str]
    intercrop_recommendation: str
    expected_damage_without_intervention: str


class RefugeStrategy(BaseModel):
    refuge_acres: float
    refuge_crop: str
    rationale: str
    pheromone_traps: int
    expected_resistance_reduction: str


class PBZProtocol(BaseModel):
    application_timing: str
    dose_per_tree_g: float
    application_method: Literal["soil_drench", "foliar_spray"]
    expected_off_season_yield_pct: float
    risks: list[str]


class OffSeasonStrategy(BaseModel):
    target_off_season_window: str
    techniques: list[str]
    expected_price_premium_pct: float
    additional_investment_inr: str


class CloneSelection(BaseModel):
    recommended_clones: list[str]
    source_organization: str
    expected_yield_per_acre_per_rotation: str
    expected_yield_t_ffb_per_acre_per_year: float | None = None
    rotation_years: int | None = None
    productive_lifetime_years: int


class CoppiceStrategy(BaseModel):
    rotation_cycle_years: int
    coppice_cycles: int
    yield_per_cycle_pct: list[float]
    coppice_practices: list[str]
    total_productive_years: int


class BuybackContract(BaseModel):
    recommended_buyer: str
    contract_duration_years: int
    pricing_mechanism: str
    advance_recovery_terms: str
    rationale: str


class GanodermaProtocol(BaseModel):
    early_detection_indicators: list[str]
    soil_sanitation_practices: list[str]
    drainage_requirements: str
    quarantine_protocol: str


class YieldCritique(BaseModel):
    why_target_is_realistic: list[str] = Field(description="3-5 concrete reasons the yield target is achievable given this farm's conditions.")
    why_target_might_NOT_be_realistic: list[str] = Field(description="3-5 honest reasons the target may not be hit (weather, skill, market, pest risk).")
    biggest_yield_gap_driver: str = Field(description="Single biggest factor limiting yield on this specific parcel.")
    overall_confidence: float = Field(ge=0.0, le=1.0, description="Calibrated confidence the plan meets the stated yield target, 0-1.")


class OptimizationLever(BaseModel):
    lever: str
    yield_uplift_pct: float
    investment_inr: str
    payback: str
    difficulty: Literal["easy", "moderate", "hard"]
    ranked_priority: int


# =====================================================================
# Supporting schemas
# =====================================================================


class LandPrep(BaseModel):
    soil_test_needed: bool = True
    amendments: list[str] = Field(default_factory=list)
    bed_type: str | None = None
    drainage_notes: str | None = None


class SpacingDensity(BaseModel):
    row_spacing_m: float
    plant_spacing_m: float
    plants_per_acre: int
    geometry_notes: str | None = None


class MonthlyIrrigationEntry(BaseModel):
    month: str = Field(description="Calendar month, e.g. 'June', 'July'.")
    depth_mm: float = Field(description="Irrigation depth in mm per application.")
    frequency: str = Field(description="How often, e.g. 'every 7 days', 'twice weekly'.")


class IrrigationSchedule(BaseModel):
    monthly_schedule: list[MonthlyIrrigationEntry]
    growth_stage_overrides: list[str] = Field(description="Special instructions by crop stage, e.g. 'reduce at flowering'.")


class NutritionStage(BaseModel):
    stage_name: str
    dap_range: str  # e.g. "0-15 DAP" or "tillering"
    fertilizers: list[str]
    notes: str | None = None


class PestEvent(BaseModel):
    month: str
    pest_name: str
    threshold: str
    organic_action: str
    chemical_action: str | None = None


class CanopyManagement(BaseModel):
    pruning_type: str
    timing: str
    technique: str
    expected_yield_impact_pct: float | None = None


class PollinationStrategy(BaseModel):
    method: str
    details: str
    expected_yield_boost_pct: float | None = None


class HarvestPlan(BaseModel):
    maturity_indicators: list[str]
    harvest_method: str
    post_harvest_steps: list[str]
    storage_notes: str | None = None


class YearlyYieldBenchmark(BaseModel):
    year: int
    low_yield: float
    high_yield: float
    unit: str  # "kg/acre" or "tons/acre"
    notes: str | None = None


class YearlyCashFlow(BaseModel):
    year: int
    investment_inr: float
    revenue_inr: float
    net_inr: float
    notes: str | None = None


class CostLineItem(BaseModel):
    item: str
    annual_cost_inr: float
    notes: str | None = None


class BenchmarkComparison(BaseModel):
    district_average: float
    state_best: float
    target: float
    unit: str
    gap_analysis: str


class YieldRisk(BaseModel):
    risk: str
    probability: Literal["low", "medium", "high"]
    impact: str
    mitigation: str


class WildlifeDeterrent(BaseModel):
    threats: list[str]
    deterrent_methods: list[str]
    estimated_loss_without_pct: float


class CarbonCredit(BaseModel):
    scheme_name: str
    estimated_tco2e_per_acre_per_year: float
    revenue_inr_per_acre_per_year: float
    certification_body: str
    caveats: list[str]


# =====================================================================
# Output schema
# =====================================================================


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
    clone_selection: CloneSelection | None = None
    land_preparation: LandPrep

    # 2. Geometry + water
    spacing_and_density: SpacingDensity
    water_regime: WaterRegime
    irrigation_schedule: IrrigationSchedule

    # 3. Nutrition
    nutrition_program: list[NutritionStage]
    nitrogen_split_protocol: NitrogenSplits | None = None

    # 4. Crop protection
    pest_calendar: list[PestEvent]
    fall_armyworm_protocol: FallArmywormProtocol | None = None
    refuge_strategy: RefugeStrategy | None = None
    ganoderma_prevention_protocol: GanodermaProtocol | None = None
    wildlife_deterrent_plan: WildlifeDeterrent | None = None

    # 5. Crop-stage specifics
    canopy_management: CanopyManagement | None = None
    coppice_strategy: CoppiceStrategy | None = None
    paclobutrazol_protocol: PBZProtocol | None = None
    off_season_strategy: OffSeasonStrategy | None = None
    pollination_strategy: PollinationStrategy | None = None

    # 6. Harvest + post-harvest
    harvest_and_postharvest: HarvestPlan
    buyback_contract_strategy: BuybackContract | None = None

    # 7. Economics
    yield_benchmarks: list[YearlyYieldBenchmark]
    decadal_cash_flow: list[YearlyCashFlow]
    production_costs: list[CostLineItem]
    carbon_credit_potential: CarbonCredit | None = None

    # 8. Risks + levers
    risk_register: list[YieldRisk]
    optimization_levers: list[OptimizationLever]
    benchmark_comparison: BenchmarkComparison

    # 9. Confidence + disclaimers
    confidence_self: float = Field(ge=0.0, le=1.0, description="Calibrated confidence in this plan's recommendations, 0-1.")
    confidence_meta: float = Field(ge=0.0, le=1.0, description="Meta-confidence: confidence in the confidence estimate, 0-1.")
    critique: YieldCritique
    disclaimers: list[str]


# =====================================================================
# Graph state
# =====================================================================


class YieldOptimizerGraphState(TypedDict, total=False):
    profile: YieldOptimizationProfile
    variety_land: dict          # output of node 1
    spacing_water_nutrition: dict  # output of node 2
    protection: dict            # output of node 3
    harvest_economics: dict     # output of node 4
    plan: YieldOptimizationPlan
    critique: YieldCritique


# =====================================================================
# Intermediate output schemas
# =====================================================================


class VarietyLandOutput(BaseModel):
    focused_variety: str
    variety_rationale: str
    clone_selection: CloneSelection | None = None
    land_preparation: LandPrep


class SpacingWaterNutritionOutput(BaseModel):
    spacing_and_density: SpacingDensity
    water_regime: WaterRegime
    irrigation_schedule: IrrigationSchedule
    nutrition_program: list[NutritionStage]
    nitrogen_split_protocol: NitrogenSplits | None = None


class ProtectionOutput(BaseModel):
    pest_calendar: list[PestEvent]
    fall_armyworm_protocol: FallArmywormProtocol | None = None
    refuge_strategy: RefugeStrategy | None = None
    ganoderma_prevention_protocol: GanodermaProtocol | None = None
    wildlife_deterrent_plan: WildlifeDeterrent | None = None
    canopy_management: CanopyManagement | None = None
    paclobutrazol_protocol: PBZProtocol | None = None
    pollination_strategy: PollinationStrategy | None = None


class HarvestEconomicsOutput(BaseModel):
    harvest_and_postharvest: HarvestPlan
    buyback_contract_strategy: BuybackContract | None = None
    yield_benchmarks: list[YearlyYieldBenchmark]
    decadal_cash_flow: list[YearlyCashFlow]
    production_costs: list[CostLineItem]
    carbon_credit_potential: CarbonCredit | None = None
    risk_register: list[YieldRisk]
    optimization_levers: list[OptimizationLever]
    benchmark_comparison: BenchmarkComparison
    off_season_strategy: OffSeasonStrategy | None = None
    coppice_strategy: CoppiceStrategy | None = None


# =====================================================================
# System prompt + caching helpers
# =====================================================================

SYSTEM_PROMPT_TEMPLATE = """You are a senior crop-yield optimization advisor for the
Suryapet / Jangaon / Nalgonda region of Telangana, India.

You have authoritative knowledge of:
- Telangana climate, soil types, and water availability by district
- Variety-level crop economics (paddy, cotton, lemon, mango, oil palm, eucalyptus, maize, etc.)
- Best-practice agronomy: SRI/DSR/AWD for paddy, HDPS for cotton, drip scheduling
- Govt schemes (NMEO-OP, ITC/JK Paper buyback, MIDH, PM-KISAN, carbon credit schemes)
- IPM protocols including fall armyworm, Ganoderma, bollworm, fruit fly
- Fertilizer scheduling, micronutrient corrections, biostimulants

Embedded knowledge base below — treat as authoritative for variety names,
economics, suppliers, schemes.

Style:
- Opinionated. Pick ONE concrete recommendation per question. No hedging.
- Specific numbers (₹ ranges, kg yields, breakeven years), not platitudes.
- Variety-level granularity. Say "BPT 5204" not "paddy variety".
- Honest about confidence.

KNOWLEDGE BASE (authoritative, do not contradict):
==================================================
{knowledge_base}
==================================================
"""


def _load_knowledge_base() -> str:
    return KNOWLEDGE_BASE_PATH.read_text()


def _build_system_blocks_for_caching() -> list[dict]:
    """Build the system prompt as a content-block list with cache_control.
    First call writes the cache; subsequent calls within ~5 min read it cheaply."""
    knowledge = _load_knowledge_base()
    text = SYSTEM_PROMPT_TEMPLATE.format(knowledge_base=knowledge)
    return [{
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }]


def _call_anthropic_structured(
    schema_model: type[BaseModel],
    user_prompt: str,
    label: str = "call",
    model: str = ANSWER_MODEL,
    max_tokens: int = 4096,
    timeout: int = 240,
    max_retries: int = 3,
) -> BaseModel:
    """Call Anthropic API with structured output via tool-use + cache_control.

    Returns a validated instance of `schema_model`. Retries on transient
    connection errors / overload with exponential backoff.
    """
    system_blocks = _build_system_blocks_for_caching()
    tool_def = {
        "name": schema_model.__name__,
        "description": f"Emit a {schema_model.__name__} matching the provided schema.",
        "input_schema": schema_model.model_json_schema(),
    }

    last_err: Exception | None = None
    backoff = [0, 10, 30, 60, 90]
    for attempt in range(max_retries):
        if attempt > 0:
            wait = backoff[min(attempt, len(backoff) - 1)]
            print(f"[anthropic] {label}: backing off {wait}s before retry {attempt + 1}...")
            time.sleep(wait)
        # Fresh client per call avoids stale keep-alive connections from the shared pool
        # (parallel fan-out nodes exhaust the pool; subsequent fan-in node hits closed connections)
        client = _anthropic.Anthropic()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                timeout=timeout,
                system=system_blocks,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[tool_def],
                tool_choice={"type": "tool", "name": schema_model.__name__},
            )
            # Log cache usage for observability
            usage = response.usage
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
            print(f"[anthropic] {label}: input={usage.input_tokens} "
                  f"cache_read={cache_read} cache_write={cache_write} "
                  f"output={usage.output_tokens}")

            # Extract tool_use block
            for block in response.content:
                if block.type == "tool_use" and block.name == schema_model.__name__:
                    return schema_model.model_validate(block.input)
            raise RuntimeError(
                f"No {schema_model.__name__} tool_use in response. "
                f"Got blocks: {[b.type for b in response.content]}"
            )
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"[anthropic] {label}: {type(e).__name__} on attempt "
                      f"{attempt + 1} — will retry...")
    raise last_err


# =====================================================================
# LangGraph nodes
# =====================================================================

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False


def _profile_summary(profile: YieldOptimizationProfile) -> str:
    """Render profile as a concise text block for prompts."""
    lines = [
        f"Farmer ID: {profile.farmer_id}",
        f"Crop: {profile.focused_crop} ({profile.crop_type})",
        f"Acres: {profile.focused_acres}",
        f"Current stage: {profile.current_stage}",
    ]
    if profile.focused_variety:
        lines.append(f"Preferred variety: {profile.focused_variety}")
    if profile.parcel_notes:
        lines.append(f"Parcel notes: {profile.parcel_notes}")
    if profile.yield_goal_pct_improvement:
        lines.append(f"Yield improvement goal: {profile.yield_goal_pct_improvement}%")
    if profile.yield_goal_absolute_per_acre:
        lines.append(f"Absolute yield goal: {profile.yield_goal_absolute_per_acre}")
    if profile.organic_required:
        lines.append("Organic: required")
    if profile.avoid_chemical_pesticides:
        lines.append("Chemical pesticides: avoid")
    if profile.investment_cap_inr:
        lines.append(f"Investment cap: ₹{profile.investment_cap_inr:,}")
    if profile.labor_cap:
        lines.append(f"Labor cap: {profile.labor_cap}")
    if profile.existing_inputs:
        lines.append(f"Existing inputs: {profile.existing_inputs}")
    if profile.notes:
        lines.append(f"Notes: {profile.notes}")
    return "\n".join(lines)


def _node_variety_and_land(state: YieldOptimizerGraphState) -> dict:
    """Node 1: Recommend variety and land preparation."""
    profile = state["profile"]
    p = _profile_summary(profile)
    ct = profile.crop_type

    if ct == "annual_grain":
        crop_guidance = """
PADDY-SPECIFIC GUIDANCE:
- Recommend best variety: BPT 5204 (Samba Mahsuri), Telangana Sona, MTU 1010, or RNR 15048 based on season and water availability.
- Choose water regime: SRI (system of rice intensification) for water-saving + yield boost, DSR (direct seeded rice) for labor saving, or AWD (alternate wetting drying) for water efficiency.
- For black cotton soil: raised bed system preferred for drainage.
- Variety selection: consider season (Kharif vs Rabi), market preference (fine vs medium grain), and water availability.
"""
    elif ct == "annual_fiber":
        crop_guidance = """
COTTON-SPECIFIC GUIDANCE:
- Recommend Bt hybrid: NHH 44, Ankur 651, MRC 7017, or Brahma based on soil type.
- HDPS (high-density plant stand): 10,000-15,000 plants/acre for early variety, 6,000-8,000 for full-season hybrid.
- Black cotton soil: manage bed for drainage, raised beds in waterlogging areas.
- Variety maturity: 150-170 days for full-season, 100-120 days for early hybrid.
"""
    elif ct == "perennial_fruit":
        crop_guidance = """
FRUIT CROP GUIDANCE:
- Mango: Banganapalli (export-grade), Himayat (local premium), Kesar (off-season).
- Lemon: Thailand Lemon (seedless, high juice content) preferred over Kagzi Lime.
- Source only grafted plants from certified nurseries (KVK, IIHR Bengaluru, local certified).
- Age cohort planning: year 1-3 is establishment, commercial yield from year 4+.
- Spacing: mango 10x10m (40 trees/acre), lemon 5x4m (200 trees/acre).
"""
    elif ct == "perennial_timber":
        crop_guidance = """
EUCALYPTUS-SPECIFIC GUIDANCE:
- Clone selection critical: ITC clone 1316, 526, or 411 for best pulpwood yield.
- ITC Paper / JK Paper buyback: confirm availability in your district before planting.
- Caution on water table: eucalyptus is a heavy water user, avoid if water table is critical.
- Spacing: 2x2m (1000 trees/acre) for pulpwood, 3x2m for mixed timber.
- First harvest at 4-5 years; coppice for 2-3 additional rotations.
"""
    elif ct == "perennial_oilseed":
        crop_guidance = """
OIL PALM GUIDANCE:
- DxP hybrid mandatory: Murugappa (TNP-01), ICAR-IIOPR Pedavegi DxP, or MPOB sourced.
- NMEO-OP subsidy: ₹29,000/ha planting subsidy available — must use approved variety.
- Drip irrigation mandatory: 150-250 litres/tree/day depending on age and season.
- Planting density: 9x9m or 9x7.8m triangular (56-66 palms/acre).
- Productive life: 25+ years. Buyback contracts available with Ruchi Soya, Godrej Agrovet.
"""
    else:
        crop_guidance = ""

    prompt = f"""
FARMER PROFILE:
{p}

{crop_guidance}

Recommend the best variety / clone / hybrid for this farmer's specific situation.
Consider: crop type, season, soil notes from parcel_notes, water availability, market linkage.
Provide land preparation details including soil amendments, bed type, drainage.

Return a VarietyLandOutput with:
- focused_variety: the single best recommended variety name (specific, not generic)
- variety_rationale: 2-3 sentences explaining why this variety for this farm
- clone_selection: fill only for eucalyptus/palm oil (clone details, source, yields)
- land_preparation: soil test, amendments, bed type, drainage
"""

    result: VarietyLandOutput = _call_anthropic_structured(
        VarietyLandOutput,
        prompt,
        label="variety_and_land",
        max_tokens=4096,
        timeout=240,
    )
    return {"variety_land": result.model_dump()}


def _node_spacing_water_nutrition(state: YieldOptimizerGraphState) -> dict:
    """Node 2: Spacing, water regime, and nutrition program."""
    profile = state["profile"]
    variety_land = state.get("variety_land", {})
    p = _profile_summary(profile)
    ct = profile.crop_type
    chosen_variety = variety_land.get("focused_variety", profile.focused_crop)

    if ct == "annual_grain":
        water_guidance = """
PADDY WATER REGIME:
- SRI: transplant at 8-12 days, single seedling, 25x25cm spacing, AWD (alternate wetting/drying),
  target 20-30% water saving vs flood, yield boost 10-20%.
- DSR: direct seeding at 20-22kg seed/acre, line sowing 20cm rows, reduce puddling.
- AWD: flood to 5cm, allow to drain to 15cm below ground, re-flood — 25-30% water saving.
- Choose based on water source (canal vs borewell) and labor availability.
"""
        spacing_guidance = "SRI: 25x25cm (64,000 plants/acre). DSR: 20cm rows. Conventional transplant: 20x15cm."
    elif ct == "annual_fiber":
        water_guidance = """
COTTON WATER REGIME:
- Drip preferred: 4L/plant/day peak, reduce at boll opening.
- Furrow irrigation if drip unavailable: irrigate alternate furrows.
- Critical stages: flowering and boll formation — do not stress.
"""
        spacing_guidance = "HDPS: 60x10cm (27,000 plants/acre). Standard: 90x60cm (7,400 plants/acre)."
    elif ct == "perennial_oilseed":
        water_guidance = """
OIL PALM DRIP SCHEDULE:
- Year 1: 50 litres/palm/day
- Year 2: 100 litres/palm/day
- Year 3+: 150-250 litres/palm/day (peak in summer April-June)
- Reduce 20% post-monsoon (Oct-Dec)
- Drip lateral: 2 drippers per palm at 50cm from trunk
"""
        spacing_guidance = "9x9m triangular: 60 palms/acre. 9x7.8m triangular: 66 palms/acre."
    elif ct == "perennial_fruit":
        water_guidance = """
FRUIT CROP DRIP/IRRIGATION:
- Mango: drip 40-60L/tree/day Mar-May, reduce pre-flowering (Nov-Dec stress for flowering induction).
- Lemon: drip 30-50L/tree/day, weekly irrigation in peak summer.
- Critical: avoid waterlogging at any stage for mango/lemon.
"""
        spacing_guidance = "Mango: 10x10m (40 trees/acre). Lemon/lime: 5x4m (200 trees/acre)."
    elif ct == "perennial_timber":
        water_guidance = """
EUCALYPTUS IRRIGATION:
- Year 1: 30L/plant/week until established (3-4 months)
- Year 2+: rainfed if >750mm rainfall; supplemental drip in dry spells
- Caution: heavy user — 6-8 litres/day/tree at peak
"""
        spacing_guidance = "Pulpwood: 2x2m (1000 trees/acre). Timber: 3x2m (667 trees/acre)."
    else:
        water_guidance = ""
        spacing_guidance = ""

    prompt = f"""
FARMER PROFILE:
{p}

CHOSEN VARIETY (from node 1): {chosen_variety}
LAND PREP DECIDED: {variety_land.get("land_preparation", "standard")}

{water_guidance}

SPACING GUIDANCE: {spacing_guidance}

Provide the complete spacing, water regime, irrigation schedule and nutrition program.

NUTRITION GUIDELINES:
- Paddy: NPK 40:20:20 per acre split 3 ways; zinc 5kg/acre basal; foliar urea at tillering.
- Cotton: NPK 32:16:16 split 4 ways; boron 1kg/acre at square formation; foliar K at boll stage.
- Perennials (mango/lemon): NPK per tree by age; micronutrients (Mn, Zn, B) foliar twice/year.
- Oil palm: major NPK per palm per month by age cohort; magnesium critical.
- Eucalyptus: NPK 60:30:30/acre basal + top-dress at 2-3 months.

Return SpacingWaterNutritionOutput with full irrigation_schedule (monthly) and nutrition_program (by growth stage).
Nitrogen_split_protocol only for paddy/cotton.
"""

    result: SpacingWaterNutritionOutput = _call_anthropic_structured(
        SpacingWaterNutritionOutput,
        prompt,
        label="spacing_water_nutrition",
        max_tokens=5120,
        timeout=240,
    )
    return {"spacing_water_nutrition": result.model_dump()}


def _node_protection(state: YieldOptimizerGraphState) -> dict:
    """Node 3: Crop protection calendar and protocols."""
    profile = state["profile"]
    p = _profile_summary(profile)
    ct = profile.crop_type
    focused_crop = profile.focused_crop.lower()

    mandatory_note = ""
    if ct == "annual_grain" and ("maize" in focused_crop or "corn" in focused_crop):
        mandatory_note = """
MANDATORY: fall_armyworm_protocol and wildlife_deterrent_plan are REQUIRED for maize/corn.
Fall armyworm (FAW): most devastating pest. Use pheromone traps (1 per acre),
Bt spray (Coragen 18.5SC), SpiltNPV, intercrop with cowpea.
Wildlife: nilgai, wild boar, monkeys — solar fencing, chilli smoke, community watch.
"""
    elif ct == "annual_grain":
        mandatory_note = "Paddy: blast, BPH, stem borer, leaf folder are key pests."
    elif ct == "annual_fiber":
        mandatory_note = """
MANDATORY: refuge_strategy is REQUIRED for Bt cotton.
Refuge: 5% non-Bt cotton (1 row per 20 Bt rows) as bollworm refuge.
Pheromone traps: 2/acre for pink bollworm monitoring.
"""
    elif ct in ("perennial_fruit",) and "mango" in focused_crop:
        mandatory_note = """
MANDATORY: paclobutrazol_protocol, pollination_strategy, and canopy_management REQUIRED for mango.
PBZ: Cultar 23.1SC soil drench at 1-1.5g a.i./m canopy diameter, Oct-Nov (before flowering).
Pollination: honey bee hives (2-4/acre) during flowering Feb-Mar.
Canopy: open-center pruning post-harvest Jun-Jul, remove criss-crossing branches.
"""
    elif ct == "perennial_oilseed":
        mandatory_note = """
MANDATORY: ganoderma_prevention_protocol and pollination_strategy (weevil) REQUIRED for oil palm.
Ganoderma: most destructive disease. Early detection (conch fruiting bodies),
remove and burn infected palms, soil treatment with Trichoderma, no palm debris in field.
Pollination: Elaeidobius weevil (introduce 50-100/palm at first male anthesis if not naturally present).
"""
    elif ct == "perennial_timber":
        mandatory_note = """
Eucalyptus: gall wasp (Leptocybe invasa) is key pest — use resistant clones.
Canopy management: prune lower branches at year 1-2 for clean bole.
MANDATORY: canopy_management REQUIRED for eucalyptus — pruning schedule for clean bole:
- Year 0.5: prune lower 1/3 of branches to encourage straight bole growth
- Year 1.5: remove remaining dead/crossing lower branches
Include expected bole quality impact.
"""

    prompt = f"""
FARMER PROFILE:
{p}

CROP-SPECIFIC PROTECTION NOTES:
{mandatory_note}

Organic required: {profile.organic_required}
Avoid chemical pesticides: {profile.avoid_chemical_pesticides}

Provide a comprehensive crop protection plan including:
1. Monthly pest calendar (all 12 months, major pests + actions)
2. Any mandatory protocols (FAW, refuge, PBZ, Ganoderma, pollination) as specified above

For organic farmers: emphasize ZBNF (Jeevamrutha, Beejamrutha), biopesticides,
Trichoderma/Pseudomonas, pheromone traps, neem-based sprays.

Return ProtectionOutput — only fill optional fields that are relevant to this crop.
"""

    result: ProtectionOutput = _call_anthropic_structured(
        ProtectionOutput,
        prompt,
        label="protection",
        max_tokens=5120,
        timeout=240,
    )
    return {"protection": result.model_dump()}


def _node_harvest_economics_risks(state: YieldOptimizerGraphState) -> dict:
    """Node 4: Harvest, economics, risks — reads variety_land + protection."""
    profile = state["profile"]
    variety_land = state.get("variety_land", {})
    protection = state.get("protection", {})
    p = _profile_summary(profile)
    ct = profile.crop_type
    focused_crop = profile.focused_crop.lower()
    chosen_variety = variety_land.get("focused_variety", profile.focused_crop)

    econ_guidance = ""
    if ct == "perennial_oilseed":
        econ_guidance = """
OIL PALM ECONOMICS (25-year crop):
- Buyback: mandatory from NMEO-OP approved buyer (Ruchi Soya, Godrej Agrovet, 3F Oil Palm).
  Contract duration: 25 years. Pricing: govt-announced MSP + FFB premium.
  Advance/subsidy recovery: ₹6,000/acre advance recoverable from FFB payments.
- Yield benchmarks: Year 3: 2-4 t FFB/acre; Year 7+: 8-12 t FFB/acre (peak).
- Decadal cash flow: must cover years 1-25.
- Production costs: drip maintenance, fertilizer, harvest labor (monthly).
- Carbon credits: REDD+/Verra potential for oil palm agroforestry systems.
"""
    elif ct == "perennial_timber":
        econ_guidance = """
EUCALYPTUS ECONOMICS:
- Coppice strategy REQUIRED: rotation 4-5 years, 3 coppice cycles, total 15-20 years.
- Carbon credits: eucalyptus plantation qualifies for VCS/Gold Standard carbon credits.
  Estimated 2-4 tCO2e/acre/year, ₹1,000-2,000/acre/year at current markets.
- ITC/JK Paper buyback: ₹4,500-6,500/tonne pulpwood depending on district agreement.
- Yield: 15-20 t/acre/rotation (first); 12-18 t subsequent coppice.
"""
    elif ct in ("perennial_fruit",) and "mango" in focused_crop:
        econ_guidance = """
MANGO ECONOMICS:
- Off-season strategy (PBZ-induced): Banganapalli off-season (Sep-Nov) fetches 2-3x price.
  Techniques: PBZ drench + ethephon spray to advance/delay harvest.
- Yield: Year 4-5: 1-2 t/acre; Year 8+: 4-6 t/acre; Year 15+: 6-10 t/acre.
- Market: local mandi vs direct export agent (Kurnool, Hyderabad exporters).
"""
    elif ct == "annual_grain":
        econ_guidance = """
PADDY ECONOMICS:
- MSP: ₹2,300/quintal (Kharif 2024). Procurement via Telangana Civil Supplies.
- Custom milling: ₹800-1,200/tonne milling margin if own-mill or FPO.
- Yield target: SRI 25-30 quintals/acre vs district average 18-22 quintals/acre.
"""
    elif ct == "annual_fiber":
        econ_guidance = """
COTTON ECONOMICS:
- MSP: ₹7,000-7,500/quintal. Kapas price varies ₹6,500-8,500 in mandi.
- Extra-long staple premium: 15-20% over MSP for ELS variety.
- HDPS cotton: 10-14 quintals/acre vs standard 6-8 quintals/acre.
"""

    prompt = f"""
FARMER PROFILE:
{p}

CHOSEN VARIETY: {chosen_variety}
PROTECTION PLAN SUMMARY: {list(protection.keys())}

{econ_guidance}

Provide complete harvest, economics and risk analysis:
1. Harvest and post-harvest: maturity indicators, harvest method, storage.
2. Yield benchmarks: year-by-year low/high for 1-10 years (or crop lifespan).
3. Decadal cash flow: year 1-10 investment, revenue, net (for perennials, year 1-25).
4. Production costs: line items (land prep, inputs, labor, irrigation, harvest).
5. Risk register: 5-7 risks with probability, impact, mitigation.
6. Optimization levers: 5-7 ranked levers with yield uplift% and investment.
7. Benchmark comparison: district average vs state best vs this plan's target.

Fill optional fields only where relevant:
- buyback_contract_strategy: oil palm and eucalyptus only
- carbon_credit_potential: eucalyptus and oil palm agroforestry
- off_season_strategy: mango only
- coppice_strategy: eucalyptus only

Return HarvestEconomicsOutput.
"""

    result: HarvestEconomicsOutput = _call_anthropic_structured(
        HarvestEconomicsOutput,
        prompt,
        label="harvest_economics_risks",
        max_tokens=8192,
        timeout=360,
        max_retries=5,
    )
    return {"harvest_economics": result.model_dump()}


def _node_assemble(state: YieldOptimizerGraphState) -> dict:
    """Node 5 (deterministic): Stitch all intermediate dicts into YieldOptimizationPlan."""
    profile = state["profile"]
    vl = state.get("variety_land", {})
    swn = state.get("spacing_water_nutrition", {})
    prot = state.get("protection", {})
    he = state.get("harvest_economics", {})

    plan_id = f"yopt_{uuid4().hex[:8]}"

    # Placeholder critique — will be filled by _node_critique
    placeholder_critique = YieldCritique(
        why_target_is_realistic=["Plan assembled — critique pending."],
        why_target_might_NOT_be_realistic=["Critique pending."],
        biggest_yield_gap_driver="Critique pending.",
        overall_confidence=0.7,
    )

    assembled_plan = YieldOptimizationPlan(
        plan_id=plan_id,
        farmer_id=profile.farmer_id,
        crop_type=profile.crop_type,
        focused_crop=profile.focused_crop,
        focused_variety=vl.get("focused_variety", profile.focused_variety or profile.focused_crop),
        focused_acres=profile.focused_acres,
        current_stage=profile.current_stage,
        # 1. Variety + land
        variety_rationale=vl.get("variety_rationale", ""),
        clone_selection=CloneSelection(**vl["clone_selection"]) if vl.get("clone_selection") else None,
        land_preparation=LandPrep(**vl["land_preparation"]) if vl.get("land_preparation") else LandPrep(),
        # 2. Geometry + water
        spacing_and_density=SpacingDensity(**swn["spacing_and_density"]) if swn.get("spacing_and_density") else SpacingDensity(row_spacing_m=1.0, plant_spacing_m=1.0, plants_per_acre=4000),
        water_regime=WaterRegime(**swn["water_regime"]) if swn.get("water_regime") else WaterRegime(primary_method="weekly_irrigation", rationale="default"),
        irrigation_schedule=IrrigationSchedule(**swn["irrigation_schedule"]) if swn.get("irrigation_schedule") else IrrigationSchedule(monthly_schedule=[], growth_stage_overrides=[]),
        # 3. Nutrition
        nutrition_program=[NutritionStage(**s) for s in swn.get("nutrition_program", [])],
        nitrogen_split_protocol=NitrogenSplits(**swn["nitrogen_split_protocol"]) if swn.get("nitrogen_split_protocol") else None,
        # 4. Crop protection
        pest_calendar=[PestEvent(**e) for e in prot.get("pest_calendar", [])],
        fall_armyworm_protocol=FallArmywormProtocol(**prot["fall_armyworm_protocol"]) if prot.get("fall_armyworm_protocol") else None,
        refuge_strategy=RefugeStrategy(**prot["refuge_strategy"]) if prot.get("refuge_strategy") else None,
        ganoderma_prevention_protocol=GanodermaProtocol(**prot["ganoderma_prevention_protocol"]) if prot.get("ganoderma_prevention_protocol") else None,
        wildlife_deterrent_plan=WildlifeDeterrent(**prot["wildlife_deterrent_plan"]) if prot.get("wildlife_deterrent_plan") else None,
        # 5. Crop-stage specifics
        canopy_management=CanopyManagement(**prot["canopy_management"]) if prot.get("canopy_management") else None,
        coppice_strategy=CoppiceStrategy(**he["coppice_strategy"]) if he.get("coppice_strategy") else None,
        paclobutrazol_protocol=PBZProtocol(**prot["paclobutrazol_protocol"]) if prot.get("paclobutrazol_protocol") else None,
        off_season_strategy=OffSeasonStrategy(**he["off_season_strategy"]) if he.get("off_season_strategy") else None,
        pollination_strategy=PollinationStrategy(**prot["pollination_strategy"]) if prot.get("pollination_strategy") else None,
        # 6. Harvest + post-harvest
        harvest_and_postharvest=HarvestPlan(**he["harvest_and_postharvest"]) if he.get("harvest_and_postharvest") else HarvestPlan(maturity_indicators=[], harvest_method="manual", post_harvest_steps=[]),
        buyback_contract_strategy=BuybackContract(**he["buyback_contract_strategy"]) if he.get("buyback_contract_strategy") else None,
        # 7. Economics
        yield_benchmarks=[YearlyYieldBenchmark(**b) for b in he.get("yield_benchmarks", [])],
        decadal_cash_flow=[YearlyCashFlow(**cf) for cf in he.get("decadal_cash_flow", [])],
        production_costs=[CostLineItem(**c) for c in he.get("production_costs", [])],
        carbon_credit_potential=CarbonCredit(**he["carbon_credit_potential"]) if he.get("carbon_credit_potential") else None,
        # 8. Risks + levers
        risk_register=[YieldRisk(**r) for r in he.get("risk_register", [])],
        optimization_levers=[OptimizationLever(**lv) for lv in he.get("optimization_levers", [])],
        benchmark_comparison=BenchmarkComparison(**he["benchmark_comparison"]) if he.get("benchmark_comparison") else BenchmarkComparison(district_average=0, state_best=0, target=0, unit="kg/acre", gap_analysis=""),
        # 9. Confidence + disclaimers
        confidence_self=0.75,
        confidence_meta=0.7,
        critique=placeholder_critique,
        disclaimers=[
            "This plan is advisory only — consult local KVK/ATMA before major investments.",
            "Prices and yields are estimates based on Telangana averages; actual results vary.",
            "Govt scheme eligibility subject to current year notifications.",
        ],
    )
    if not assembled_plan.yield_benchmarks:
        print(f"[assemble] WARNING: yield_benchmarks empty for {profile.farmer_id}")
    if not assembled_plan.decadal_cash_flow:
        print(f"[assemble] WARNING: decadal_cash_flow empty for {profile.farmer_id}")
    if not assembled_plan.pest_calendar:
        print(f"[assemble] WARNING: pest_calendar empty for {profile.farmer_id}")
    return {"plan": assembled_plan}


def _node_critique(state: YieldOptimizerGraphState) -> dict:
    """Node 6: Devil's advocate critique of the assembled plan."""
    profile = state["profile"]
    plan: YieldOptimizationPlan = state["plan"]

    prompt = f"""
You are reviewing a yield optimization plan for:
- Farmer: {profile.farmer_id}
- Crop: {plan.focused_crop} ({plan.focused_variety}) on {plan.focused_acres} acres
- Stage: {plan.current_stage}
- Parcel notes: {profile.parcel_notes or "none"}

PLAN SUMMARY:
- Water regime: {plan.water_regime.primary_method} — {plan.water_regime.rationale}
- Spacing: {plan.spacing_and_density.plants_per_acre} plants/acre
- Nutrition stages: {len(plan.nutrition_program)}
- Pest calendar entries: {len(plan.pest_calendar)}
- Yield benchmarks: {[(b.year, b.low_yield, b.high_yield, b.unit) for b in plan.yield_benchmarks[:3]]}
- Top optimization lever: {plan.optimization_levers[0].lever if plan.optimization_levers else "none"} ({plan.optimization_levers[0].yield_uplift_pct if plan.optimization_levers else 0}% uplift)
- Biggest risk: {plan.risk_register[0].risk if plan.risk_register else "none"}
- Target vs district avg: {plan.benchmark_comparison.target} vs {plan.benchmark_comparison.district_average} {plan.benchmark_comparison.unit}

Play devil's advocate. Be honest and specific.
Return a YieldCritique with:
- why_target_is_realistic: 3-5 concrete reasons this plan can succeed
- why_target_might_NOT_be_realistic: 3-5 honest risks/reasons it may fail
- biggest_yield_gap_driver: the single most likely bottleneck on THIS specific parcel
- overall_confidence: 0-1 calibrated probability the plan achieves its stated yield target
"""

    result: YieldCritique = _call_anthropic_structured(
        YieldCritique,
        prompt,
        label="critique",
        max_tokens=2048,
        timeout=120,
    )
    return {"critique": result.model_dump()}


# =====================================================================
# Graph builder
# =====================================================================


def build_yield_optimizer_graph(checkpointer=None):
    """Build and compile the yield optimizer LangGraph.

    Pipeline:
        START → variety_and_land
            ├──→ spacing_water_nutrition  (parallel)
            └──→ protection              (parallel)
                    join ↓
             harvest_economics_risks
                    ↓
                assemble (deterministic)
                    ↓
                critique
                    ↓
                   END
    """
    if not _LANGGRAPH_AVAILABLE:
        raise RuntimeError("langgraph not installed — `pip install langgraph`")

    g = StateGraph(YieldOptimizerGraphState)
    g.add_node("variety_and_land", _node_variety_and_land)
    g.add_node("spacing_water_nutrition", _node_spacing_water_nutrition)
    g.add_node("protection", _node_protection)
    g.add_node("harvest_economics_risks", _node_harvest_economics_risks)
    g.add_node("assemble", _node_assemble)
    g.add_node("critique", _node_critique)

    g.add_edge(START, "variety_and_land")
    # Symmetric fan-out from variety_and_land (same superstep → correct fan-in)
    g.add_edge("variety_and_land", "spacing_water_nutrition")
    g.add_edge("variety_and_land", "protection")
    # Fan-in at harvest_economics_risks
    g.add_edge("spacing_water_nutrition", "harvest_economics_risks")
    g.add_edge("protection", "harvest_economics_risks")
    # Sequential tail
    g.add_edge("harvest_economics_risks", "assemble")
    g.add_edge("assemble", "critique")
    g.add_edge("critique", END)

    return g.compile(checkpointer=checkpointer)


# =====================================================================
# Public API
# =====================================================================


def generate_yield_plan(profile: YieldOptimizationProfile) -> YieldOptimizationPlan:
    """Run the full 5-LLM-call pipeline synchronously. Returns completed plan."""
    checkpointer = MemorySaver()
    graph = build_yield_optimizer_graph(checkpointer=checkpointer)
    thread_id = f"yopt_{uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    initial: YieldOptimizerGraphState = {"profile": profile}
    final = graph.invoke(initial, config=config)

    # Attach the critique to the plan
    plan: YieldOptimizationPlan = final["plan"]
    critique = YieldCritique.model_validate(final["critique"])
    plan = plan.model_copy(update={"critique": critique})
    return plan


def stream_yield_plan(profile: YieldOptimizationProfile):
    """Generator yielding per-node events for UI streaming progress.
    Each yielded value is a dict {node_name: state_delta}.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from uuid import uuid4
    checkpointer = MemorySaver()
    graph = build_yield_optimizer_graph(checkpointer=checkpointer)
    thread_id = f"yopt_{uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    initial = {"profile": profile}
    for event in graph.stream(initial, config=config, stream_mode="updates"):
        yield event


# =====================================================================
# PDF renderer
# =====================================================================

def _safe(text: str) -> str:
    """Sanitize text for fpdf2 core fonts (Latin-1 only)."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "→": "->", "←": "<-", "•": "*", "★": "*", "❌": "[X]", "✅": "[OK]",
        "₹": "Rs.", "—": "-", "–": "-", "…": "...",
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "≥": ">=", "≤": "<=",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin1", errors="replace").decode("latin1")



# =====================================================================
# PDF renderer
# =====================================================================

_GD = (30, 100, 55)    # green dark
_GM = (60, 140, 80)    # green mid
_GL = (220, 240, 225)  # green light
_GP = (245, 252, 247)  # green pale (alternating row)
_GR = (100, 100, 100)  # grey
_W  = (255, 255, 255)  # white
_BK = (0, 0, 0)        # black

_TBL_HEADING = FontFace(emphasis="BOLD", color=_W, fill_color=_GM, size_pt=8)
_TBL_ALT     = _GP


def _safe(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    for k, v in {
        "→": "->", "←": "<-", "•": "-", "★": "*", "❌": "[X]", "✅": "[OK]",
        "₹": "Rs.", "—": "-", "–": "-", "…": "...",
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "≥": ">=", "≤": "<=",
    }.items():
        text = text.replace(k, v)
    return text.encode("latin1", errors="replace").decode("latin1")


def _s(v) -> str:
    return _safe(str(v)) if v is not None else ""


class YieldPlanPDF(FPDF):
    LM = 18          # left/right margin mm
    CW = 174         # content width = 210 - 2*18
    LH = 4.8         # default line height

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(self.LM, 16, self.LM)

    # ── chrome ──────────────────────────────────────────────────────
    def header(self):
        self.set_fill_color(*_GD)
        self.rect(0, 0, 210, 9, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_W)
        self.set_xy(0, 1)
        self.cell(0, 7, "  Crop Yield Optimizer  |  Telangana Farm Planner", align="L")
        self.set_text_color(*_BK)
        self.ln(5)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(*_GM)
        self.line(self.LM, self.get_y(), 210 - self.LM, self.get_y())
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*_GR)
        self.cell(0, 6, _safe(f"Page {self.page_no()}  |  Advisory only — validate with local KVK before applying."), align="C")
        self.set_text_color(*_BK)

    # ── typography helpers ───────────────────────────────────────────
    def h1(self, text: str):
        self.ln(4)
        self.set_x(self.LM)
        self.set_fill_color(*_GD)
        self.set_text_color(*_W)
        self.set_font("Helvetica", "B", 12)
        self.cell(self.CW, 8, _safe("  " + text), ln=True, fill=True)
        self.set_text_color(*_BK)
        self.ln(2)

    def h2(self, text: str):
        self.ln(2)
        self.set_x(self.LM)
        self.set_fill_color(*_GL)
        self.set_text_color(*_GD)
        self.set_font("Helvetica", "B", 10)
        self.cell(self.CW, 6, _safe("  " + text), ln=True, fill=True)
        self.set_text_color(*_BK)
        self.ln(1)

    def body(self, text: str):
        if not text:
            return
        self.set_x(self.LM)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(self.CW, self.LH, _safe(str(text)))
        self.ln(1)

    def bullet(self, text: str):
        if not text:
            return
        self.set_x(self.LM)
        self.set_font("Helvetica", "", 9)
        self.cell(5, self.LH, "-", ln=False)
        self.multi_cell(self.CW - 5, self.LH, _safe(str(text)))

    def kv(self, key: str, val):
        if val is None or val == "":
            return
        self.set_x(self.LM)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*_GD)
        self.cell(55, self.LH, _safe(str(key) + ":"), ln=False)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_BK)
        self.multi_cell(self.CW - 55, self.LH, _safe(str(val)))

    def divider(self):
        self.ln(2)
        self.set_x(self.LM)
        self.set_draw_color(*_GL)
        self.line(self.LM, self.get_y(), 210 - self.LM, self.get_y())
        self.set_draw_color(*_BK)
        self.ln(2)

    # ── table helper ─────────────────────────────────────────────────
    def tbl(self, headers: list[tuple[str, int]], rows: list[list]):
        """Render a table using fpdf2 native table() — handles multi-line cells."""
        col_widths = tuple(w for _, w in headers)
        self.set_font("Helvetica", "", 8)
        with self.table(
            col_widths=col_widths,
            headings_style=_TBL_HEADING,
            line_height=4.8,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_TBL_ALT,
            cell_fill_mode=TableCellFillMode.ROWS,
            first_row_as_headings=True,
        ) as table:
            hrow = table.row()
            for label, _ in headers:
                hrow.cell(_safe(label))
            for row_data in rows:
                row = table.row()
                for cell in row_data:
                    row.cell(_s(cell))
        self.ln(1)


def _build_weekly_calendar(plan: "YieldOptimizationPlan") -> list[dict]:
    """Derive a week-by-week crop calendar from plan data."""
    crop = plan.focused_crop.lower()
    if any(x in crop for x in ("paddy", "rice")):
        total_days = 120
        stage_map = [
            (0, 7,   "Nursery prep"),
            (7, 14,  "Nursery / seedling"),
            (14, 21, "Seedling growth"),
            (21, 35, "Transplanting & estab."),
            (35, 49, "Active tillering"),
            (49, 63, "Maximum tillering"),
            (63, 77, "Panicle initiation"),
            (77, 91, "Booting / heading"),
            (91, 105,"Flowering / grain fill"),
            (105, 120,"Grain maturity / harvest"),
        ]
    elif "cotton" in crop:
        total_days = 180
        stage_map = [
            (0, 14,"Germination"),(14,35,"Seedling"),(35,70,"Squaring"),
            (70,105,"Flowering"),(105,150,"Boll dev."),(150,180,"Maturity"),
        ]
    elif "corn" in crop or "maize" in crop:
        total_days = 110
        stage_map = [
            (0,14,"Germination"),(14,35,"V-stage"),(35,55,"V6-V12"),
            (55,70,"Tasseling/Silking"),(70,90,"Grain fill"),(90,110,"Maturity"),
        ]
    elif "mango" in crop:
        total_days = 365
        stage_map = [
            (0,60,"Dormancy"),(60,120,"Flowering"),(120,180,"Fruit set"),
            (180,270,"Fruit dev."),(270,330,"Pre-harvest"),(330,365,"Harvest"),
        ]
    else:
        total_days = 120
        stage_map = [(0, total_days, "Growing season")]

    def stage_for(dap):
        for s, e, n in stage_map:
            if s <= dap < e:
                return n
        return stage_map[-1][2]

    # Fertilizer events keyed by week
    fert: dict[int, list[str]] = {}
    if plan.nitrogen_split_protocol:
        for sp in plan.nitrogen_split_protocol.splits:
            w = sp.days_after_sowing // 7 + 1
            fert.setdefault(w, []).append(f"N {sp.pct}% - {sp.stage}")
    if plan.nutrition_program:
        for ns in plan.nutrition_program:
            try:
                d = int((ns.dap_range or "0").split("-")[0].replace("DAT","").strip())
                w = d // 7 + 1
                fert.setdefault(w, []).append(f"{ns.stage_name[:20]}")
            except Exception:
                pass

    # Irrigation events by week
    irr: dict[int, str] = {}
    if plan.irrigation_schedule.monthly_schedule:
        for idx, m in enumerate(plan.irrigation_schedule.monthly_schedule):
            for w in range(idx * 4 + 1, idx * 4 + 5):
                irr[w] = f"{m.depth_mm}mm / {m.frequency[:25]}"

    # Pest events
    pest: dict[int, list[str]] = {}
    if plan.pest_calendar:
        for idx, pe in enumerate(plan.pest_calendar):
            w = idx * 4 + 2
            if pe.pest_name and pe.pest_name.lower() not in ("nil","none","n/a"):
                pest.setdefault(w, []).append(pe.pest_name[:25])

    total_weeks = min((total_days + 6) // 7, 52)
    rows = []
    for w in range(1, total_weeks + 1):
        dap = (w - 1) * 7
        rows.append({
            "week": w,
            "dap": f"{dap}-{dap+6}",
            "stage": stage_for(dap),
            "irrigation": irr.get(w, "-"),
            "fertilizer": "; ".join(fert.get(w, ["-"])),
            "pest_ipm": "; ".join(pest.get(w, ["Routine scout"])),
        })
    return rows


def render_yield_plan_pdf(plan: "YieldOptimizationPlan", output_path) -> "Path":
    """Render a YieldOptimizationPlan to a clean, well-formatted PDF."""
    pdf = YieldPlanPDF()

    # ═══════════════════════════════════════════════════════════
    # PAGE 1 — Cover
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()

    # Hero band
    pdf.set_fill_color(*_GD)
    pdf.rect(0, 18, 210, 45, "F")
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_W)
    pdf.set_xy(0, 24)
    pdf.cell(0, 12, _safe("Crop Yield Optimizer Report"), ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, _safe(f"{plan.focused_crop.title()}  |  {plan.focused_variety or plan.focused_crop}"), ln=True, align="C")
    pdf.set_text_color(*_BK)

    # Summary box
    pdf.set_xy(25, 72)
    pdf.set_fill_color(*_GP)
    pdf.set_draw_color(*_GM)
    pdf.rect(25, 70, 160, 55, "FD")

    pdf.set_xy(32, 75)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_GD)
    pdf.cell(0, 7, "Plan Summary", ln=True)
    pdf.set_text_color(*_BK)

    for label, val in [
        ("Farmer ID",   plan.farmer_id),
        ("Plan ID",     plan.plan_id),
        ("Crop",        plan.focused_crop.title()),
        ("Variety",     plan.focused_variety or "-"),
        ("Area",        f"{plan.focused_acres} acres"),
        ("Stage",       plan.current_stage),
        ("Confidence",  f"{plan.confidence_self:.0%} (self-assessed)"),
    ]:
        pdf.set_x(32)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_GD)
        pdf.cell(52, 5.5, _safe(label + ":"), ln=False)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_BK)
        pdf.cell(0, 5.5, _safe(str(val)), ln=True)

    pdf.set_xy(25, 132)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_GR)
    pdf.cell(0, 5, "Advisory report. All recommendations must be validated with local KVK officer before application.", align="C")
    pdf.set_text_color(*_BK)

    # Table of contents hint
    pdf.set_xy(25, 145)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_GD)
    pdf.cell(0, 6, "Contents:", ln=True)
    pdf.set_x(28)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_BK)
    sections = [
        "1. Variety Selection & Land Preparation",
        "2. Spacing, Water & Irrigation",
        "3. Nutrition Program",
        "4. IPM & Crop Protection",
        "5. Harvest & Post-harvest",
        "6. Economics & Cash Flow",
        "7. Risk Register & Optimization Levers",
        "8. Devil's Advocate Critique",
        "9. Week-by-Week Activity Calendar",
    ]
    for sec in sections:
        pdf.set_x(30)
        pdf.cell(0, 5, _safe(sec), ln=True)

    # ═══════════════════════════════════════════════════════════
    # PAGE 2 — Variety & Land Preparation
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("1. Variety Selection & Land Preparation")
    pdf.body(plan.variety_rationale)

    lp = plan.land_preparation
    pdf.h2("Land Preparation")
    pdf.kv("Soil test needed", "Yes — obtain results before transplanting" if lp.soil_test_needed else "No")
    if lp.amendments:
        pdf.kv("Soil amendments", ", ".join(lp.amendments))
    pdf.kv("Tillage / bed type", lp.bed_type)
    pdf.kv("Drainage", lp.drainage_notes)

    if plan.clone_selection:
        cs = plan.clone_selection
        pdf.h2("Clone / Variety Details")
        pdf.kv("Recommended clones", ", ".join(cs.recommended_clones))
        pdf.kv("Source nursery", cs.source_organization)
        pdf.kv("Expected yield / rotation", cs.expected_yield_per_acre_per_rotation)
        pdf.kv("Productive life", f"{cs.productive_lifetime_years} years")

    # ═══════════════════════════════════════════════════════════
    # Spacing, Water & Irrigation (continues on same page if room)
    # ═══════════════════════════════════════════════════════════
    pdf.h1("2. Spacing, Water & Irrigation")
    sd = plan.spacing_and_density
    pdf.kv("Plant spacing", f"{sd.row_spacing_m} m (row)  x  {sd.plant_spacing_m} m (plant)")
    pdf.kv("Plant density", f"{sd.plants_per_acre:,} plants / acre")
    if sd.geometry_notes:
        pdf.kv("Geometry notes", sd.geometry_notes)

    wr = plan.water_regime
    pdf.h2("Water Regime")
    pdf.kv("Method", wr.primary_method)
    pdf.body(wr.rationale)
    if wr.water_savings_pct is not None:
        pdf.kv("Water savings vs flood", f"{wr.water_savings_pct:.0f}%")
    if wr.yield_impact_pct is not None:
        pdf.kv("Yield impact", f"{wr.yield_impact_pct:+.0f}%")
    if wr.setup_investment_inr:
        pdf.kv("Setup investment", str(wr.setup_investment_inr))

    if plan.irrigation_schedule.monthly_schedule:
        pdf.h2("Monthly Irrigation Schedule")
        rows = [[m.month, str(m.depth_mm), m.frequency]
                for m in plan.irrigation_schedule.monthly_schedule]
        pdf.tbl([("Month", 30), ("Depth (mm)", 28), ("Frequency / Notes", 116)], rows)

    if plan.irrigation_schedule.growth_stage_overrides:
        pdf.h2("Growth-Stage Overrides")
        for ov in plan.irrigation_schedule.growth_stage_overrides:
            pdf.bullet(ov)

    # ═══════════════════════════════════════════════════════════
    # Section 3 — Nutrition (flows from previous section)
    # ═══════════════════════════════════════════════════════════
    pdf.h1("3. Nutrition Program")

    if plan.nutrition_program:
        rows = [[ns.stage_name, ns.dap_range or "", ", ".join(ns.fertilizers)]
                for ns in plan.nutrition_program]
        pdf.tbl([("Stage", 48), ("DAP Range", 28), ("Fertilizers Applied", 98)], rows)
        for ns in plan.nutrition_program:
            if ns.notes:
                pdf.bullet(f"{ns.stage_name}: {ns.notes}")
        pdf.ln(1)

    if plan.nitrogen_split_protocol:
        nsp = plan.nitrogen_split_protocol
        pdf.h2(f"Nitrogen Split Protocol  —  {nsp.total_n_kg_per_acre} kg N / acre total")
        rows = [[s.stage, f"{s.pct}%", f"DAP {s.days_after_sowing}"]
                for s in nsp.splits]
        pdf.tbl([("Growth Stage", 85), ("% of Total N", 40), ("Day After Transplant (DAP)", 49)], rows)
        if nsp.foliar_corrections:
            pdf.h2("Foliar Corrections")
            for fc in nsp.foliar_corrections:
                pdf.bullet(fc)

    # ═══════════════════════════════════════════════════════════
    # PAGE 4 — IPM & Crop Protection
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("4. IPM & Crop Protection")

    if plan.pest_calendar:
        pdf.h2("Monthly Pest Calendar")
        rows = [[pe.month, pe.pest_name, pe.threshold, pe.organic_action, pe.chemical_action]
                for pe in plan.pest_calendar]
        pdf.tbl([
            ("Month", 20), ("Pest / Disease", 44), ("Threshold", 36),
            ("Organic First", 42), ("Chemical (last resort)", 32),
        ], rows)

    if plan.fall_armyworm_protocol:
        faw = plan.fall_armyworm_protocol
        pdf.h2("Fall Armyworm Protocol (MANDATORY)")
        pdf.kv("Monitoring", faw.monitoring_protocol)
        pdf.kv("Action threshold", faw.threshold_for_action)
        pdf.kv("Loss without action", faw.expected_damage_without_intervention)
        pdf.kv("Intercrop", faw.intercrop_recommendation)
        pdf.h2("Step 1: Organic options")
        for opt in faw.organic_first_options:
            pdf.bullet(opt)
        pdf.h2("Step 2: Chemical options (only if threshold breached)")
        for opt in faw.chemical_options_if_severe:
            pdf.bullet(opt)

    if plan.refuge_strategy:
        r = plan.refuge_strategy
        pdf.h2("Bt Refuge Strategy (MANDATORY for Bt Cotton)")
        pdf.kv("Refuge crop", r.refuge_crop)
        pdf.kv("Refuge area", f"{r.refuge_acres:.2f} acres")
        pdf.kv("Pheromone traps", str(r.pheromone_traps))
        pdf.body(r.rationale)

    if plan.ganoderma_prevention_protocol:
        g = plan.ganoderma_prevention_protocol
        pdf.h2("Ganoderma Prevention — Basal Stem Rot")
        pdf.h2("Early Detection Indicators")
        for ind in g.early_detection_indicators:
            pdf.bullet(ind)
        pdf.kv("Drainage requirement", g.drainage_requirements)
        pdf.kv("Quarantine protocol", g.quarantine_protocol)

    if plan.wildlife_deterrent_plan:
        wd = plan.wildlife_deterrent_plan
        pdf.h2("Wildlife Deterrent Plan")
        pdf.kv("Threat species", ", ".join(wd.threats))
        pdf.kv("Crop loss without action", f"{wd.estimated_loss_without_pct:.0f}%")
        for m in wd.deterrent_methods:
            pdf.bullet(m)

    # Crop-specific sections (mango, eucalyptus, oil palm only — skip for annual grains)
    _is_annual = plan.crop_type in ("annual_grain", "annual_fiber", "annual_oilseed")
    _has_specialty = not _is_annual and (
        any([plan.canopy_management, plan.paclobutrazol_protocol,
             plan.off_season_strategy, plan.coppice_strategy]) or (
            plan.pollination_strategy and plan.pollination_strategy.expected_yield_boost_pct > 0
        )
    )
    if _has_specialty:
        pdf.add_page()
        pdf.h1("4b. Canopy Management, PBZ & Pollination")

        if plan.canopy_management:
            cm = plan.canopy_management
            pdf.h2(f"Canopy Management — {cm.pruning_type}")
            pdf.kv("Timing", cm.timing)
            pdf.body(cm.technique)
            pdf.kv("Expected yield impact", f"{cm.expected_yield_impact_pct:+.0f}%")

        if plan.paclobutrazol_protocol:
            pbz = plan.paclobutrazol_protocol
            pdf.h2("Paclobutrazol (PBZ) Protocol")
            pdf.kv("Application timing", pbz.application_timing)
            pdf.kv("Dose", f"{pbz.dose_per_tree_g} g a.i./tree via {pbz.application_method}")
            pdf.kv("Expected off-season yield", f"{pbz.expected_off_season_yield_pct:.0f}% of normal")
            for r in pbz.risks:
                pdf.bullet(r)

        if plan.off_season_strategy:
            oss = plan.off_season_strategy
            pdf.h2("Off-Season Strategy")
            pdf.kv("Target window", oss.target_off_season_window)
            pdf.kv("Price premium", f"{oss.expected_price_premium_pct:.0f}% over peak-season")
            pdf.kv("Additional investment", str(oss.additional_investment_inr))
            for t in oss.techniques:
                pdf.bullet(t)

        if plan.pollination_strategy:
            ps = plan.pollination_strategy
            pdf.h2("Pollination Strategy")
            pdf.kv("Method", ps.method)
            pdf.body(ps.details)
            pdf.kv("Expected yield boost", f"{ps.expected_yield_boost_pct:+.0f}%")

        if plan.coppice_strategy:
            cs = plan.coppice_strategy
            pdf.h2("Coppice / Multi-Rotation Strategy")
            pdf.kv("Rotation cycle", f"{cs.rotation_cycle_years} years")
            pdf.kv("Coppice cycles", str(cs.coppice_cycles))
            pdf.kv("Total productive life", f"{cs.total_productive_years} years")
            for pr in cs.coppice_practices:
                pdf.bullet(pr)

    # ═══════════════════════════════════════════════════════════
    # Section 5 — Harvest & Post-harvest
    # ═══════════════════════════════════════════════════════════
    pdf.h1("5. Harvest & Post-harvest")
    hp = plan.harvest_and_postharvest
    indicators = hp.maturity_indicators
    if isinstance(indicators, list):
        indicators = ";  ".join(indicators)
    pdf.kv("Maturity indicators", str(indicators))
    pdf.kv("Harvest method", hp.harvest_method)
    if hp.post_harvest_steps:
        pdf.h2("Post-harvest Steps")
        for step in hp.post_harvest_steps:
            pdf.bullet(step)
    if hp.storage_notes:
        pdf.kv("Storage", hp.storage_notes)

    if plan.buyback_contract_strategy:
        bc = plan.buyback_contract_strategy
        pdf.h2("Buyback / Off-take Contract")
        pdf.kv("Recommended buyer", bc.recommended_buyer)
        pdf.kv("Contract duration", f"{bc.contract_duration_years} years")
        pdf.kv("Pricing mechanism", bc.pricing_mechanism)
        pdf.kv("Advance recovery", bc.advance_recovery_terms)
        pdf.body(bc.rationale)

    # ═══════════════════════════════════════════════════════════
    # PAGE 6 — Economics
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("6. Economics & Cash Flow")

    if plan.yield_benchmarks:
        pdf.h2("Year-by-Year Yield Benchmarks")
        rows = [[f"Y{b.year}", str(b.low_yield), str(b.high_yield), b.unit, b.notes]
                for b in plan.yield_benchmarks]
        pdf.tbl([("Year", 16), ("Low", 28), ("High", 28), ("Unit", 34), ("Notes", 68)], rows)

    if plan.decadal_cash_flow:
        pdf.h2("Cash Flow Projection")
        rows = [[f"Y{cf.year}", f"{cf.investment_inr:,.0f}", f"{cf.revenue_inr:,.0f}",
                 f"{cf.net_inr:,.0f}", cf.notes]
                for cf in plan.decadal_cash_flow]
        pdf.tbl([("Year", 12), ("Investment (Rs.)", 36), ("Revenue (Rs.)", 36),
                 ("Net (Rs.)", 36), ("Notes", 54)], rows)

    if plan.production_costs:
        pdf.h2("Production Cost Breakdown")
        rows = [[c.item, f"{c.annual_cost_inr:,.0f}", c.notes or ""]
                for c in plan.production_costs]
        pdf.tbl([("Cost Item", 95), ("Annual Cost (Rs.)", 45), ("Notes", 34)], rows)

    bcomp = plan.benchmark_comparison
    pdf.h2("Benchmark Comparison")
    pdf.tbl(
        [("Metric", 60), ("Value", 60), ("Unit", 54)],
        [
            ["Your target", str(bcomp.target), bcomp.unit],
            ["District average", str(bcomp.district_average), bcomp.unit],
            ["State best practice", str(bcomp.state_best), bcomp.unit],
        ],
    )
    pdf.body(bcomp.gap_analysis)

    if plan.carbon_credit_potential:
        cc = plan.carbon_credit_potential
        pdf.h2("Carbon Credit Potential")
        pdf.kv("Scheme", cc.scheme_name)
        pdf.kv("Sequestration", f"{cc.estimated_tco2e_per_acre_per_year} tCO2e / acre / year")
        pdf.kv("Revenue potential", f"Rs. {cc.revenue_inr_per_acre_per_year} / acre / year")
        pdf.kv("Certification body", cc.certification_body)
        caveats = cc.caveats if isinstance(cc.caveats, list) else [cc.caveats]
        for cv in caveats:
            pdf.bullet(cv)

    # ═══════════════════════════════════════════════════════════
    # PAGE 7 — Risks & Levers
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("7. Risk Register & Optimization Levers")

    if plan.risk_register:
        pdf.h2("Risk Register")
        rows = [[r.risk, r.probability, r.impact, r.mitigation]
                for r in plan.risk_register]
        pdf.tbl([("Risk", 72), ("Probability", 24), ("Impact", 38), ("Mitigation", 40)], rows)

    if plan.optimization_levers:
        pdf.h2("Optimization Levers  (ranked by priority)")
        sorted_levers = sorted(plan.optimization_levers, key=lambda x: x.ranked_priority)
        rows = [[str(lv.ranked_priority), lv.lever, f"+{lv.yield_uplift_pct:.0f}%",
                 str(lv.investment_inr), lv.difficulty, lv.payback]
                for lv in sorted_levers]
        pdf.tbl([
            ("#", 9), ("Lever", 72), ("+Yield", 20),
            ("Investment", 26), ("Difficulty", 24), ("Payback", 23),
        ], rows)

    # ═══════════════════════════════════════════════════════════
    # PAGE 8 — Critique
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("8. Devil's Advocate Critique")
    crit = plan.critique
    if crit:
        conf = crit.overall_confidence
        # Confidence bar
        pdf.set_x(pdf.LM)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_GD)
        pdf.cell(55, 5, "Overall confidence:", ln=False)
        pdf.set_text_color(*_BK)
        bx = pdf.get_x(); by = pdf.get_y() + 1
        bar_w = 80
        pdf.set_fill_color(*_GL)
        pdf.rect(bx, by, bar_w, 4, "FD")
        pdf.set_fill_color(*_GM)
        pdf.rect(bx, by, bar_w * conf, 4, "F")
        pdf.set_xy(bx + bar_w + 3, by - 1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_GD)
        pdf.cell(20, 5, f"{conf:.0%}", ln=True)
        pdf.set_text_color(*_BK)
        pdf.ln(2)

        pdf.kv("Biggest yield gap driver", crit.biggest_yield_gap_driver)
        pdf.ln(2)

        pdf.h2("Why the target IS realistic")
        for r in crit.why_target_is_realistic:
            pdf.bullet(r)

        pdf.h2("Why the target might NOT be realistic")
        for r in crit.why_target_might_NOT_be_realistic:
            pdf.bullet(r)

    # ═══════════════════════════════════════════════════════════
    # PAGE 9 — Week-by-Week Calendar
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("9. Week-by-Week Activity Calendar")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_GR)
    pdf.cell(0, 4, _safe("Derived from N-split protocol, irrigation schedule and IPM calendar. Adjust dates to your actual sowing/transplant date."), ln=True)
    pdf.set_text_color(*_BK)
    pdf.ln(1)

    weekly = _build_weekly_calendar(plan)
    rows = [
        [str(r["week"]), r["dap"], r["stage"], r["irrigation"],
         r["fertilizer"], r["pest_ipm"]]
        for r in weekly
    ]
    pdf.tbl([
        ("Wk", 10), ("DAP", 15), ("Growth Stage", 33), ("Irrigation", 28),
        ("Fertilizer / Nutrition", 45), ("IPM / Scouting", 43),
    ], rows)

    # Key milestones
    pdf.h2("Key Fertilizer Milestones")
    if plan.nitrogen_split_protocol:
        nsp = plan.nitrogen_split_protocol
        for sp in nsp.splits:
            kg = nsp.total_n_kg_per_acre * sp.pct / 100
            pdf.bullet(
                f"DAP {sp.days_after_sowing} (Week {sp.days_after_sowing // 7 + 1}): "
                f"{sp.stage} — apply {sp.pct}% = {kg:.1f} kg N/acre"
            )

    hp = plan.harvest_and_postharvest
    indicators = hp.maturity_indicators
    if isinstance(indicators, list):
        indicators = ";  ".join(indicators[:3])
    pdf.bullet(f"Harvest: {indicators}")

    # ═══════════════════════════════════════════════════════════
    # Final page — Disclaimers
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.h1("Disclaimers & Data Sources")
    for d in (plan.disclaimers or []):
        pdf.bullet(d)
    pdf.bullet("All chemical recommendations must be validated against current CIB&RC registrations before use.")
    pdf.bullet("Yield projections are estimates based on ICAR/KVK published data. Actual results depend on weather, soil variability, and management quality.")
    pdf.bullet("This report does not constitute a guarantee of income or yields. The farmer bears sole responsibility for all agronomic decisions.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
