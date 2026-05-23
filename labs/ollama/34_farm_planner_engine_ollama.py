"""Farm planner engine — Ollama variant.

# Requires: ollama serve + ollama pull llama3.2

Generates structured FarmPlan from FarmProfile + PlanningGoals using an LLM
grounded by the Telangana knowledge base.

Same engine drives:
- Streamlit UI       (34_farm_planner_ui.py)
- FastAPI REST API   (34_farm_planner_api.py)
- Pytest tests       (tests can import + call directly)

When you swap UI from Streamlit to React + FastAPI later, this engine is unchanged.

Public API:
    list_profiles() -> list[ProfileSummary]
    load_profile(farmer_id) -> FarmProfile
    save_profile(profile) -> Path
    delete_profile(farmer_id) -> None

    generate_farm_plan(profile, goals) -> FarmPlan
    score_sustainability(plan) -> SustainabilityScore
    save_plan(plan, farmer_id) -> Path
    load_plans_for_farmer(farmer_id) -> list[PlanSummary]

    render_plan_markdown(plan) -> str
    render_plan_pdf(plan, output_path) -> Path
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fpdf import FPDF
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

# NOTE: Both answer and judge use llama3.2 — Ollama has no separate small model by default
ANSWER_MODEL = "llama3.2"
JUDGE_MODEL = "llama3.2"

HERE = Path(__file__).parent.parent  # labs/ directory (not labs/ollama/)
PROFILES_DIR = HERE / "farm_profiles"
PLANS_DIR = HERE / "farm_plans"
KNOWLEDGE_BASE_PATH = HERE / "agritech" / "telangana_knowledge_base.md"

PROFILES_DIR.mkdir(exist_ok=True)
PLANS_DIR.mkdir(exist_ok=True)


def _load_knowledge_base() -> str:
    return KNOWLEDGE_BASE_PATH.read_text()


# =====================================================================
# Profile schemas
# =====================================================================

class SoilTestData(BaseModel):
    ph: float | None = None
    nitrogen_kg_ha: float | None = None
    phosphorus_kg_ha: float | None = None
    potassium_kg_ha: float | None = None
    organic_carbon_pct: float | None = None
    notes: str | None = None


class ExistingCrop(BaseModel):
    crop_name: str
    variety: str | None = None
    acres: float
    year_planted: int | None = None
    age_years: float | None = None
    condition: Literal["thriving", "stable", "struggling"] = "stable"


class ExistingLivestock(BaseModel):
    type: Literal["cow", "buffalo", "goat", "poultry", "fish", "duck", "sheep"]
    breed: str | None = None
    count: int


class ApiaryInfo(BaseModel):
    species: Literal["Apis cerana indica", "Apis mellifera", "Trigona"] | None = None
    boxes: int = 0


class FarmProfile(BaseModel):
    # Identity
    farmer_id: str
    name: str
    village: str | None = None
    district: Literal["Suryapet", "Jangaon", "Nalgonda", "Other"] = "Suryapet"
    state: str = "Telangana"
    pincode: str | None = None

    # Land
    total_acres: float
    parcel_count: int = 1
    soil_types_present: list[Literal[
        "red_soil_loam", "red_soil_chalka_sandy", "black_cotton_regur",
        "alluvial", "laterite", "saline_alkaline", "mixed", "unknown",
    ]] = Field(default_factory=list)
    soil_test_done: bool = False
    soil_test_data: SoilTestData | None = None

    # Water
    water_sources: list[Literal[
        "bore_well", "canal", "lift_irrigation", "pond_tank", "rainfed_only"
    ]] = Field(default_factory=list)
    irrigation_infrastructure: list[Literal["drip", "sprinkler", "flood", "none"]] = Field(default_factory=list)
    drought_history_years: list[int] = Field(default_factory=list)

    # Existing
    existing_crops: list[ExistingCrop] = Field(default_factory=list)
    existing_livestock: list[ExistingLivestock] = Field(default_factory=list)
    existing_apiary: ApiaryInfo | None = None

    # Family + labor
    adult_workers: int = 1
    children: int = 0
    hired_labor_available: Literal["family_only", "seasonal_hired", "year_round_hired"] = "family_only"

    # Wildlife
    wildlife_present: list[Literal[
        "monkeys", "wild_boar", "peacocks", "nilgai", "elephants", "birds", "none"
    ]] = Field(default_factory=lambda: ["none"])
    forest_proximity_km: float | None = None
    previous_crop_losses_to_wildlife: list[str] = Field(default_factory=list)

    # Investment + income
    investment_capacity_inr: int = 0
    primary_income_source: Literal["farming_only", "mixed", "salary_with_farm_side"] = "farming_only"

    # Existing infrastructure
    has_drip: bool = False
    has_storage: bool = False
    has_processing_unit: bool = False
    has_cold_storage: bool = False

    # Govt schemes enrolled
    pm_kisan_enrolled: bool = False
    kcc_enrolled: bool = False
    pmfby_enrolled: bool = False
    soil_health_card: bool = False
    rythu_bandhu_received: bool = False

    # Sustainability orientation
    organic_interest: Literal["none", "transitioning", "certified"] = "none"
    zbnf_practitioner: bool = False
    open_to_agroforestry: bool = True

    # Cultural
    primary_language: Literal["Telugu", "Hindi", "English", "other"] = "Telugu"

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =====================================================================
# Planning goals schema (per session)
# =====================================================================

class PlanningGoals(BaseModel):
    primary_goal: Literal[
        "stable_monthly_income",
        "asset_building_long_term",
        "subsistence_first",
        "max_revenue_per_acre",
        "diversification_resilience",
        "transition_to_organic",
        "sustainability_focused",
    ] = "diversification_resilience"
    # Risk profile drives multi-option generation: conservative = lower risk,
    # smaller perennial bets, more food security; balanced = mid; aggressive =
    # bigger perennial bets, more exotic crops, larger upside / variance.
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    secondary_goals: list[str] = Field(default_factory=list)
    planning_horizon_years: Literal[1, 3, 5, 10] = 10

    # Constraints
    max_investment_inr: int = 500_000
    min_food_security: bool = False
    must_use_existing_infrastructure: bool = False
    organic_required: bool = False
    avoid_chemical_pesticides: bool = False
    water_use_priority: Literal["minimize", "moderate", "unconstrained"] = "moderate"

    # Mixed farming additions
    include_dairy: bool = False
    include_apiary: bool = False
    include_poultry: bool = False
    include_fish: bool = False
    include_sericulture: bool = False
    include_mushroom: bool = False

    # Exotic crops interest
    interested_exotic_crops: list[str] = Field(default_factory=list)
    other_exotic_interest: str = ""

    # Risk + rollout
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate"
    pilot_first: bool = True


# =====================================================================
# FarmPlan output schema
# =====================================================================

class CropInPlan(BaseModel):
    crop_name: str
    variety: str | None = None
    local_name: str | None = None
    role: Literal["short_term_cash_crop", "medium_term_crop",
                  "perennial_anchor", "intercrop", "boundary_crop"]
    acres_allocated: float
    time_to_first_yield_years: float
    peak_production_year_start: int
    peak_production_year_end: int
    expected_yield_per_acre: str
    revenue_per_acre_at_peak_inr: str
    year_1_investment_inr: str
    annual_maintenance_inr: str
    breakeven_year: int
    suitable_for_climate: bool
    climate_concerns: list[str] = Field(default_factory=list)
    soil_requirements: list[str] = Field(default_factory=list)
    disease_risks: list[str] = Field(default_factory=list)
    pest_risks: list[str] = Field(default_factory=list)
    market_channels: list[str] = Field(default_factory=list)
    seasonal_price_windows: str = ""
    govt_subsidies_available: list[str] = Field(default_factory=list)
    suppliers_known: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    why_it_fits: list[str] = Field(default_factory=list)
    pairs_well_with: list[str] = Field(default_factory=list)
    organic_compatible: bool = True
    pollinator_friendly: bool = False
    is_exotic_high_value: bool = False
    export_potential: Literal["none", "domestic_metro", "international"] = "domestic_metro"
    value_addition_options: list[str] = Field(default_factory=list)
    confidence_self: float = 0.0
    confidence_meta: float = 0.0


class LivestockInPlan(BaseModel):
    type: Literal["dairy_cow", "buffalo", "goat", "poultry_backyard", "poultry_commercial",
                  "fish", "duck"]
    breed: str
    count: int
    space_required_sqft: int
    daily_feed_kg: float
    monthly_revenue_inr_range: str
    monthly_cost_inr_range: str
    monthly_net_inr_range: str
    integration_with_crops: list[str] = Field(default_factory=list)
    breakeven_months: int
    govt_schemes_applicable: list[str] = Field(default_factory=list)
    confidence_self: float = 0.0
    confidence_meta: float = 0.0


class ApiaryInPlan(BaseModel):
    bee_species: Literal["Apis mellifera", "Apis cerana indica", "Trigona"]
    bee_box_count: int
    placement_strategy: str
    expected_yield_kg_per_box_per_year: float
    expected_revenue_inr_per_year: str
    pollination_benefit_to_crops: list[str] = Field(default_factory=list)
    midh_subsidy_eligibility: bool = True
    confidence_self: float = 0.0
    confidence_meta: float = 0.0


class SustainabilityPractice(BaseModel):
    practice: Literal[
        "crop_rotation", "intercropping", "cover_crops", "composting",
        "vermicomposting", "biogas", "rainwater_harvesting", "solar_pump",
        "agroforestry", "alley_cropping", "permaculture_swales",
        "zbnf_practices", "carbon_sequestration", "soil_health_monitoring",
        "mulching", "green_manure", "drip_irrigation",
    ]
    why_it_fits: str
    investment_inr: str
    payback_period: str
    soil_health_impact: Literal["high", "medium", "low"] = "medium"
    water_savings_pct: float | None = None
    govt_schemes_applicable: list[str] = Field(default_factory=list)
    confidence_self: float = 0.0


class YearlyCashFlow(BaseModel):
    year: int
    investment_inr_total: str
    revenue_inr_range: str
    net_inr_range: str
    notes: str = ""


class PlanCritique(BaseModel):
    """Devil's advocate per plan — honest about why the plan might NOT work.
    Same shape Session 19's red-team auditor uses, applied to a farm plan."""
    why_it_might_work: list[str] = Field(
        description="3-5 concrete reasons this plan is likely to succeed in THIS farmer's context.")
    why_it_might_NOT_work: list[str] = Field(
        description="3-5 honest failure modes — concrete things that could break this plan, "
                    "specific to this farmer's profile (not generic advice).")
    key_assumptions: list[str] = Field(
        description="3-5 explicit assumptions the plan makes — what would invalidate it if it changed "
                    "(market prices stay in current band, no disease outbreak, KVK support available, etc.).")
    biggest_risk: str = Field(description="One sentence — the single largest risk to this plan.")
    overall_confidence: float = Field(ge=0.0, le=1.0,
        description="0.0-1.0 calibrated confidence the plan delivers the stated goals over the planning horizon. "
                    "Be honest — over-confidence is the failure mode.")


