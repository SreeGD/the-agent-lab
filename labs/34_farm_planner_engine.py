"""Farm planner engine — pure Python, no UI imports.

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
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

ANSWER_MODEL = "claude-sonnet-4-6"
JUDGE_MODEL = "claude-haiku-4-5-20251001"

HERE = Path(__file__).parent
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
Suryapet / Jangaon / Nalgonda region of Telangana, India. The user gives you
a FarmProfile and PlanningGoals (both as JSON). You produce a STRUCTURED
FarmPlan with crops, optional livestock and apiary, sustainability practices,
a 10-year cash flow, and concrete next steps.

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
- Specific numbers (₹ ranges, kg yields, breakeven years), not platitudes.
- Variety-level granularity. Say "Thailand Lemon" not "lemon".
- Honest about confidence — use the calibration guide in the knowledge base.
- Always end with the standard disclaimer + KVK escalation note.

Generate 3-6 crops in the plan, balancing time horizons:
- Short-term (3-6 months): pulses, vegetables, oilseeds — for Year 1-2 cash flow
- Medium-term (6-12 months): cotton, papaya — annual/biennial
- Perennials (2-10+ years): lemon, avocado, mango, dragon fruit — asset building
- Boundary crops: drumstick, agroforestry trees — buffer + wildlife defense

For each crop, fill confidence_self (your own confidence) and confidence_meta
(calibrated). High confidence (>0.85) for knowledge-base-grounded claims;
medium (0.65-0.85) for ₹ projections; lower for experimental crops.

KNOWLEDGE BASE (authoritative, do not contradict):
==================================================
{knowledge_base}
==================================================
"""


def _build_system_prompt() -> list[dict]:
    """Build system prompt with cache_control on the knowledge base prefix."""
    knowledge = _load_knowledge_base()
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT_TEMPLATE.format(knowledge_base=knowledge),
            "cache_control": {"type": "ephemeral"},
        }
    ]


def generate_farm_plan(profile: FarmProfile, goals: PlanningGoals,
                       max_retries: int = 3) -> FarmPlan:
    """The main entry point. Calls the LLM, returns a validated FarmPlan.

    Retries on transient API errors (connection drop, timeout).
    """
    model = ChatAnthropic(model=ANSWER_MODEL, temperature=0,
                          max_tokens=8192, timeout=600)
    planner = model.with_structured_output(FarmPlan)

    user_prompt = (
        f"FARM PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"PLANNING GOALS:\n{goals.model_dump_json(indent=2)}\n\n"
        "Generate a complete FarmPlan. Use the embedded knowledge base for "
        "all variety, supplier, scheme, and economics references. Match crops "
        "to the profile's climate (district), soil, water access, wildlife "
        "pressure, labor, investment, and stated goals."
    )

    last_err: Exception | None = None
    backoff_seconds = [0, 10, 30, 60]   # exponential backoff between retries
    for attempt in range(max_retries):
        if attempt > 0:
            wait = backoff_seconds[min(attempt, len(backoff_seconds) - 1)]
            print(f"[engine] backing off {wait}s before retry {attempt + 1}...")
            time.sleep(wait)
        try:
            plan = planner.invoke([
                SystemMessage(content=_build_system_prompt()),
                HumanMessage(user_prompt),
            ])
            # Inject required ID fields the LLM doesn't generate
            plan.plan_id = f"plan_{uuid4().hex[:8]}"
            plan.farmer_id = profile.farmer_id
            plan.generated_at = datetime.now(timezone.utc).isoformat()
            return plan
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"[engine] transient error on attempt {attempt + 1}: "
                      f"{type(e).__name__} — will retry...")
    raise last_err


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
        "→": "->", "←": "<-", "•": "*", "★": "*", "❌": "[X]",
        "₹": "Rs.", "—": "-", "–": "-", "…": "...",
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
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
    print("Farm planner engine - module sanity check")
    print(f"  PROFILES_DIR: {PROFILES_DIR}")
    print(f"  PLANS_DIR:    {PLANS_DIR}")
    print(f"  KB path:      {KNOWLEDGE_BASE_PATH}")
    print(f"  KB exists:    {KNOWLEDGE_BASE_PATH.exists()}")
    if KNOWLEDGE_BASE_PATH.exists():
        kb = _load_knowledge_base()
        print(f"  KB size:      {len(kb):,} chars / ~{len(kb)//4:,} tokens")
    print(f"  Profiles on disk: {len(list_profiles())}")
    for p in list_profiles():
        print(f"    - {p.name} ({p.district}, {p.total_acres} ac, {p.farmer_id})")