class PlanOption(BaseModel):
    """One of N plans presented to the farmer — comes with its critique."""
    risk_profile: Literal["conservative", "balanced", "aggressive"]
    plan: "FarmPlan"
    critique: PlanCritique


class FarmPlanResult(BaseModel):
    """Multi-option output — 1 or 3 plans, with a recommendation."""
    farmer_id: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    profile_summary: str
    options: list[PlanOption]
    recommended_option: Literal["conservative", "balanced", "aggressive"]
    recommendation_reasoning: str = Field(
        description="One paragraph — why this risk profile fits THIS farmer's profile + goals + context.")


class FarmPlan(BaseModel):
    plan_id: str
    farmer_id: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    plan_summary: str
    farmer_profile_inferred: str
    crops: list[CropInPlan]
    livestock: list[LivestockInPlan] = Field(default_factory=list)
    apiary: ApiaryInPlan | None = None
    sustainability_practices: list[SustainabilityPractice] = Field(default_factory=list)
    year_by_year_cash_flow: list[YearlyCashFlow] = Field(default_factory=list)
    risk_diversification_strategy: str = ""
    sustainability_score: float = 0.0
    organic_transition_path: str | None = None
    govt_subsidies_to_pursue: list[str] = Field(default_factory=list)
    suppliers_to_contact: list[str] = Field(default_factory=list)
    market_channels_to_develop: list[str] = Field(default_factory=list)
    immediate_next_steps: list[str] = Field(default_factory=list)
    pilot_recommendation: str | None = None
    disclaimers: list[str] = Field(default_factory=list)


# =====================================================================
# Profile I/O
# =====================================================================

class ProfileSummary(BaseModel):
    farmer_id: str
    name: str
    district: str
    total_acres: float
    updated_at: str


def list_profiles() -> list[ProfileSummary]:
    summaries: list[ProfileSummary] = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            summaries.append(ProfileSummary(
                farmer_id=data["farmer_id"],
                name=data.get("name", "(no name)"),
                district=data.get("district", "Suryapet"),
                total_acres=data.get("total_acres", 0),
                updated_at=data.get("updated_at", ""),
            ))
        except (KeyError, json.JSONDecodeError):
            continue
    return sorted(summaries, key=lambda s: s.updated_at, reverse=True)


def load_profile(farmer_id: str) -> FarmProfile:
    path = PROFILES_DIR / f"{farmer_id}.json"
    return FarmProfile.model_validate_json(path.read_text())


def save_profile(profile: FarmProfile) -> Path:
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    path = PROFILES_DIR / f"{profile.farmer_id}.json"
    path.write_text(profile.model_dump_json(indent=2))
    return path


def delete_profile(farmer_id: str) -> None:
    path = PROFILES_DIR / f"{farmer_id}.json"
    if path.exists():
        path.unlink()


def make_farmer_id() -> str:
    return f"farmer_{uuid4().hex[:8]}"


# =====================================================================
# Plan I/O
# =====================================================================

class PlanSummary(BaseModel):
    plan_id: str
    farmer_id: str
    generated_at: str
    summary: str
    crop_count: int
    sustainability_score: float


def save_plan(plan: FarmPlan) -> Path:
    farmer_dir = PLANS_DIR / plan.farmer_id
    farmer_dir.mkdir(exist_ok=True)
    path = farmer_dir / f"{plan.plan_id}.json"
    path.write_text(plan.model_dump_json(indent=2))
    return path


def load_plan(farmer_id: str, plan_id: str) -> FarmPlan:
    path = PLANS_DIR / farmer_id / f"{plan_id}.json"
    return FarmPlan.model_validate_json(path.read_text())


def load_plans_for_farmer(farmer_id: str) -> list[PlanSummary]:
    farmer_dir = PLANS_DIR / farmer_id
    if not farmer_dir.exists():
        return []
    plans: list[PlanSummary] = []
    for f in farmer_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            plans.append(PlanSummary(
                plan_id=data["plan_id"],
                farmer_id=data["farmer_id"],
                generated_at=data["generated_at"],
                summary=data["plan_summary"][:200],
                crop_count=len(data.get("crops", [])),
                sustainability_score=data.get("sustainability_score", 0),
            ))
        except (KeyError, json.JSONDecodeError):
            continue
    return sorted(plans, key=lambda p: p.generated_at, reverse=True)


# =====================================================================
# The LLM call
# =====================================================================

SYSTEM_PROMPT_TEMPLATE = """You are a senior farm-planning advisor for the
Suryapet / Jangaon / Nalgonda region of Telangana, India.

You have authoritative knowledge of:
- Telangana climate, soil, market structure
- Variety-level crop economics (lemon, avocado, dragon fruit, mango, etc.)
- Mixed farming (dairy, apiary, poultry, fish, sericulture, mushroom)
- Sustainability practices (ZBNF, agroforestry, drip, biogas, solar)
- Govt schemes (PM-KISAN, Rythu Bandhu, MIDH, NLM, PM-KUSUM, etc.)
- Suppliers + market channels

Embedded knowledge base below — treat as authoritative for variety names,
economics, suppliers, schemes. Do NOT recommend Hass avocado for Telangana
(climate fails). Do NOT generate crops without checking the climate / soil /
wildlife constraints from the profile.

Style:
- Opinionated. Pick ONE concrete recommendation per question. No hedging.
- Specific numbers (Rs. ranges, kg yields, breakeven years), not platitudes.
- Variety-level granularity. Say "Thailand Lemon" not "lemon".
- Honest about confidence — use the calibration guide in the knowledge base.

KNOWLEDGE BASE (authoritative, do not contradict):
==================================================
{knowledge_base}
==================================================
"""


def _build_system_prompt() -> str:
    """Build the system prompt as a plain string."""
    knowledge = _load_knowledge_base()
    return SYSTEM_PROMPT_TEMPLATE.format(knowledge_base=knowledge)


# =====================================================================
# Multi-call schemas — each section a subset of FarmPlan
# =====================================================================

class CorePlanSection(BaseModel):
    """Legacy combined section — kept for backwards compat."""
    plan_summary: str = Field(description="One-paragraph overview of the plan.")
    farmer_profile_inferred: str = Field(description="One-paragraph synthesis of the profile.")
    crops: list[CropInPlan] = Field(description="3-6 crops balancing short/medium/perennial time horizons.")
    livestock: list[LivestockInPlan] = Field(default_factory=list)
    apiary: ApiaryInPlan | None = None
    risk_diversification_strategy: str = Field(default="",
        description="How the crop + livestock + apiary mix hedges risk.")


class ProfileSynthesisSection(BaseModel):
    """Fast first node: synthesize the profile + state the strategy in plain English."""
    plan_summary: str = Field(description="One-paragraph overview of the plan you'll recommend.")
    farmer_profile_inferred: str = Field(description="One-paragraph synthesis of the farmer's situation.")
    risk_diversification_strategy: str = Field(
        description="How the eventual crop + livestock mix will hedge risk.")


class CropSelectionSection(BaseModel):
    """Crops only — the biggest LLM output, isolated for reliability."""
    crops: list[CropInPlan] = Field(
        description="3-6 crops balancing short-term cash crops / medium-term / perennials / boundary. "
                    "Variety-level granularity. Match to climate + soil + wildlife + labor + investment.")


class LivestockApiarySection(BaseModel):
    """Livestock + apiary — only emitted when goals request them."""
    livestock: list[LivestockInPlan] = Field(default_factory=list,
        description="Livestock recommendations (dairy, poultry, fish, etc.) IF goals include them.")
    apiary: ApiaryInPlan | None = Field(default=None,
        description="Apiary plan IF goals.include_apiary is true. Otherwise None.")


class SustainabilitySection(BaseModel):
    """Call 2 output: regenerative practices + organic path + logistics."""
    sustainability_practices: list[SustainabilityPractice] = Field(
        description="3-6 specific practices (ZBNF, drip, biogas, agroforestry, etc.) "
                    "matched to this profile's soil/water/labor.")
    organic_transition_path: str | None = Field(default=None,
        description="If organic is a goal, the concrete 3-year PGS-India / NPOP path. "
                    "Otherwise None.")
    govt_subsidies_to_pursue: list[str] = Field(
        description="Specific schemes + their application paths (MIDH drip, Rythu Bandhu, "
                    "NLM indigenous breed, PMFBY, etc.)")
    suppliers_to_contact: list[str] = Field(
        description="Specific organizations + locations (SKLTSHU Rajendranagar, Deccan Exotics "
                    "Hyderabad, KVK Suryapet, etc.)")
    market_channels_to_develop: list[str] = Field(
        description="Wholesale + retail + processing channels relevant to the crops.")


class CashFlowSection(BaseModel):
    """Call 3 output: 10-year cash flow + concrete next steps + disclaimers."""
    year_by_year_cash_flow: list[YearlyCashFlow] = Field(
        description="10 yearly entries (Y1..Y10) with investment, revenue, net, notes. "
                    "Reflect the perennial breakeven timeline.")
    immediate_next_steps: list[str] = Field(
        description="3-6 concrete actions for the next 30 days (place seedling orders, "
                    "soil test, contact KVK, apply for MIDH, etc.)")
    pilot_recommendation: str | None = Field(default=None,
        description="If any crop should start as a small pilot (0.25-1 ac) before scaling.")
    disclaimers: list[str] = Field(
        description="2-4 disclaimers covering: KVK validation requirement, market uncertainty, "
                    "wildlife variability, weather risk.")


def _make_planner_model(timeout: int = 600) -> ChatOllama:
    return ChatOllama(
        model=ANSWER_MODEL,
        timeout=timeout,
        temperature=0,
    )


def _call_with_retry(planner, system_prompt, user_prompt, max_retries=3,
                     label: str = "call"):
    """Generic retry wrapper for the structured-output planner calls."""
    last_err: Exception | None = None
    backoff_seconds = [0, 10, 30, 60]
    for attempt in range(max_retries):
        if attempt > 0:
            wait = backoff_seconds[min(attempt, len(backoff_seconds) - 1)]
            print(f"[engine] {label}: backing off {wait}s before retry {attempt + 1}...")
            time.sleep(wait)
        try:
            return planner.invoke([
                SystemMessage(system_prompt),
                HumanMessage(user_prompt),
            ])
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"[engine] {label}: transient error on attempt {attempt + 1}: "
                      f"{type(e).__name__} — will retry...")
    raise last_err


def generate_farm_plan_multicall(profile: FarmProfile, goals: PlanningGoals,
                                 max_retries: int = 3) -> FarmPlan:
    """Multi-call planner — three sequential structured-output calls.

    Recovers the cash-flow + sustainability-practices fields that the single
    call drops under output pressure.

    Note: Ollama handles KV cache internally — no client-side cache_control needed.
    """
    model = _make_planner_model()
    system_prompt = _build_system_prompt()

    # ---- Call 1: core plan (crops + livestock + apiary + summary) ----
    print("[engine] multicall: call 1/3 — core plan (crops + livestock + apiary)...")
    core_planner = model.with_structured_output(CorePlanSection)
    call1_prompt = (
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        "Generate the CORE plan section: plan_summary, farmer_profile_inferred, "
        "crops (3-6 with variety-level detail), livestock (if include_dairy/poultry/fish "
        "set in goals), apiary (if include_apiary). Match crops to the profile's climate "
        "district, soil, water, wildlife pressure, labor, investment, and stated goals. "
        "Use the embedded knowledge base for varieties, suppliers, schemes, and economics."
    )
    section1: CorePlanSection = _call_with_retry(
        core_planner, system_prompt, call1_prompt, max_retries, label="call1"
    )
    print(f"[engine] call 1 done: {len(section1.crops)} crops, "
          f"{len(section1.livestock)} livestock, apiary={'yes' if section1.apiary else 'no'}")

    # ---- Call 2: sustainability + logistics ----
    print("[engine] multicall: call 2/3 — sustainability + subsidies + suppliers...")
    sust_planner = model.with_structured_output(SustainabilitySection)
    call2_prompt = (
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"CORE PLAN ALREADY DECIDED (do not contradict — extend with):\n"
        f"{section1.model_dump_json(indent=2)}\n\n"
        "Now generate the SUSTAINABILITY + LOGISTICS section: sustainability_practices "
        "(3-6 specific practices like ZBNF, drip, biogas, agroforestry — matched to this "
        "profile + goals), organic_transition_path (if organic is goal), "
        "govt_subsidies_to_pursue (concrete schemes), suppliers_to_contact "
        "(named orgs), market_channels_to_develop. Be specific."
    )
    section2: SustainabilitySection = _call_with_retry(
        sust_planner, system_prompt, call2_prompt, max_retries, label="call2"
    )
    print(f"[engine] call 2 done: {len(section2.sustainability_practices)} practices, "
          f"{len(section2.govt_subsidies_to_pursue)} subsidies")

    # ---- Call 3: cash flow + next steps ----
    print("[engine] multicall: call 3/3 — 10-year cash flow + next steps...")
    cf_planner = model.with_structured_output(CashFlowSection)
    horizon = goals.planning_horizon_years
    call3_prompt = (
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"CORE PLAN:\n{section1.model_dump_json(indent=2)}\n\n"
        f"SUSTAINABILITY + LOGISTICS:\n{section2.model_dump_json(indent=2)}\n\n"
        f"Generate the CASH FLOW + ACTIONS section for the {horizon}-year horizon. "
        f"year_by_year_cash_flow must have entries for Y1 through Y{horizon} reflecting "
        "the perennial breakeven timeline (e.g., lemon Y4, avocado Y5, dragon fruit Y2-3). "
        "Each YearlyCashFlow needs investment_inr_total, revenue_inr_range, net_inr_range, "
        "and a notes field explaining what's happening that year. "
        "immediate_next_steps: 3-6 concrete 30-day actions. "
        "pilot_recommendation: if applicable. "
        "disclaimers: KVK validation, market uncertainty, weather risk, wildlife variability."
    )
    section3: CashFlowSection = _call_with_retry(
        cf_planner, system_prompt, call3_prompt, max_retries, label="call3"
    )
    print(f"[engine] call 3 done: {len(section3.year_by_year_cash_flow)} cash-flow years, "
          f"{len(section3.immediate_next_steps)} next steps")

    # ---- Stitch into a complete FarmPlan ----
    plan = FarmPlan(
        plan_id=f"plan_{uuid4().hex[:8]}",
        farmer_id=profile.farmer_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        plan_summary=section1.plan_summary,
        farmer_profile_inferred=section1.farmer_profile_inferred,
        crops=section1.crops,
        livestock=section1.livestock,
        apiary=section1.apiary,
        sustainability_practices=section2.sustainability_practices,
        year_by_year_cash_flow=section3.year_by_year_cash_flow,
        risk_diversification_strategy=section1.risk_diversification_strategy,
        organic_transition_path=section2.organic_transition_path,
        govt_subsidies_to_pursue=section2.govt_subsidies_to_pursue,
        suppliers_to_contact=section2.suppliers_to_contact,
        market_channels_to_develop=section2.market_channels_to_develop,
        immediate_next_steps=section3.immediate_next_steps,
        pilot_recommendation=section3.pilot_recommendation,
        disclaimers=section3.disclaimers,
    )
    return plan


# =====================================================================
# LangGraph engine — multi-call as a StateGraph
#
# Same 3 LLM calls as the linear multi-call path, but expressed as a graph:
# core -> sustainability -> cashflow -> assemble -> critique. Benefits:
#   - graph.stream() emits per-node events for UI progress display
#   - SqliteSaver checkpointer persists state per node (resume on crash)
#   - easy to add new nodes (eval, vision diagnostic in Session 23, etc.)
#   - per-node retry logic is local
#
# The critique node is the devil's advocate — honest about why the plan
# might NOT work, not just why it will. Same red-team discipline as
# Session 19, applied to farm plans.
# =====================================================================

from typing import TypedDict, Annotated
from operator import add as _list_add

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Send
    from langgraph.checkpoint.sqlite import SqliteSaver
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

import operator
from typing import Annotated as _Annotated


CHECKPOINT_DB_PATH = HERE / "farm_plans" / "checkpoints.sqlite"


def _get_checkpointer():
    """Lazy-initialize SqliteSaver. Returns None if langgraph not installed."""
    if not _LANGGRAPH_AVAILABLE:
        return None
    return SqliteSaver.from_conn_string(str(CHECKPOINT_DB_PATH))


# =====================================================================
# ChatOllama structured-output helper
#
# Replaces the native Anthropic SDK helper from the original file.
# Uses ChatOllama.with_structured_output() which calls Ollama's
# tool/function-calling API. No cache_control — Ollama handles KV
# cache internally without client-side configuration.
# =====================================================================

def _call_ollama_structured(
    schema_model: type[BaseModel],
    user_prompt: str,
    label: str = "call",
    max_retries: int = 3,
) -> BaseModel:
    """Call Ollama with structured output via ChatOllama.with_structured_output().

    Returns a validated instance of `schema_model`. Retries on transient errors.
    Note: Ollama handles KV cache internally — no cache_control needed.
    """
    system_prompt = _build_system_prompt()
    planner = _make_planner_model().with_structured_output(schema_model)

    last_err: Exception | None = None
    backoff = [0, 10, 30, 60]
    for attempt in range(max_retries):
        if attempt > 0:
            wait = backoff[min(attempt, len(backoff) - 1)]
            print(f"[ollama] {label}: backing off {wait}s before retry {attempt + 1}...")
            time.sleep(wait)
        try:
            result = planner.invoke([
                SystemMessage(system_prompt),
                HumanMessage(user_prompt),
            ])
            print(f"[ollama] {label}: completed")
            return result
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"[ollama] {label}: {type(e).__name__} on attempt "
                      f"{attempt + 1} — will retry...")
    raise last_err


# =====================================================================
# Per-crop generation schemas + nodes
# =====================================================================

class CropIntentItem(BaseModel):
    """One crop the advisor plans to include — name + role + variety hint."""
    crop_name: str = Field(description="Common crop name, e.g. 'Thailand Lemon', 'Bt Cotton', 'Ragi'.")
    variety_hint: str | None = Field(default=None,
        description="Variety / cultivar hint, e.g. 'NHH 44', 'PKM-1', 'Fuerte'. "
                    "Leave None if undecided.")
    role: Literal["short_term_cash_crop", "medium_term_crop",
                  "perennial_anchor", "intercrop", "boundary_crop"]
    acres_allocated: float = Field(description="Acres allocated to this crop.")
    rationale_for_inclusion: str = Field(description="One sentence: why this crop.")


class CropIntentSection(BaseModel):
    """Output of crop_intent node — just the LIST of crops to detail."""
    crops_planned: list[CropIntentItem] = Field(
        description="3-6 crops to include in the plan, balancing time horizons. "
                    "Each gets fully detailed in the next stage."
    )


class PlanGraphState(TypedDict, total=False):
    """State threading through the per-option planning graph."""
    profile: FarmProfile
    goals: PlanningGoals
    risk_profile: str        # "conservative" | "balanced" | "aggressive"
    # LLM-call outputs — 3 small core sections (replaces single CorePlanSection)
    profile_synthesis: ProfileSynthesisSection
    crop_intent: CropIntentSection
    crop_details: _Annotated[list[CropInPlan], operator.add]
    crop_selection: CropSelectionSection
    livestock_apiary: LivestockApiarySection
    # Legacy combined section (for backwards compat)
    core: CorePlanSection
    sustainability: SustainabilitySection
    cashflow: CashFlowSection
    # Assembled artifacts
    plan: FarmPlan
    critique: PlanCritique


def _risk_profile_instruction(risk_profile: str) -> str:
    """Bias prompt language per risk profile."""
    return {
        "conservative": (
            "RISK PROFILE: CONSERVATIVE. Bias toward: food security first, low Year-1 investment, "
            "more short-term cash crops (millets, pulses), small perennial pilots only "
            "(0.25-0.5 ac), avoid exotic / experimental crops. Optimize for stable income, "
            "not maximum upside."
        ),
        "balanced": (
            "RISK PROFILE: BALANCED. Mix of short-term cash crops, established perennials "
            "(lemon, mango), and 1-2 small exotic pilots. Standard MIDH-grade investments. "
            "Optimize for stable income + asset building."
        ),
        "aggressive": (
            "RISK PROFILE: AGGRESSIVE. Lean into perennials + exotic high-value crops "
            "(dragon fruit, avocado, pomegranate, dates). Larger Year-1 investment within "
            "the cap. Optimize for upside; accept higher variance + longer payback windows. "
            "Multiple pilots OK."
        ),
    }.get(risk_profile, "")


# ---------- LangGraph nodes ----------

def _node_profile_synthesis(state: PlanGraphState) -> dict:
    """First node: synthesize the profile + state the strategy. Small + fast."""
    profile = state["profile"]
    goals = state["goals"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        "Generate ONLY the ProfileSynthesisSection: a one-paragraph plan_summary "
        "(what you're going to recommend overall), a one-paragraph farmer_profile_inferred "
        "(synthesis of the situation), and risk_diversification_strategy. Keep this section concise."
    )
    result = _call_ollama_structured(
        ProfileSynthesisSection, prompt,
        label=f"{risk_profile}:profile_synth",
    )
    return {"profile_synthesis": result}


def _node_crop_intent(state: PlanGraphState) -> dict:
    """Tiny LLM call that just NAMES the crops to include (3-6 of them) plus
    variety hint + role + acres."""
    profile = state["profile"]
    goals = state["goals"]
    synth = state["profile_synthesis"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"PROFILE SYNTHESIS:\n{synth.model_dump_json(indent=2)}\n\n"
        "Generate the CropIntentSection — JUST the list of crops you plan to include "
        "in the final plan (3-6 crops). For each crop give: crop_name, variety_hint "
        "(specific cultivar like 'NHH 44' or 'Thailand Lemon'), role "
        "(short_term_cash_crop / medium_term_crop / perennial_anchor / intercrop / boundary_crop), "
        "acres_allocated (must sum to <= profile.total_acres), and a one-sentence "
        "rationale_for_inclusion.\n\n"
        "Match crops to climate / soil / wildlife / labor / investment. "
        "If goals.interested_exotic_crops is non-empty, consider those seriously. "
        "Do NOT generate full crop details yet — just the list."
    )
    result = _call_ollama_structured(
        CropIntentSection, prompt,
        label=f"{risk_profile}:crop_intent",
    )
    return {"crop_intent": result}


def _generate_one_crop_detail(ci: CropIntentItem, profile: FarmProfile,
                              goals: PlanningGoals,
                              synth: ProfileSynthesisSection,
                              risk_profile: str) -> CropInPlan:
    """Generate ONE CropInPlan in detail. Called from `_node_crops_parallel` once
    per CropIntentItem, in parallel via a thread pool."""
    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE (relevant fields):\n"
        f"  district: {profile.district}\n"
        f"  total_acres: {profile.total_acres}\n"
        f"  soil_types: {profile.soil_types_present}\n"
        f"  water_sources: {profile.water_sources}\n"
        f"  irrigation: {profile.irrigation_infrastructure}\n"
        f"  wildlife: {profile.wildlife_present}\n"
        f"  forest_proximity_km: {profile.forest_proximity_km}\n"
        f"  organic_interest: {profile.organic_interest}\n\n"
        f"PLAN SUMMARY:\n{synth.plan_summary}\n\n"
        f"CROP TO DETAIL:\n"
        f"  crop_name: {ci.crop_name}\n"
        f"  variety_hint: {ci.variety_hint}\n"
        f"  role: {ci.role}\n"
        f"  acres_allocated: {ci.acres_allocated}\n"
        f"  rationale: {ci.rationale_for_inclusion}\n\n"
        f"Generate a COMPLETE CropInPlan for THIS ONE CROP. Fill EVERY field with "
        f"variety-level specificity (crop_name, variety, role, acres_allocated, "
        f"time_to_first_yield_years, peak_production_year_start/end, breakeven_year, "
        f"expected_yield_per_acre, revenue_per_acre_at_peak_inr, year_1_investment_inr, "
        f"annual_maintenance_inr, climate_concerns, soil_requirements, disease_risks, "
        f"pest_risks, market_channels, seasonal_price_windows, govt_subsidies_available, "
        f"suppliers_known, risk_flags, why_it_fits, pairs_well_with, organic_compatible, "
        f"pollinator_friendly, is_exotic_high_value, export_potential, value_addition_options, "
        f"confidence_self, confidence_meta). Use the KB for variety, supplier, scheme references."
    )
    return _call_ollama_structured(
        CropInPlan, prompt,
        label=f"{risk_profile}:crop_detail:{ci.crop_name[:20]}",
    )


def _node_crops_parallel(state: PlanGraphState) -> dict:
    """Run all crop_detail calls in PARALLEL via a thread pool — one LangGraph
    node, internally concurrent."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    profile = state["profile"]
    goals = state["goals"]
    synth = state["profile_synthesis"]
    intent = state["crop_intent"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    if not intent.crops_planned:
        return {"crop_selection": CropSelectionSection(crops=[])}

    max_workers = min(len(intent.crops_planned), 6)
    print(f"[engine] crops_parallel: {len(intent.crops_planned)} crops in pool of {max_workers}")
    crops: list[CropInPlan] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_generate_one_crop_detail, ci, profile, goals, synth, risk_profile): ci
            for ci in intent.crops_planned
        }
        for future in as_completed(futures):
            ci = futures[future]
            try:
                crop = future.result()
                crops.append(crop)
                print(f"[engine] crops_parallel: ok {ci.crop_name}")
            except Exception as e:
                print(f"[engine] crops_parallel: failed {ci.crop_name} — {type(e).__name__}: {e}")
                # If a crop fails, continue with the others — don't fail the whole plan

    return {"crop_selection": CropSelectionSection(crops=crops)}


def _node_crop_selection(state: PlanGraphState) -> dict:
    """Legacy single-call crop generation — kept for the legacy build path."""
    profile = state["profile"]
    goals = state["goals"]
    synth = state["profile_synthesis"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"PROFILE SYNTHESIS:\n{synth.model_dump_json(indent=2)}\n\n"
        "Generate the CropSelectionSection: 3-6 crops with FULL variety-level detail."
    )
    result = _call_ollama_structured(
        CropSelectionSection, prompt,
        label=f"{risk_profile}:crop_selection_legacy",
    )
    return {"crop_selection": result}


def _node_livestock_apiary(state: PlanGraphState) -> dict:
    """Livestock + apiary only. Skipped if goals don't request any."""
    profile = state["profile"]
    goals = state["goals"]
    synth = state["profile_synthesis"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    wants_dairy = goals.include_dairy
    wants_apiary = goals.include_apiary
    wants_poultry = goals.include_poultry
    wants_fish = goals.include_fish
    if not any([wants_dairy, wants_apiary, wants_poultry, wants_fish]):
        return {"livestock_apiary": LivestockApiarySection(livestock=[], apiary=None)}

    request_lines = []
    if wants_dairy: request_lines.append("- DAIRY: breed + count (Sahiwal/Gir/Murrah).")
    if wants_apiary: request_lines.append("- APIARY: bee species + box count + placement.")
    if wants_poultry: request_lines.append("- POULTRY: type + count.")
    if wants_fish: request_lines.append("- FISH: species + pond setup.")

    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"PROFILE SYNTHESIS:\n{synth.model_dump_json(indent=2)}\n\n"
        "Generate the LivestockApiarySection. Goals request:\n"
        + "\n".join(request_lines) + "\n\n"
        "Use indigenous + heat-tolerant breeds. For apiary, place hives within 100-200m "
        "of flowering crops. Include monthly net + integration_with_crops + govt schemes (NLM, MIDH)."
    )
    result = _call_ollama_structured(
        LivestockApiarySection, prompt,
        label=f"{risk_profile}:livestock_apiary",
    )
    return {"livestock_apiary": result}


def _node_core(state: PlanGraphState) -> dict:
    """Legacy single-call core node — preserved for non-graph callers."""
    profile = state["profile"]
    goals = state["goals"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    model = _make_planner_model()
    planner = model.with_structured_output(CorePlanSection)
    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        "Generate the CORE plan section: plan_summary, farmer_profile_inferred, "
        "crops (3-6 with variety-level detail), livestock, apiary, "
        "risk_diversification_strategy."
    )
    result = _call_with_retry(planner, _build_system_prompt(), prompt,
                              label=f"{risk_profile}:core")
    return {"core": result}


def _node_sustainability(state: PlanGraphState) -> dict:
    """Sustainability + logistics."""
    profile = state["profile"]
    goals = state["goals"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    if "profile_synthesis" in state and "crop_selection" in state:
        synth = state["profile_synthesis"]
        crops = state["crop_selection"]
        la = state.get("livestock_apiary", LivestockApiarySection())
        core_ctx = (
            f"SYNTHESIS: {synth.plan_summary}\n"
            f"CROPS: {[c.crop_name + (' (' + c.variety + ')' if c.variety else '') for c in crops.crops]}\n"
            f"LIVESTOCK: {[(l.type, l.breed, l.count) for l in la.livestock]}\n"
            f"APIARY: {la.apiary.bee_species + ' x ' + str(la.apiary.bee_box_count) if la.apiary else 'none'}"
        )
    else:
        core_ctx = state["core"].model_dump_json(indent=2)

    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"CORE PLAN ALREADY DECIDED:\n{core_ctx}\n\n"
        "Generate SUSTAINABILITY + LOGISTICS: 3-6 sustainability_practices, "
        "organic_transition_path (if applicable), govt_subsidies_to_pursue, "
        "suppliers_to_contact, market_channels_to_develop."
    )
    result = _call_ollama_structured(
        SustainabilitySection, prompt,
        label=f"{risk_profile}:sustainability",
    )
    return {"sustainability": result}


def _node_cashflow(state: PlanGraphState) -> dict:
    profile = state["profile"]
    goals = state["goals"]
    sust = state["sustainability"]
    risk_profile = state.get("risk_profile", goals.risk_profile)
    horizon = goals.planning_horizon_years

    if "crop_selection" in state:
        crops_summary = "\n".join(
            f"- {c.crop_name}{' (' + c.variety + ')' if c.variety else ''} . {c.role} . "
            f"{c.acres_allocated} ac . Y1 Rs.{c.year_1_investment_inr} . breakeven Y{c.breakeven_year} "
            f". peak Y{c.peak_production_year_start}-{c.peak_production_year_end}"
            for c in state["crop_selection"].crops
        )
        la = state.get("livestock_apiary", LivestockApiarySection())
        livestock_summary = "\n".join(
            f"- {l.type} {l.breed} x{l.count} . monthly net {l.monthly_net_inr_range}"
            for l in la.livestock
        )
        apiary_summary = (
            f"- {la.apiary.bee_species} x {la.apiary.bee_box_count} boxes . "
            f"{la.apiary.expected_revenue_inr_per_year} yearly"
        ) if la.apiary else ""
        core_ctx = (
            f"CROPS:\n{crops_summary}\n\n"
            f"LIVESTOCK:\n{livestock_summary or '(none)'}\n\n"
            f"APIARY:\n{apiary_summary or '(none)'}"
        )
    else:
        core_ctx = state["core"].model_dump_json(indent=2)

    prompt = (
        f"{_risk_profile_instruction(risk_profile)}\n\n"
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        f"CORE PLAN ALREADY DECIDED:\n{core_ctx}\n\n"
        f"SUSTAINABILITY:\n{sust.model_dump_json(indent=2)}\n\n"
        f"Generate CASH FLOW + ACTIONS for the {horizon}-year horizon. "
        f"year_by_year_cash_flow MUST have entries Y1..Y{horizon} reflecting perennial "
        "breakeven timelines. immediate_next_steps (3-6 30-day actions), pilot_recommendation, disclaimers."
    )
    result = _call_ollama_structured(
        CashFlowSection, prompt,
        label=f"{risk_profile}:cashflow",
    )
    return {"cashflow": result}


def _node_assemble(state: PlanGraphState) -> dict:
    """Deterministic stitching — no LLM. Combines either the split sections or
    the legacy single core section."""
    profile = state["profile"]
    sust = state["sustainability"]
    cf = state["cashflow"]

    if "profile_synthesis" in state and "crop_selection" in state:
        # New path — 3 split sections
        synth = state["profile_synthesis"]
        crops_section = state["crop_selection"]
        la = state.get("livestock_apiary", LivestockApiarySection())
        plan_summary = synth.plan_summary
        farmer_profile_inferred = synth.farmer_profile_inferred
        risk_strategy = synth.risk_diversification_strategy
        crops = crops_section.crops
        livestock = la.livestock
        apiary = la.apiary
    else:
        # Legacy combined core
        core = state["core"]
        plan_summary = core.plan_summary
        farmer_profile_inferred = core.farmer_profile_inferred
        risk_strategy = core.risk_diversification_strategy
        crops = core.crops
        livestock = core.livestock
        apiary = core.apiary

    plan = FarmPlan(
        plan_id=f"plan_{uuid4().hex[:8]}",
        farmer_id=profile.farmer_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        plan_summary=plan_summary,
        farmer_profile_inferred=farmer_profile_inferred,
        crops=crops,
        livestock=livestock,
        apiary=apiary,
        sustainability_practices=sust.sustainability_practices,
        year_by_year_cash_flow=cf.year_by_year_cash_flow,
        risk_diversification_strategy=risk_strategy,
        organic_transition_path=sust.organic_transition_path,
        govt_subsidies_to_pursue=sust.govt_subsidies_to_pursue,
        suppliers_to_contact=sust.suppliers_to_contact,
        market_channels_to_develop=sust.market_channels_to_develop,
        immediate_next_steps=cf.immediate_next_steps,
        pilot_recommendation=cf.pilot_recommendation,
        disclaimers=cf.disclaimers,
    )
    return {"plan": plan}


def _node_critique(state: PlanGraphState) -> dict:
    """Devil's advocate — honest critique of the just-assembled plan."""
    profile = state["profile"]
    goals = state["goals"]
    plan = state["plan"]
    risk_profile = state.get("risk_profile", goals.risk_profile)

    prompt = (
        f"You are playing DEVIL'S ADVOCATE. The following farm plan was generated for "
        f"a {risk_profile} risk profile. Your job is to find honest failure modes — "
        f"NOT to validate the plan. Be specific to THIS farmer's context.\n\n"
        f"FARMER PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLAN:\n{plan.model_dump_json(indent=2)}\n\n"
        f"Generate PlanCritique. Be honest. Over-confidence is the failure mode — "
        f"calibrate overall_confidence to reflect real-world delivery risk over the "
        f"{goals.planning_horizon_years}-year horizon."
    )
    result = _call_ollama_structured(
        PlanCritique, prompt,
        label=f"{risk_profile}:critique",
    )
    return {"critique": result}


def build_planner_graph(checkpointer=None):
    """Per-option planning StateGraph with per-crop parallel detailing.

        START
          |
        profile_synthesis                     (small -- names + strategy)
          |
        crop_intent                           (small -- lists crops)
          |---> crops_parallel                 (threaded -- full CropInPlan per crop)
          |                                           |
          +--> livestock_apiary               <-------+
                  (small / skipped)           fan-in -- symmetric superstep
                                          |
                                  sustainability
                                          |
                                       cashflow
                                          |
                                       assemble (deterministic)
                                          |
                                       critique
                                          |
                                         END

    Note: Ollama handles KV cache internally. No cache_control needed on the
    KB system prompt — the runtime reuses computation automatically.
    """
    if checkpointer is None:
        raise RuntimeError("langgraph not installed — `pip install langgraph`")

    g = StateGraph(PlanGraphState)
    g.add_node("profile_synthesis", _node_profile_synthesis)
    g.add_node("crop_intent", _node_crop_intent)
    g.add_node("crops_parallel", _node_crops_parallel)   # threading internally
    g.add_node("livestock_apiary", _node_livestock_apiary)
    g.add_node("sustainability", _node_sustainability)
    g.add_node("cashflow", _node_cashflow)
    g.add_node("assemble", _node_assemble)
    g.add_node("critique", _node_critique)

    # Entry
    g.add_edge(START, "profile_synthesis")
    # profile_synthesis -> crop_intent (gets the crop list first)
    g.add_edge("profile_synthesis", "crop_intent")
    # crop_intent fans out to crops_parallel AND livestock_apiary in the SAME superstep
    g.add_edge("crop_intent", "crops_parallel")
    g.add_edge("crop_intent", "livestock_apiary")
    # Join into sustainability — waits for BOTH crops_parallel AND livestock_apiary
    g.add_edge("crops_parallel", "sustainability")
    g.add_edge("livestock_apiary", "sustainability")
    # Sequential tail
    g.add_edge("sustainability", "cashflow")
    g.add_edge("cashflow", "assemble")
    g.add_edge("assemble", "critique")
    g.add_edge("critique", END)

    return g.compile(checkpointer=checkpointer)


def generate_plan_via_graph(profile: FarmProfile, goals: PlanningGoals,
                             risk_profile: str | None = None,
                             thread_id: str | None = None,
                             use_checkpointer: bool = True) -> tuple[FarmPlan, PlanCritique]:
    """Run the planner StateGraph once. Returns (plan, critique).

    Pass thread_id to resume a crashed run (SqliteSaver restores per-node state).
    """
    checkpointer = _get_checkpointer() if use_checkpointer else None
    if checkpointer is not None:
        with checkpointer as cp:
            graph = build_planner_graph(checkpointer=cp)
            thread_id = thread_id or f"plan_{uuid4().hex[:8]}"
            config = {"configurable": {"thread_id": thread_id}}
            initial = {
                "profile": profile,
                "goals": goals,
                "risk_profile": risk_profile or goals.risk_profile,
            }
            final = graph.invoke(initial, config=config)
    else:
        graph = build_planner_graph(checkpointer=None)
        initial = {
            "profile": profile,
            "goals": goals,
            "risk_profile": risk_profile or goals.risk_profile,
        }
        final = graph.invoke(initial)
    return final["plan"], final["critique"]


def stream_plan_via_graph(profile: FarmProfile, goals: PlanningGoals,
                          risk_profile: str | None = None,
                          thread_id: str | None = None):
    """Generator yielding per-node events for UI streaming progress.

    Each yielded value is a dict {node_name: state_delta}.
    """
    checkpointer = _get_checkpointer()
    if checkpointer is None:
        raise RuntimeError("langgraph not installed — `pip install langgraph`")
    with checkpointer as cp:
        graph = build_planner_graph(checkpointer=cp)
        thread_id = thread_id or f"plan_{uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}
        initial = {
            "profile": profile,
            "goals": goals,
            "risk_profile": risk_profile or goals.risk_profile,
        }
        for event in graph.stream(initial, config=config, stream_mode="updates"):
            yield event


def generate_three_options(profile: FarmProfile,
                           goals: PlanningGoals) -> FarmPlanResult:
    """Generate 3 plans — conservative + balanced + aggressive — plus
    a recommendation pick. Sequential for simplicity.
    """
    options: list[PlanOption] = []
    for rp in ["conservative", "balanced", "aggressive"]:
        print(f"\n[engine] === Generating {rp} option ===")
        plan, critique = generate_plan_via_graph(profile, goals, risk_profile=rp)
        options.append(PlanOption(risk_profile=rp, plan=plan, critique=critique))

    # Recommend the option with highest critique.overall_confidence,
    # tie-broken by primary goal alignment with risk profile.
    best = max(options, key=lambda o: o.critique.overall_confidence)
    goal_alignment = {
        "subsistence_first":              "conservative",
        "stable_monthly_income":          "conservative",
        "diversification_resilience":     "balanced",
        "transition_to_organic":          "balanced",
        "sustainability_focused":         "balanced",
        "asset_building_long_term":       "aggressive",
        "max_revenue_per_acre":           "aggressive",
    }
    suggested = goal_alignment.get(goals.primary_goal, "balanced")
    # If the goal-aligned option's confidence is within 0.05 of the best,
    # pick the goal-aligned one.
    goal_option = next(o for o in options if o.risk_profile == suggested)
    if goal_option.critique.overall_confidence >= best.critique.overall_confidence - 0.05:
        recommended = suggested
        reasoning = (
            f"The {suggested} option aligns with your primary goal "
            f"('{goals.primary_goal}') and its overall confidence "
            f"({goal_option.critique.overall_confidence:.2f}) is within tolerance of "
            f"the highest-confidence option ({best.risk_profile}, "
            f"{best.critique.overall_confidence:.2f})."
        )
    else:
        recommended = best.risk_profile
        reasoning = (
            f"The {best.risk_profile} option has notably higher confidence "
            f"({best.critique.overall_confidence:.2f}) than the goal-aligned "
            f"{suggested} option ({goal_option.critique.overall_confidence:.2f}). "
            f"Consider this option even though it differs from the typical "
            f"{goals.primary_goal} mapping."
        )

    return FarmPlanResult(
        farmer_id=profile.farmer_id,
        profile_summary=options[0].plan.farmer_profile_inferred,
        options=options,
        recommended_option=recommended,
        recommendation_reasoning=reasoning,
    )


def save_plan_result(result: FarmPlanResult) -> Path:
    """Save the multi-option result + each constituent plan."""
    farmer_dir = PLANS_DIR / result.farmer_id
    farmer_dir.mkdir(exist_ok=True)
    # Save the FarmPlanResult itself
    result_path = farmer_dir / f"result_{uuid4().hex[:8]}.json"
    result_path.write_text(result.model_dump_json(indent=2))
    # Save each plan individually as well (compat with load_plan)
    for opt in result.options:
        save_plan(opt.plan)
    return result_path


def generate_farm_plan(profile: FarmProfile, goals: PlanningGoals,
                       max_retries: int = 3,
                       use_multicall: bool = True) -> FarmPlan:
    """Main entry point. Returns a validated FarmPlan.

    use_multicall=True (default) splits into 3 sequential structured-output
    calls (core / sustainability / cash flow) — recovers fields the single
    call drops under output pressure. Recommended.

    use_multicall=False uses a single call against the full FarmPlan schema —
    faster wall-clock for tiny plans but drops sustainability_practices and
    cash_flow on realistic profiles.
    """
    if use_multicall:
        return generate_farm_plan_multicall(profile, goals, max_retries)

    # Legacy single-call path
    model = _make_planner_model()
    planner = model.with_structured_output(FarmPlan)
    user_prompt = (
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        "Generate a complete FarmPlan. Use the embedded knowledge base."
    )
    plan = _call_with_retry(
        planner, _build_system_prompt(), user_prompt, max_retries, label="single"
    )
    plan.plan_id = f"plan_{uuid4().hex[:8]}"
    plan.farmer_id = profile.farmer_id
    plan.generated_at = datetime.now(timezone.utc).isoformat()
    return plan


# =====================================================================
# Sustainability scoring (deterministic, post-LLM)
# =====================================================================

class SustainabilityScore(BaseModel):
    composite_0_to_100: float
    soil_health_0_to_20: float
    water_efficiency_0_to_20: float
    biodiversity_0_to_20: float
    carbon_balance_0_to_20: float
    input_self_sufficiency_0_to_20: float
    recommendations: list[str]


def score_sustainability(plan: FarmPlan) -> SustainabilityScore:
    """Compute the sustainability score from the plan's structure deterministically.
    Per the rubric in the knowledge base."""
    practices = {p.practice for p in plan.sustainability_practices}

    # 1. Soil health
    soil = 0.0
    if "crop_rotation" in practices: soil += 5
    if any(p in practices for p in ("intercropping", "cover_crops")): soil += 5
    if any(p in practices for p in ("composting", "vermicomposting", "green_manure")): soil += 5
    if "zbnf_practices" in practices: soil += 5
    soil = min(soil, 20)

    # 2. Water efficiency
    water = 0.0
    if "drip_irrigation" in practices: water += 8
    if "rainwater_harvesting" in practices: water += 5
    if "mulching" in practices: water += 4
    # drought-tolerant variety = any crop with "drought" in its concerns or crops like millets
    drought_tol_keywords = {"ragi", "bajra", "jowar", "millet", "horsegram", "drought"}
    crop_str = " ".join(c.crop_name.lower() + " " + str(c.climate_concerns).lower()
                        for c in plan.crops)
    if any(kw in crop_str for kw in drought_tol_keywords):
        water += 3
    water = min(water, 20)

    # 3. Biodiversity
    bio = 0.0
    if len({c.crop_name.lower() for c in plan.crops}) >= 3: bio += 6
    if any(c.role == "perennial_anchor" for c in plan.crops): bio += 5
    if plan.apiary: bio += 4
    if any(c.role == "boundary_crop" for c in plan.crops): bio += 3
    if "agroforestry" in practices: bio += 2
    if plan.livestock: bio += 2
    bio = min(bio, 20)

    # 4. Carbon
    carbon = 0.0
    if "solar_pump" in practices: carbon += 4
    if "biogas" in practices: carbon += 4
    if "agroforestry" in practices: carbon += 5
    if any(c.role == "perennial_anchor" for c in plan.crops): carbon += 3
    if "composting" in practices or "vermicomposting" in practices: carbon += 3
    if "zbnf_practices" in practices: carbon += 1
    carbon = min(carbon, 20)

    # 5. Input self-sufficiency
    inputs = 0.0
    if "composting" in practices or "vermicomposting" in practices: inputs += 6
    if "zbnf_practices" in practices: inputs += 5
    indigenous_breeds = {"sahiwal", "gir", "murrah", "osmanabadi", "aseel", "kadaknath", "cerana"}
    livestock_breeds = " ".join((l.breed or "").lower() for l in plan.livestock)
    apiary_species = (plan.apiary.bee_species.lower() if plan.apiary else "")
    if any(b in livestock_breeds or b in apiary_species for b in indigenous_breeds):
        inputs += 5
    if "green_manure" in practices: inputs += 4
    inputs = min(inputs, 20)

    composite = soil + water + bio + carbon + inputs

    recs: list[str] = []
    if soil < 12:
        recs.append("Add crop rotation / cover crops / composting to lift soil score.")
    if water < 12:
        recs.append("Install drip + rainwater harvesting to lift water score.")
    if bio < 12:
        recs.append("Diversify crop mix or add boundary/agroforestry plantings.")
    if carbon < 12:
        recs.append("Add solar pump / biogas / perennials to lift carbon score.")
    if inputs < 12:
        recs.append("Adopt ZBNF / composting / indigenous breeds for input self-sufficiency.")

    return SustainabilityScore(
        composite_0_to_100=composite,
        soil_health_0_to_20=soil,
        water_efficiency_0_to_20=water,
        biodiversity_0_to_20=bio,
        carbon_balance_0_to_20=carbon,
        input_self_sufficiency_0_to_20=inputs,
        recommendations=recs,
    )


# =====================================================================
# Markdown + PDF rendering
# =====================================================================

def render_plan_markdown(plan: FarmPlan, score: SustainabilityScore | None = None) -> str:
    if score is None:
        score = score_sustainability(plan)

    lines: list[str] = []
    lines.append(f"# Farm Plan — {plan.farmer_id}")
    lines.append(f"_Generated: {plan.generated_at}_  \n_Plan ID: {plan.plan_id}_\n")
    lines.append("## Summary\n")
    lines.append(plan.plan_summary)
    lines.append(f"\n**Farmer profile inferred**: {plan.farmer_profile_inferred}\n")
    lines.append(f"**Sustainability score**: {score.composite_0_to_100:.1f} / 100\n")

    lines.append("\n## Crops")
    for c in plan.crops:
        lines.append(f"\n### {c.crop_name}" + (f" — {c.variety}" if c.variety else "")
                     + (f" ({c.local_name})" if c.local_name else ""))
        lines.append(f"- **Role**: {c.role.replace('_', ' ')}")
        lines.append(f"- **Acres allocated**: {c.acres_allocated}")
        lines.append(f"- **Time to first yield**: {c.time_to_first_yield_years} years")
        lines.append(f"- **Peak production**: years {c.peak_production_year_start}-{c.peak_production_year_end}")
        lines.append(f"- **Yield (mature)**: {c.expected_yield_per_acre}")
        lines.append(f"- **Revenue at peak**: {c.revenue_per_acre_at_peak_inr}")
        lines.append(f"- **Year-1 investment**: {c.year_1_investment_inr}")
        lines.append(f"- **Annual maintenance**: {c.annual_maintenance_inr}")
        lines.append(f"- **Breakeven year**: Year {c.breakeven_year}")
        if c.why_it_fits:
            lines.append("- **Why it fits**: " + "; ".join(c.why_it_fits))
        if c.risk_flags:
            lines.append("- **Risk flags**: " + "; ".join(c.risk_flags))
        if c.market_channels:
            lines.append("- **Market channels**: " + ", ".join(c.market_channels))
        if c.govt_subsidies_available:
            lines.append("- **Govt subsidies**: " + ", ".join(c.govt_subsidies_available))
        if c.suppliers_known:
            lines.append("- **Suppliers**: " + ", ".join(c.suppliers_known))
        lines.append(f"- **Confidence**: self={c.confidence_self:.2f} · meta={c.confidence_meta:.2f}")

    if plan.livestock:
        lines.append("\n## Livestock")
        for l in plan.livestock:
            lines.append(f"\n### {l.type.replace('_', ' ').title()} — {l.breed} × {l.count}")
            lines.append(f"- **Space**: {l.space_required_sqft} sqft")
            lines.append(f"- **Daily feed**: {l.daily_feed_kg} kg")
            lines.append(f"- **Monthly net**: {l.monthly_net_inr_range}")
            lines.append(f"- **Breakeven**: {l.breakeven_months} months")
            if l.integration_with_crops:
                lines.append("- **Integration**: " + ", ".join(l.integration_with_crops))
            if l.govt_schemes_applicable:
                lines.append("- **Govt schemes**: " + ", ".join(l.govt_schemes_applicable))

    if plan.apiary:
        a = plan.apiary
        lines.append("\n## Apiary")
        lines.append(f"- **Species**: {a.bee_species}")
        lines.append(f"- **Boxes**: {a.bee_box_count}")
        lines.append(f"- **Placement**: {a.placement_strategy}")
        lines.append(f"- **Yield**: {a.expected_yield_kg_per_box_per_year} kg/box/year")
        lines.append(f"- **Revenue**: {a.expected_revenue_inr_per_year}")
        lines.append(f"- **Pollination benefit**: {', '.join(a.pollination_benefit_to_crops)}")

    if plan.sustainability_practices:
        lines.append("\n## Sustainability Practices")
        for p in plan.sustainability_practices:
            lines.append(f"\n### {p.practice.replace('_', ' ').title()}")
            lines.append(f"- {p.why_it_fits}")
            lines.append(f"- **Investment**: {p.investment_inr}  ·  **Payback**: {p.payback_period}")
            if p.govt_schemes_applicable:
                lines.append("- **Govt schemes**: " + ", ".join(p.govt_schemes_applicable))

    if plan.year_by_year_cash_flow:
        lines.append("\n## 10-Year Cash Flow\n")
        lines.append("| Year | Investment | Revenue | Net | Notes |")
        lines.append("|---|---|---|---|---|")
        for y in plan.year_by_year_cash_flow:
            lines.append(f"| Y{y.year} | {y.investment_inr_total} | {y.revenue_inr_range} | "
                         f"{y.net_inr_range} | {y.notes} |")

    lines.append(f"\n## Sustainability Score: {score.composite_0_to_100:.1f} / 100\n")
    lines.append(f"- Soil health: {score.soil_health_0_to_20:.0f}/20")
    lines.append(f"- Water efficiency: {score.water_efficiency_0_to_20:.0f}/20")
    lines.append(f"- Biodiversity: {score.biodiversity_0_to_20:.0f}/20")
    lines.append(f"- Carbon balance: {score.carbon_balance_0_to_20:.0f}/20")
    lines.append(f"- Input self-sufficiency: {score.input_self_sufficiency_0_to_20:.0f}/20")
    if score.recommendations:
        lines.append("\n**To improve:**")
        for r in score.recommendations:
            lines.append(f"- {r}")

    if plan.risk_diversification_strategy:
        lines.append(f"\n## Risk Diversification\n\n{plan.risk_diversification_strategy}")

    if plan.govt_subsidies_to_pursue:
        lines.append("\n## Govt Subsidies to Pursue")
        for s in plan.govt_subsidies_to_pursue:
            lines.append(f"- {s}")

    if plan.suppliers_to_contact:
        lines.append("\n## Suppliers to Contact")
        for s in plan.suppliers_to_contact:
            lines.append(f"- {s}")

    if plan.market_channels_to_develop:
        lines.append("\n## Market Channels to Develop")
        for m in plan.market_channels_to_develop:
            lines.append(f"- {m}")

    if plan.organic_transition_path:
        lines.append(f"\n## Organic Transition Path\n\n{plan.organic_transition_path}")

    if plan.immediate_next_steps:
        lines.append("\n## Next 30 Days — Action Items")
        for s in plan.immediate_next_steps:
            lines.append(f"- [ ] {s}")

    if plan.pilot_recommendation:
        lines.append(f"\n## Pilot Recommendation\n\n{plan.pilot_recommendation}")

    if plan.disclaimers:
        lines.append("\n## Disclaimers\n")
        for d in plan.disclaimers:
            lines.append(f"> {d}\n")

    return "\n".join(lines)


# ---- PDF rendering (fpdf2) ----

def _safe(text: str) -> str:
    """fpdf2's core fonts don't handle Unicode well; sanitize where needed.
    Replace common non-Latin1 chars."""
    replacements = {
        "->": "->", "<-": "<-", "*": "*",
        "Rs.": "Rs.", "-": "-", "...": "...",
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "₹": "Rs.", "→": "->", "←": "<-", "•": "*",
        "★": "*", "❌": "[X]", "—": "-", "–": "-",
        "…": "...",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Drop any remaining non-Latin1 chars
    return text.encode("latin1", errors="replace").decode("latin1")


class FarmPlanPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, _safe("Suryapet Farm Plan"), border=0, ln=1, align="L")
        self.set_draw_color(180, 180, 180)
        self.line(15, 25, 195, 25)
        self.ln(3)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, _safe(f"Page {self.page_no()}"), align="C")

    def section_h(self, text: str) -> None:
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(40, 100, 60)
        self.ln(4)
        self.cell(0, 7, _safe(text), ln=1)
        self.set_text_color(0, 0, 0)

    def section_h2(self, text: str) -> None:
        self.set_font("Helvetica", "B", 11)
        self.ln(2)
        self.cell(0, 6, _safe(text), ln=1)

    def body_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.multi_cell(180, 5, _safe(text))

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.multi_cell(180, 5, _safe(f"  * {text}"))


def render_plan_pdf(plan: FarmPlan, output_path: Path, score: SustainabilityScore | None = None) -> Path:
    if score is None:
        score = score_sustainability(plan)
    pdf = FarmPlanPDF()
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _safe("Farm Plan Report"), ln=1, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(f"Farmer ID: {plan.farmer_id}   |   Plan ID: {plan.plan_id}"),
             ln=1, align="C")
    pdf.cell(0, 6, _safe(f"Generated: {plan.generated_at[:19]}"), ln=1, align="C")
    pdf.ln(4)

    # Summary
    pdf.section_h("Summary")
    pdf.body_text(plan.plan_summary)
    pdf.ln(2)
    pdf.body_text(f"Farmer profile inferred: {plan.farmer_profile_inferred}")
    pdf.ln(1)
    pdf.body_text(f"Sustainability score: {score.composite_0_to_100:.1f} / 100")

    # Crops
    pdf.section_h("Crop Plan")
    for c in plan.crops:
        title = f"{c.crop_name}" + (f" - {c.variety}" if c.variety else "")
        pdf.section_h2(title)
        pdf.bullet(f"Role: {c.role.replace('_', ' ')}   |   Acres: {c.acres_allocated}")
        pdf.bullet(f"Time to first yield: {c.time_to_first_yield_years} yrs  |  "
                   f"Peak: Y{c.peak_production_year_start}-{c.peak_production_year_end}  |  "
                   f"Breakeven: Y{c.breakeven_year}")
        pdf.bullet(f"Yield (mature): {c.expected_yield_per_acre}")
        pdf.bullet(f"Revenue at peak: {c.revenue_per_acre_at_peak_inr}")
        pdf.bullet(f"Y1 investment: {c.year_1_investment_inr}   |   "
                   f"Annual maint: {c.annual_maintenance_inr}")
        if c.why_it_fits:
            pdf.bullet("Why it fits: " + "; ".join(c.why_it_fits))
        if c.risk_flags:
            pdf.bullet("Risks: " + "; ".join(c.risk_flags))
        if c.govt_subsidies_available:
            pdf.bullet("Govt subsidies: " + ", ".join(c.govt_subsidies_available))
        if c.suppliers_known:
            pdf.bullet("Suppliers: " + ", ".join(c.suppliers_known))
        pdf.bullet(f"Confidence: self={c.confidence_self:.2f}  meta={c.confidence_meta:.2f}")

    # Livestock
    if plan.livestock:
        pdf.section_h("Livestock")
        for l in plan.livestock:
            pdf.section_h2(f"{l.type.replace('_', ' ').title()} - {l.breed} x {l.count}")
            pdf.bullet(f"Space: {l.space_required_sqft} sqft  |  Daily feed: {l.daily_feed_kg} kg")
            pdf.bullet(f"Monthly net: {l.monthly_net_inr_range}  |  Breakeven: {l.breakeven_months} mo")
            if l.govt_schemes_applicable:
                pdf.bullet("Govt schemes: " + ", ".join(l.govt_schemes_applicable))

    # Apiary
    if plan.apiary:
        a = plan.apiary
        pdf.section_h("Apiary")
        pdf.bullet(f"Species: {a.bee_species}  |  Boxes: {a.bee_box_count}")
        pdf.bullet(f"Placement: {a.placement_strategy}")
        pdf.bullet(f"Yield: {a.expected_yield_kg_per_box_per_year} kg/box/yr  |  "
                   f"Revenue: {a.expected_revenue_inr_per_year}")
        if a.pollination_benefit_to_crops:
            pdf.bullet("Pollination benefit: " + ", ".join(a.pollination_benefit_to_crops))

    # Sustainability practices
    if plan.sustainability_practices:
        pdf.section_h("Sustainability Practices")
        for p in plan.sustainability_practices:
            pdf.section_h2(p.practice.replace("_", " ").title())
            pdf.bullet(p.why_it_fits)
            pdf.bullet(f"Investment: {p.investment_inr}  |  Payback: {p.payback_period}")
            if p.govt_schemes_applicable:
                pdf.bullet("Govt schemes: " + ", ".join(p.govt_schemes_applicable))

    # Cash flow table
    if plan.year_by_year_cash_flow:
        pdf.section_h("10-Year Cash Flow")
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(15, 6, "Year", border=1)
        pdf.cell(35, 6, "Investment", border=1)
        pdf.cell(40, 6, "Revenue", border=1)
        pdf.cell(35, 6, "Net", border=1)
        pdf.cell(55, 6, "Notes", border=1, ln=1)
        pdf.set_font("Helvetica", "", 8)
        for y in plan.year_by_year_cash_flow:
            pdf.cell(15, 6, _safe(f"Y{y.year}"), border=1)
            pdf.cell(35, 6, _safe(y.investment_inr_total), border=1)
            pdf.cell(40, 6, _safe(y.revenue_inr_range), border=1)
            pdf.cell(35, 6, _safe(y.net_inr_range), border=1)
            pdf.cell(55, 6, _safe(y.notes[:50]), border=1, ln=1)

    # Sustainability score breakdown
    pdf.section_h(f"Sustainability Score: {score.composite_0_to_100:.1f} / 100")
    pdf.bullet(f"Soil health: {score.soil_health_0_to_20:.0f}/20")
    pdf.bullet(f"Water efficiency: {score.water_efficiency_0_to_20:.0f}/20")
    pdf.bullet(f"Biodiversity: {score.biodiversity_0_to_20:.0f}/20")
    pdf.bullet(f"Carbon balance: {score.carbon_balance_0_to_20:.0f}/20")
    pdf.bullet(f"Input self-sufficiency: {score.input_self_sufficiency_0_to_20:.0f}/20")
    if score.recommendations:
        pdf.section_h2("To improve")
        for r in score.recommendations:
            pdf.bullet(r)

    # Risk + subsidies + suppliers + markets
    if plan.risk_diversification_strategy:
        pdf.section_h("Risk Diversification")
        pdf.body_text(plan.risk_diversification_strategy)

    if plan.govt_subsidies_to_pursue:
        pdf.section_h("Govt Subsidies to Pursue")
        for s in plan.govt_subsidies_to_pursue:
            pdf.bullet(s)

    if plan.suppliers_to_contact:
        pdf.section_h("Suppliers to Contact")
        for s in plan.suppliers_to_contact:
            pdf.bullet(s)

    if plan.market_channels_to_develop:
        pdf.section_h("Market Channels")
        for m in plan.market_channels_to_develop:
            pdf.bullet(m)

    if plan.organic_transition_path:
        pdf.section_h("Organic Transition Path")
        pdf.body_text(plan.organic_transition_path)

    # Next steps
    if plan.immediate_next_steps:
        pdf.section_h("Next 30 Days - Action Items")
        for s in plan.immediate_next_steps:
            pdf.bullet(s)

    if plan.pilot_recommendation:
        pdf.section_h("Pilot Recommendation")
        pdf.body_text(plan.pilot_recommendation)

    # Disclaimers
    if plan.disclaimers:
        pdf.section_h("Disclaimers")
        for d in plan.disclaimers:
            pdf.body_text(d)

    output_path = Path(output_path)
    pdf.output(str(output_path))
    return output_path


# =====================================================================
# CLI sanity check
# =====================================================================

if __name__ == "__main__":
    print("Farm planner engine (Ollama variant) - module sanity check")
    print(f"  ANSWER_MODEL:  {ANSWER_MODEL}")
    print(f"  PROFILES_DIR:  {PROFILES_DIR}")
    print(f"  PLANS_DIR:     {PLANS_DIR}")
    print(f"  KB path:       {KNOWLEDGE_BASE_PATH}")
    print(f"  KB exists:     {KNOWLEDGE_BASE_PATH.exists()}")
    if KNOWLEDGE_BASE_PATH.exists():
        kb = _load_knowledge_base()
        print(f"  KB size:       {len(kb):,} chars / ~{len(kb)//4:,} tokens")
    print(f"  Profiles on disk: {len(list_profiles())}")
    for p in list_profiles():
        print(f"    - {p.name} ({p.district}, {p.total_acres} ac, {p.farmer_id})")
