"""Streamlit UI for the Suryapet Farm Planner.

Thin wrapper over `34_farm_planner_engine.py`. All business logic lives in
the engine; this file is just forms + tabs + rendering.

Run with:
    streamlit run 34_farm_planner_ui.py
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

# Import engine via importlib (file starts with digit)
_engine_path = Path(__file__).parent / "34_farm_planner_engine.py"
_spec = importlib.util.spec_from_file_location("engine", _engine_path)
engine = importlib.util.module_from_spec(_spec)
sys.modules["engine"] = engine
_spec.loader.exec_module(engine)

import importlib.util as _ilu
_yo_path = Path(__file__).parent / "agritech" / "yield_optimizer_engine.py"
_yo_spec = _ilu.spec_from_file_location("yield_optimizer_engine", _yo_path)
if _yo_spec is None:
    raise ImportError(f"yield_optimizer_engine not found at {_yo_path}")
yo_engine = _ilu.module_from_spec(_yo_spec)
sys.modules["yield_optimizer_engine"] = yo_engine
_yo_spec.loader.exec_module(yo_engine)

st.set_page_config(
    page_title="Suryapet Farm Planner",
    page_icon=":seedling:",
    layout="wide",
)


# =====================================================================
# Session state init
# =====================================================================

if "current_farmer_id" not in st.session_state:
    st.session_state.current_farmer_id = None
if "current_plan" not in st.session_state:
    st.session_state.current_plan = None
if "current_score" not in st.session_state:
    st.session_state.current_score = None
if "yo_plan" not in st.session_state:
    st.session_state.yo_plan = None


# =====================================================================
# Sidebar nav
# =====================================================================

st.sidebar.title(":seedling: Farm Planner")
st.sidebar.caption("Suryapet · Jangaon · Nalgonda")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Home", "Farm Profile", "Goals & Constraints", "Generate Plan",
     "Yield Optimizer", "View Plan", "Sustainability Audit", "About"],
    label_visibility="collapsed",
)

# Show current farmer in sidebar
if st.session_state.current_farmer_id:
    try:
        p = engine.load_profile(st.session_state.current_farmer_id)
        st.sidebar.divider()
        st.sidebar.caption("Current farmer")
        st.sidebar.write(f"**{p.name}**")
        st.sidebar.write(f"{p.district} · {p.total_acres} acres")
    except FileNotFoundError:
        st.session_state.current_farmer_id = None


# =====================================================================
# Page: Home
# =====================================================================

def page_home():
    st.title(":seedling: Suryapet Farm Planner")
    st.caption("Knowledge-grounded crop planning for Telangana smallholder + commercial farmers")
    st.markdown(
        "This planner takes your **farm profile** + **goals** and produces a multi-year "
        "crop plan with variety-level economics, mixed-farming options (dairy, apiary, etc.), "
        "sustainability practices, and a 10-year cash flow.\n\n"
        "Knowledge base covers **Suryapet, Jangaon, Nalgonda** with regional soil, "
        "climate, market, wildlife, and govt-scheme detail."
    )

    profiles = engine.list_profiles()
    if profiles:
        st.subheader("Existing farmers")
        for prof in profiles:
            cols = st.columns([4, 2, 2, 1])
            cols[0].write(f"**{prof.name}**")
            cols[1].write(prof.district)
            cols[2].write(f"{prof.total_acres} acres")
            if cols[3].button("Select", key=f"sel_{prof.farmer_id}"):
                st.session_state.current_farmer_id = prof.farmer_id
                st.success(f"Selected: {prof.name}")
                st.rerun()

    st.divider()
    if st.button("Create new farmer profile", type="primary"):
        st.session_state.current_farmer_id = None
        st.session_state.show_new_profile = True
        st.info("Go to **Farm Profile** in the sidebar to enter details.")


# =====================================================================
# Page: Farm Profile builder
# =====================================================================

def page_profile():
    st.title("Farm Profile")

    if st.session_state.current_farmer_id:
        try:
            p = engine.load_profile(st.session_state.current_farmer_id)
            st.caption(f"Editing existing profile: {p.name}")
        except FileNotFoundError:
            p = engine.FarmProfile(
                farmer_id=engine.make_farmer_id(), name="", total_acres=0.0,
            )
    else:
        p = engine.FarmProfile(
            farmer_id=engine.make_farmer_id(), name="", total_acres=0.0,
        )
        st.caption("Creating new profile")

    with st.form("profile_form"):
        # IDENTITY
        st.subheader("Identity & Location")
        cols = st.columns(2)
        p.name = cols[0].text_input("Farmer name", value=p.name)
        p.village = cols[1].text_input("Village", value=p.village or "")
        cols = st.columns(3)
        p.district = cols[0].selectbox(
            "District", ["Suryapet", "Jangaon", "Nalgonda", "Other"],
            index=["Suryapet", "Jangaon", "Nalgonda", "Other"].index(p.district),
        )
        p.state = cols[1].text_input("State", value=p.state)
        p.pincode = cols[2].text_input("Pincode", value=p.pincode or "")

        # LAND
        st.subheader("Land & Soil")
        cols = st.columns(2)
        p.total_acres = cols[0].number_input("Total acres", min_value=0.0, value=p.total_acres, step=0.5)
        p.parcel_count = cols[1].number_input("Number of parcels", min_value=1, value=p.parcel_count)

        soil_options = ["red_soil_loam", "red_soil_chalka_sandy", "black_cotton_regur",
                        "alluvial", "laterite", "saline_alkaline", "mixed", "unknown"]
        p.soil_types_present = st.multiselect(
            "Soil types present (multi-select)", soil_options, default=p.soil_types_present,
        )

        p.soil_test_done = st.checkbox("Soil test done (Soil Health Card)?", value=p.soil_test_done)
        if p.soil_test_done:
            if p.soil_test_data is None:
                p.soil_test_data = engine.SoilTestData()
            cols = st.columns(5)
            p.soil_test_data.ph = cols[0].number_input("pH", value=p.soil_test_data.ph or 7.0)
            p.soil_test_data.nitrogen_kg_ha = cols[1].number_input("N (kg/ha)", value=p.soil_test_data.nitrogen_kg_ha or 0.0)
            p.soil_test_data.phosphorus_kg_ha = cols[2].number_input("P (kg/ha)", value=p.soil_test_data.phosphorus_kg_ha or 0.0)
            p.soil_test_data.potassium_kg_ha = cols[3].number_input("K (kg/ha)", value=p.soil_test_data.potassium_kg_ha or 0.0)
            p.soil_test_data.organic_carbon_pct = cols[4].number_input("OC %", value=p.soil_test_data.organic_carbon_pct or 0.0)

        # WATER
        st.subheader("Water & Irrigation")
        p.water_sources = st.multiselect(
            "Water sources",
            ["bore_well", "canal", "lift_irrigation", "pond_tank", "rainfed_only"],
            default=p.water_sources,
        )
        p.irrigation_infrastructure = st.multiselect(
            "Irrigation infrastructure",
            ["drip", "sprinkler", "flood", "none"],
            default=p.irrigation_infrastructure,
        )

        # FAMILY + LABOR
        st.subheader("Family & Labor")
        cols = st.columns(3)
        p.adult_workers = cols[0].number_input("Adult workers in family", min_value=0, value=p.adult_workers)
        p.children = cols[1].number_input("Children", min_value=0, value=p.children)
        p.hired_labor_available = cols[2].selectbox(
            "Hired labor",
            ["family_only", "seasonal_hired", "year_round_hired"],
            index=["family_only", "seasonal_hired", "year_round_hired"].index(p.hired_labor_available),
        )

        # WILDLIFE
        st.subheader("Wildlife & Risks")
        p.wildlife_present = st.multiselect(
            "Wildlife pressure on the farm",
            ["monkeys", "wild_boar", "peacocks", "nilgai", "elephants", "birds", "none"],
            default=p.wildlife_present,
        )
        p.forest_proximity_km = st.number_input(
            "Distance to nearest forest (km)",
            min_value=0.0, value=p.forest_proximity_km or 10.0,
        )

        # INVESTMENT
        st.subheader("Investment & Income")
        cols = st.columns(2)
        p.investment_capacity_inr = cols[0].number_input(
            "Investment capacity ₹", min_value=0, value=p.investment_capacity_inr, step=50000,
        )
        p.primary_income_source = cols[1].selectbox(
            "Primary income source",
            ["farming_only", "mixed", "salary_with_farm_side"],
            index=["farming_only", "mixed", "salary_with_farm_side"].index(p.primary_income_source),
        )

        # INFRASTRUCTURE
        st.subheader("Existing Infrastructure")
        cols = st.columns(4)
        p.has_drip = cols[0].checkbox("Drip", value=p.has_drip)
        p.has_storage = cols[1].checkbox("Storage", value=p.has_storage)
        p.has_processing_unit = cols[2].checkbox("Processing", value=p.has_processing_unit)
        p.has_cold_storage = cols[3].checkbox("Cold storage", value=p.has_cold_storage)

        # GOVT SCHEMES
        st.subheader("Govt Schemes Enrolled")
        cols = st.columns(5)
        p.pm_kisan_enrolled = cols[0].checkbox("PM-KISAN", value=p.pm_kisan_enrolled)
        p.kcc_enrolled = cols[1].checkbox("KCC", value=p.kcc_enrolled)
        p.pmfby_enrolled = cols[2].checkbox("PMFBY", value=p.pmfby_enrolled)
        p.soil_health_card = cols[3].checkbox("Soil Health Card", value=p.soil_health_card)
        p.rythu_bandhu_received = cols[4].checkbox("Rythu Bandhu", value=p.rythu_bandhu_received)

        # SUSTAINABILITY
        st.subheader("Sustainability Orientation")
        cols = st.columns(3)
        p.organic_interest = cols[0].selectbox(
            "Organic interest",
            ["none", "transitioning", "certified"],
            index=["none", "transitioning", "certified"].index(p.organic_interest),
        )
        p.zbnf_practitioner = cols[1].checkbox("ZBNF practitioner", value=p.zbnf_practitioner)
        p.open_to_agroforestry = cols[2].checkbox("Open to agroforestry", value=p.open_to_agroforestry)

        # LANGUAGE
        p.primary_language = st.selectbox(
            "Primary language",
            ["Telugu", "Hindi", "English", "other"],
            index=["Telugu", "Hindi", "English", "other"].index(p.primary_language),
        )

        submitted = st.form_submit_button("Save profile", type="primary")
        if submitted:
            engine.save_profile(p)
            st.session_state.current_farmer_id = p.farmer_id
            st.success(f"Profile saved: {p.name} ({p.farmer_id})")
            st.rerun()


# =====================================================================
# Page: Goals & Constraints
# =====================================================================

def page_goals():
    st.title("Planning Goals & Constraints")
    if not st.session_state.current_farmer_id:
        st.warning("Pick or create a farmer profile first (Home or Farm Profile).")
        return

    p = engine.load_profile(st.session_state.current_farmer_id)
    st.caption(f"Planning for: **{p.name}** ({p.district}, {p.total_acres} acres)")

    goals: engine.PlanningGoals = st.session_state.get("current_goals", engine.PlanningGoals())

    st.subheader("Primary goal")
    goals.primary_goal = st.radio(
        "What's the main outcome you want?",
        ["stable_monthly_income", "asset_building_long_term", "subsistence_first",
         "max_revenue_per_acre", "diversification_resilience", "transition_to_organic",
         "sustainability_focused"],
        index=["stable_monthly_income", "asset_building_long_term", "subsistence_first",
               "max_revenue_per_acre", "diversification_resilience", "transition_to_organic",
               "sustainability_focused"].index(goals.primary_goal),
        format_func=lambda x: x.replace("_", " ").title(),
    )

    goals.secondary_goals = st.multiselect(
        "Secondary goals (multi-select)",
        ["income_smoothing", "soil_health", "water_efficiency", "climate_resilience",
         "family_nutrition", "export_potential", "labor_minimization"],
        default=goals.secondary_goals,
    )

    cols = st.columns(2)
    goals.planning_horizon_years = cols[0].selectbox(
        "Planning horizon (years)",
        [1, 3, 5, 10],
        index=[1, 3, 5, 10].index(goals.planning_horizon_years),
    )
    goals.max_investment_inr = cols[1].number_input(
        "Max investment ₹", min_value=0, value=goals.max_investment_inr, step=50000,
    )

    st.subheader("Constraints")
    cols = st.columns(3)
    goals.min_food_security = cols[0].checkbox("Min food security (don't recommend all cash crops)", value=goals.min_food_security)
    goals.must_use_existing_infrastructure = cols[1].checkbox("Must use existing infrastructure", value=goals.must_use_existing_infrastructure)
    goals.organic_required = cols[2].checkbox("Organic required", value=goals.organic_required)

    goals.avoid_chemical_pesticides = st.checkbox("Avoid chemical pesticides", value=goals.avoid_chemical_pesticides)
    goals.water_use_priority = st.selectbox(
        "Water use priority",
        ["minimize", "moderate", "unconstrained"],
        index=["minimize", "moderate", "unconstrained"].index(goals.water_use_priority),
    )

    st.subheader("Mixed farming options")
    cols = st.columns(3)
    goals.include_dairy = cols[0].checkbox("Dairy (cow / buffalo / goat)", value=goals.include_dairy)
    goals.include_apiary = cols[1].checkbox("Apiary (bees)", value=goals.include_apiary)
    goals.include_poultry = cols[2].checkbox("Poultry", value=goals.include_poultry)
    cols = st.columns(3)
    goals.include_fish = cols[0].checkbox("Fish (pond aquaculture)", value=goals.include_fish)
    goals.include_sericulture = cols[1].checkbox("Sericulture (silk)", value=goals.include_sericulture)
    goals.include_mushroom = cols[2].checkbox("Mushroom", value=goals.include_mushroom)

    st.subheader("Exotic / high-value crops of interest")
    exotic_options = [
        "Avocado (Fuerte/Pollock — heat-tolerant green-skin)",
        "Dragon Fruit (very low water + wildlife)",
        "Custard Apple / Sitaphal",
        "Fig (Anjeer)",
        "Pomegranate (Bhagwa)",
        "Dates (Khajur)",
        "Aloe Vera",
        "Stevia",
        "Lemongrass",
        "Passion Fruit",
        "Moringa (commercial)",
        "Olive (experimental)",
    ]
    goals.interested_exotic_crops = st.multiselect(
        "Pick any that interest you", exotic_options, default=goals.interested_exotic_crops,
    )
    goals.other_exotic_interest = st.text_input(
        "Any other exotic / specialty crop interest?",
        value=goals.other_exotic_interest,
    )

    st.subheader("Risk + rollout")
    cols = st.columns(2)
    goals.risk_tolerance = cols[0].selectbox(
        "Risk tolerance",
        ["conservative", "moderate", "aggressive"],
        index=["conservative", "moderate", "aggressive"].index(goals.risk_tolerance),
    )
    goals.pilot_first = cols[1].checkbox(
        "Prefer pilot (0.5-1 acre) before scaling new crops", value=goals.pilot_first,
    )

    st.session_state.current_goals = goals
    st.success("Goals saved in session. Go to **Generate Plan** to run the advisor.")


# =====================================================================
# Page: Generate Plan
# =====================================================================

def page_generate():
    st.title("Generate Farm Plan")
    if not st.session_state.current_farmer_id:
        st.warning("Pick a farmer first.")
        return
    p = engine.load_profile(st.session_state.current_farmer_id)
    g = st.session_state.get("current_goals", engine.PlanningGoals())

    st.caption(f"Profile: **{p.name}** ({p.district}, {p.total_acres} ac)")
    st.caption(f"Goals: primary={g.primary_goal} · horizon={g.planning_horizon_years}yr · "
               f"investment cap=₹{g.max_investment_inr:,} · dairy={g.include_dairy} · "
               f"apiary={g.include_apiary}")

    mode = st.radio(
        "Generation mode",
        ["Single plan (pick a risk profile, ~6-9 min)",
         "Compare 3 options (conservative + balanced + aggressive, ~18-25 min)"],
        index=0,
    )

    if mode.startswith("Single"):
        risk_profile = st.selectbox(
            "Risk profile",
            ["conservative", "balanced", "aggressive"],
            index=["conservative", "balanced", "aggressive"].index(g.risk_profile),
            help="Conservative = food security + small pilots. "
                 "Balanced = mid (standard recommendation). "
                 "Aggressive = larger perennial + exotic bets."
        )
        if st.button("Generate plan", type="primary"):
            g.risk_profile = risk_profile
            status = st.status(
                f"Generating {risk_profile} plan (native SDK + cache; "
                "parallel per-crop generation)...",
                expanded=True,
            )
            try:
                # Friendly labels per node — UI sees these as they complete
                node_labels = {
                    "profile_synthesis": "📝 Profile synthesis + strategy",
                    "crop_intent":       "🎯 Picking crops (names + roles)",
                    "crops_parallel":    "🌾 Crop details (parallel thread pool)",
                    "livestock_apiary":  "🐄 Livestock + apiary",
                    "sustainability":    "🌱 Sustainability + subsidies",
                    "cashflow":          "💰 Cash flow + next steps",
                    "assemble":          "🧩 Assembling plan",
                    "critique":          "🎯 Devil's advocate critique",
                }
                plan: engine.FarmPlan | None = None
                critique: engine.PlanCritique | None = None
                for ev in engine.stream_plan_via_graph(p, g, risk_profile=risk_profile):
                    for node, delta in ev.items():
                        label = node_labels.get(node, node)
                        status.write(f"✓ {label} done")
                        if "plan" in delta:
                            plan = delta["plan"]
                        if "critique" in delta:
                            critique = delta["critique"]

                if plan is None or critique is None:
                    raise RuntimeError("Graph completed but final plan/critique missing")

                engine.save_plan(plan)
                score = engine.score_sustainability(plan)
                st.session_state.current_plan = plan
                st.session_state.current_critique = critique
                st.session_state.current_score = score
                st.session_state.current_result = None  # clear multi-option
                status.update(label=f"Plan {plan.plan_id} ready · score {score.composite_0_to_100:.1f}/100", state="complete")
                st.success(f"Confidence: {critique.overall_confidence:.2f}  ·  "
                           f"Biggest risk: {critique.biggest_risk}")
                st.info("Switch to **View Plan** to see crops, livestock, cash flow, and devil's advocate critique.")
            except Exception as e:
                status.update(state="error")
                st.error(f"Failed: {type(e).__name__}: {e}")
    else:
        if st.button("Generate 3 options", type="primary"):
            status = st.status("Generating 3 plans (conservative → balanced → aggressive)...", expanded=True)
            try:
                status.write("**Conservative** — running 4 LLM calls...")
                result = engine.generate_three_options(p, g)
                for opt in result.options:
                    status.write(f"✓ {opt.risk_profile.title()} option: "
                                 f"{len(opt.plan.crops)} crops · "
                                 f"confidence {opt.critique.overall_confidence:.2f}")
                engine.save_plan_result(result)
                st.session_state.current_result = result
                st.session_state.current_plan = next(
                    o.plan for o in result.options if o.risk_profile == result.recommended_option
                )
                st.session_state.current_critique = next(
                    o.critique for o in result.options if o.risk_profile == result.recommended_option
                )
                st.session_state.current_score = engine.score_sustainability(st.session_state.current_plan)
                status.update(label=f"3 plans ready · recommended: {result.recommended_option}", state="complete")
                st.info(f"**Recommendation**: {result.recommended_option} option. {result.recommendation_reasoning}")
                st.info("Switch to **View Plan** to compare options side-by-side.")
            except Exception as e:
                status.update(state="error")
                st.error(f"Failed: {type(e).__name__}: {e}")


# =====================================================================
# Page: Yield Optimizer
# =====================================================================

def page_yield_optimizer():
    st.title("Crop Yield Optimizer")
    st.caption("Deep-dive playbook for one crop on one patch. Complements the Farm Plan.")

    # ── Farmer selector ──────────────────────────────────────────
    profiles = engine.list_profiles()
    if not profiles:
        st.warning("No farmer profiles found. Create one in Farm Profile first.")
        st.stop()

    farmer_names = {p.farmer_id: p.name for p in profiles}
    selected_id = st.selectbox(
        "Farmer profile",
        options=list(farmer_names.keys()),
        format_func=lambda fid: f"{farmer_names[fid]} ({fid})",
        index=0 if st.session_state.current_farmer_id is None
              else (list(farmer_names.keys()).index(st.session_state.current_farmer_id)
                    if st.session_state.current_farmer_id in farmer_names else 0),
    )
    profile = engine.load_profile(selected_id)

    st.divider()

    # ── Crop type radio ──────────────────────────────────────────
    crop_type = st.radio(
        "Crop type",
        options=["annual_grain", "annual_fiber", "annual_oilseed",
                 "perennial_fruit", "perennial_timber", "perennial_oilseed"],
        format_func=lambda x: {
            "annual_grain": "Annual Grain (paddy, corn)",
            "annual_fiber": "Annual Fiber (cotton)",
            "annual_oilseed": "Annual Oilseed (groundnut, sesame)",
            "perennial_fruit": "Perennial Fruit (mango, lemon, avocado)",
            "perennial_timber": "Perennial Timber (eucalyptus)",
            "perennial_oilseed": "Perennial Oilseed (palm oil)",
        }[x],
        horizontal=True,
    )

    # ── Focus inputs ─────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        focused_crop = st.text_input("Crop name", placeholder="e.g. Thailand Lemon, BPT 5204 Paddy, Bt Cotton")
    with col2:
        focused_variety = st.text_input("Variety (optional — advisor will recommend if blank)", placeholder="e.g. NHH 44, Banganapalli")
    with col3:
        focused_acres = st.number_input("Focused acres", min_value=0.25, max_value=100.0, value=1.0, step=0.25)

    # ── Stage selector ───────────────────────────────────────────
    current_stage = st.selectbox(
        "Current stage",
        options=["planning", "planted_y1", "planted_y2_y4", "mature_bearing"],
        format_func=lambda x: {
            "planning": "Planning (not yet planted)",
            "planted_y1": "Planted — Year 1",
            "planted_y2_y4": "Planted — Years 2-4",
            "mature_bearing": "Mature / Bearing",
        }[x],
    )

    # ── Goal inputs ──────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        yield_goal_pct = st.slider("Yield improvement target (%)", 0, 100, 20, step=5,
                                    help="0 = no specific target, advisor will set benchmark")
    with col_b:
        investment_cap = st.number_input("Investment cap (₹, 0 = no cap)", min_value=0, max_value=2000000,
                                          value=0, step=10000)

    # ── Constraint checkboxes ────────────────────────────────────
    col_x, col_y, col_z = st.columns(3)
    with col_x:
        organic_required = st.checkbox("Organic certification required")
    with col_y:
        avoid_chemicals = st.checkbox("Avoid chemical pesticides")
    with col_z:
        labor_cap = st.selectbox("Labor cap", ["family_only", "seasonal", "year_round"],
                                  format_func=lambda x: {"family_only": "Family only", "seasonal": "Seasonal hired", "year_round": "Year-round hired"}[x])

    parcel_notes = st.text_area("Parcel notes (optional)", placeholder="Soil type, slope, water source distance, existing crops nearby...")

    st.divider()

    # ── Optimize button ──────────────────────────────────────────
    if st.button("Optimize yield", type="primary", disabled=not focused_crop.strip()):
        yo_profile = yo_engine.YieldOptimizationProfile(
            farmer_id=selected_id,
            focused_acres=focused_acres,
            parcel_notes=parcel_notes or None,
            focused_crop=focused_crop.strip(),
            focused_variety=focused_variety.strip() or None,
            crop_type=crop_type,
            current_stage=current_stage,
            existing_inputs=None,
            yield_goal_pct_improvement=float(yield_goal_pct) if yield_goal_pct > 0 else None,
            yield_goal_absolute_per_acre=None,
            organic_required=organic_required,
            avoid_chemical_pesticides=avoid_chemicals,
            investment_cap_inr=int(investment_cap) if investment_cap > 0 else None,
            labor_cap=labor_cap,
            notes=None,
        )

        node_labels = {
            "variety_and_land":          "🌱 Variety selection + land prep",
            "spacing_water_nutrition":   "💧 Spacing, water & nutrition",
            "protection":                "🛡️ Crop protection + IPM",
            "harvest_economics_risks":   "💰 Harvest, economics & risks",
            "assemble":                  "🧩 Assembling plan",
            "critique":                  "🎯 Devil's advocate critique",
        }

        status = st.status(
            f"Optimizing {focused_crop} yield ({focused_acres} ac) ...",
            expanded=True,
        )
        try:
            plan = None
            for ev in yo_engine.stream_yield_plan(yo_profile):
                for node, delta in ev.items():
                    label = node_labels.get(node, node)
                    status.write(f"✓ {label} done")
                    if "plan" in delta:
                        plan = yo_engine.YieldOptimizationPlan.model_validate(delta["plan"])
                    if "critique" in delta and plan is not None:
                        critique_obj = yo_engine.YieldCritique.model_validate(delta["critique"])
                        plan = plan.model_copy(update={"critique": critique_obj})

            if plan is None:
                raise RuntimeError("Optimizer completed but plan is missing")

            st.session_state.yo_plan = plan
            status.update(
                label=f"Plan ready · {plan.focused_crop} ({plan.focused_variety}) · "
                      f"confidence {plan.critique.overall_confidence:.2f}",
                state="complete",
            )
        except Exception as e:
            status.update(state="error")
            st.error(f"Failed: {type(e).__name__}: {e}")
            st.stop()

    # ── Results ──────────────────────────────────────────────────
    plan = st.session_state.get("yo_plan")
    if plan is not None:
        st.divider()
        st.subheader(f"{plan.focused_crop} — {plan.focused_variety} · {plan.focused_acres} ac")

        # Section 1: Variety + Land
        with st.expander("1. Variety & Land Preparation", expanded=True):
            st.write(plan.variety_rationale)
            lp = plan.land_preparation
            st.markdown(f"**Soil test needed:** {'Yes' if lp.soil_test_needed else 'No'}  \n"
                        f"**Bed type:** {lp.bed_type}  \n"
                        f"**Drainage:** {lp.drainage_notes}  \n"
                        f"**Amendments:** {', '.join(lp.amendments) if lp.amendments else 'None'}")
            if plan.clone_selection:
                cs = plan.clone_selection
                st.markdown(f"**Clones:** {', '.join(cs.recommended_clones)} from {cs.source_organization}  \n"
                            f"**Expected yield:** {cs.expected_yield_per_acre_per_rotation}  \n"
                            f"**Productive life:** {cs.productive_lifetime_years} years")

        # Section 2: Spacing, Water & Irrigation
        with st.expander("2. Spacing, Water & Irrigation"):
            sd = plan.spacing_and_density
            wr = plan.water_regime
            st.markdown(f"**Spacing:** {sd.row_spacing_m}m × {sd.plant_spacing_m}m ({sd.plants_per_acre} plants/acre)  \n"
                        f"**Water method:** {wr.primary_method}  \n"
                        f"**Rationale:** {wr.rationale}")
            if wr.water_savings_pct:
                st.markdown(f"**Water savings:** {wr.water_savings_pct:.0f}%  |  **Yield impact:** {wr.yield_impact_pct:+.0f}%")

        # Section 3: Nutrition
        with st.expander("3. Nutrition Program"):
            for ns in plan.nutrition_program:
                st.markdown(f"**{ns.stage_name}** ({ns.dap_range}): {', '.join(ns.fertilizers)}")
                if ns.notes:
                    st.caption(ns.notes)
            if plan.nitrogen_split_protocol:
                nsp = plan.nitrogen_split_protocol
                st.markdown(f"**Total N:** {nsp.total_n_kg_per_acre} kg/acre")
                for s in nsp.splits:
                    st.markdown(f"  - {s.stage} — {s.pct}% at day {s.days_after_sowing}")

        # Section 4: Crop Protection
        with st.expander("4. IPM & Crop Protection"):
            if plan.pest_calendar:
                rows = [{"Month": pe.month, "Pest": pe.pest_name, "Threshold": pe.threshold,
                         "Organic action": pe.organic_action, "Chemical action": pe.chemical_action}
                        for pe in plan.pest_calendar]
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            if plan.fall_armyworm_protocol:
                faw = plan.fall_armyworm_protocol
                st.markdown(f"**⚠️ Fall Armyworm:** {faw.monitoring_protocol}  \n"
                            f"Threshold: {faw.threshold_for_action}  \n"
                            f"Expected loss without action: {faw.expected_damage_without_intervention}")
            if plan.refuge_strategy:
                r = plan.refuge_strategy
                st.markdown(f"**Refuge (Bt resistance):** {r.refuge_acres:.2f} ac of {r.refuge_crop} — {r.rationale}")
            if plan.wildlife_deterrent_plan:
                wd = plan.wildlife_deterrent_plan
                st.markdown(f"**Wildlife:** {', '.join(wd.threats)} — {', '.join(wd.deterrent_methods)}")

        # Section 5: Crop-stage specifics
        with st.expander("5. Canopy, PBZ & Pollination"):
            if plan.canopy_management:
                cm = plan.canopy_management
                st.markdown(f"**Pruning:** {cm.pruning_type} — {cm.technique} ({cm.timing})  \n"
                            f"Yield impact: {cm.expected_yield_impact_pct:+.0f}%")
            if plan.paclobutrazol_protocol:
                pbz = plan.paclobutrazol_protocol
                st.markdown(f"**PBZ:** {pbz.dose_per_tree_g}g/tree via {pbz.application_method} at {pbz.application_timing}  \n"
                            f"Off-season yield: {pbz.expected_off_season_yield_pct:.0f}%  \n"
                            f"Risks: {', '.join(pbz.risks)}")
            if plan.off_season_strategy:
                oss = plan.off_season_strategy
                st.markdown(f"**Off-season window:** {oss.target_off_season_window}  \n"
                            f"Price premium: {oss.expected_price_premium_pct:.0f}%  \n"
                            f"Extra investment: {oss.additional_investment_inr}")
            if plan.pollination_strategy:
                ps = plan.pollination_strategy
                st.markdown(f"**Pollination:** {ps.method} — {ps.details}  \n"
                            f"Expected yield boost: {ps.expected_yield_boost_pct:+.0f}%")
            if plan.coppice_strategy:
                cs = plan.coppice_strategy
                st.markdown(f"**Coppice:** {cs.coppice_cycles} cycles × {cs.rotation_cycle_years} yr  \n"
                            f"Yield per cycle: {', '.join([f'{p:.0f}%' for p in cs.yield_per_cycle_pct])}")

        # Section 6: Harvest & Post-harvest
        with st.expander("6. Harvest & Post-harvest"):
            hp = plan.harvest_and_postharvest
            st.markdown(f"**Maturity indicators:** {', '.join(hp.maturity_indicators) if isinstance(hp.maturity_indicators, list) else hp.maturity_indicators}  \n"
                        f"**Method:** {hp.harvest_method}  \n"
                        f"**Storage:** {hp.storage_notes}")
            if hp.post_harvest_steps:
                for step in hp.post_harvest_steps:
                    st.markdown(f"- {step}")
            if plan.buyback_contract_strategy:
                bc = plan.buyback_contract_strategy
                st.markdown(f"**Buyback contract:** {bc.recommended_buyer} — {bc.contract_duration_years} yr  \n"
                            f"Pricing: {bc.pricing_mechanism}  \n"
                            f"Rationale: {bc.rationale}")

        # Section 7: Economics
        with st.expander("7. Economics & Cash Flow"):
            if plan.yield_benchmarks:
                bm_rows = [{"Year": b.year, f"Low ({b.unit})": b.low_yield,
                            f"High ({b.unit})": b.high_yield, "Notes": b.notes}
                           for b in plan.yield_benchmarks]
                st.markdown("**Yield benchmarks**")
                st.dataframe(pd.DataFrame(bm_rows), use_container_width=True, hide_index=True)
            if plan.decadal_cash_flow:
                cf_rows = [{"Year": c.year, "Investment (₹)": c.investment_inr,
                            "Revenue (₹)": c.revenue_inr, "Net (₹)": c.net_inr, "Notes": c.notes}
                           for c in plan.decadal_cash_flow]
                st.markdown("**Cash flow**")
                st.dataframe(pd.DataFrame(cf_rows), use_container_width=True, hide_index=True)
            bcomp = plan.benchmark_comparison
            st.markdown(f"**Your target:** {bcomp.target} {bcomp.unit}  |  "
                        f"District avg: {bcomp.district_average}  |  State best: {bcomp.state_best}  \n"
                        f"{bcomp.gap_analysis}")
            if plan.carbon_credit_potential:
                cc = plan.carbon_credit_potential
                st.info(f"**Carbon credits:** {cc.scheme_name} — {cc.estimated_tco2e_per_acre_per_year} tCO₂e/acre/yr → "
                        f"₹{cc.revenue_inr_per_acre_per_year}/acre/yr via {cc.certification_body}. {', '.join(cc.caveats) if isinstance(cc.caveats, list) else cc.caveats}")

        # Section 8: Risks & Optimization Levers
        with st.expander("8. Risks & Optimization Levers"):
            if plan.risk_register:
                risk_rows = [{"Risk": r.risk, "Probability": r.probability,
                              "Impact": r.impact, "Mitigation": r.mitigation}
                             for r in plan.risk_register]
                st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)
            if plan.optimization_levers:
                st.markdown("**Top levers (ranked by priority)**")
                for lv in sorted(plan.optimization_levers, key=lambda x: x.ranked_priority):
                    st.markdown(f"**{lv.ranked_priority}. {lv.lever}** — ↑{lv.yield_uplift_pct:.0f}% yield · "
                                f"₹{lv.investment_inr} · {lv.payback} · {lv.difficulty}")

        # Section 9: Critique
        with st.expander("9. Devil's Advocate Critique"):
            crit = plan.critique
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Why target IS realistic:**")
                for r in crit.why_target_is_realistic:
                    st.markdown(f"✅ {r}")
            with col2:
                st.markdown("**Why target might NOT be realistic:**")
                for r in crit.why_target_might_NOT_be_realistic:
                    st.markdown(f"⚠️ {r}")
            st.metric("Overall confidence", f"{crit.overall_confidence:.2f}")
            st.caption(f"Biggest yield gap driver: {crit.biggest_yield_gap_driver}")

        # Download markdown
        st.divider()
        md_lines = [f"# Yield Optimizer Plan — {plan.focused_crop} ({plan.focused_variety})",
                    f"Farmer: {plan.farmer_id} | Acres: {plan.focused_acres} | Stage: {plan.current_stage}",
                    f"Confidence: {plan.critique.overall_confidence:.2f}",
                    "", "---", "",
                    f"## Variety Rationale", plan.variety_rationale,
                    "", "## Biggest Yield Gap Driver", plan.critique.biggest_yield_gap_driver,
                    ]
        st.download_button("⬇️ Download plan (Markdown)", "\n".join(md_lines),
                           file_name=f"yield_plan_{plan.plan_id}.md", mime="text/markdown")


# =====================================================================
# Page: View Plan
# =====================================================================

def page_view_plan():
    st.title("Farm Plan")
    plan: engine.FarmPlan | None = st.session_state.get("current_plan")
    score: engine.SustainabilityScore | None = st.session_state.get("current_score")

    if not plan:
        # Try loading the most recent for current farmer
        if st.session_state.current_farmer_id:
            plans = engine.load_plans_for_farmer(st.session_state.current_farmer_id)
            if plans:
                plan = engine.load_plan(st.session_state.current_farmer_id, plans[0].plan_id)
                score = engine.score_sustainability(plan)
                st.session_state.current_plan = plan
                st.session_state.current_score = score

    if not plan:
        st.warning("No plan yet — generate one in **Generate Plan**.")
        return

    if not score:
        score = engine.score_sustainability(plan)

    # Multi-option panel above the tabs (if we have 3-option result)
    result: engine.FarmPlanResult | None = st.session_state.get("current_result")
    if result is not None:
        st.subheader("3-option comparison")
        st.info(f"**Recommended**: {result.recommended_option}  ·  "
                f"{result.recommendation_reasoning}")
        cmp_cols = st.columns(3)
        for i, opt in enumerate(result.options):
            with cmp_cols[i]:
                emoji = "🏆 " if opt.risk_profile == result.recommended_option else ""
                st.markdown(f"### {emoji}{opt.risk_profile.title()}")
                st.metric("Confidence", f"{opt.critique.overall_confidence:.2f}")
                st.caption(f"{len(opt.plan.crops)} crops · "
                           f"{len(opt.plan.livestock)} livestock")
                st.caption(f"**Biggest risk**: {opt.critique.biggest_risk[:80]}...")
                if st.button(f"View this", key=f"view_{opt.risk_profile}"):
                    st.session_state.current_plan = opt.plan
                    st.session_state.current_critique = opt.critique
                    st.session_state.current_score = engine.score_sustainability(opt.plan)
                    st.rerun()
        st.divider()

    critique: engine.PlanCritique | None = st.session_state.get("current_critique")
    has_critique = critique is not None
    tab_labels = [
        "Summary",
        f"Crops ({len(plan.crops)})",
        f"Livestock ({len(plan.livestock)})",
        "Apiary" if plan.apiary else "Apiary (n/a)",
        f"Sustainability ({len(plan.sustainability_practices)})",
        "Cash Flow",
        "Subsidies & Suppliers",
        "Next Steps",
        "Download",
    ]
    if has_critique:
        tab_labels.insert(1, "🎯 Devil's Advocate")
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        st.subheader("Plan Summary")
        st.write(plan.plan_summary)
        st.caption(f"Plan ID: `{plan.plan_id}`  ·  Farmer: `{plan.farmer_id}`  ·  "
                   f"Generated: {plan.generated_at[:19]}")
        st.divider()
        st.markdown(f"**Sustainability score: {score.composite_0_to_100:.1f} / 100**")
        cols = st.columns(5)
        cols[0].metric("Soil", f"{score.soil_health_0_to_20:.0f}/20")
        cols[1].metric("Water", f"{score.water_efficiency_0_to_20:.0f}/20")
        cols[2].metric("Biodiv", f"{score.biodiversity_0_to_20:.0f}/20")
        cols[3].metric("Carbon", f"{score.carbon_balance_0_to_20:.0f}/20")
        cols[4].metric("Self-suff", f"{score.input_self_sufficiency_0_to_20:.0f}/20")
        st.divider()
        if plan.risk_diversification_strategy:
            st.subheader("Risk Diversification")
            st.write(plan.risk_diversification_strategy)
        if plan.organic_transition_path:
            st.subheader("Organic Transition Path")
            st.write(plan.organic_transition_path)
        if plan.pilot_recommendation:
            st.info(f"**Pilot recommendation**: {plan.pilot_recommendation}")
        if plan.disclaimers:
            st.warning("**Disclaimers**\n\n" + "\n\n".join(plan.disclaimers))

    # Critique tab (only present when critique exists)
    next_tab_idx = 1
    if has_critique:
        with tabs[1]:
            st.subheader("🎯 Devil's Advocate Critique")
            st.metric("Overall confidence", f"{critique.overall_confidence:.2f}",
                      help="Honest probability this plan delivers stated goals.")
            st.error(f"**Biggest risk**: {critique.biggest_risk}")
            cols = st.columns(2)
            with cols[0]:
                st.markdown("### ✅ Why it might work")
                for x in critique.why_it_might_work:
                    st.markdown(f"- {x}")
            with cols[1]:
                st.markdown("### ❌ Why it might NOT work")
                for x in critique.why_it_might_NOT_work:
                    st.markdown(f"- {x}")
            st.divider()
            st.markdown("### 📋 Key assumptions")
            for x in critique.key_assumptions:
                st.markdown(f"- {x}")
        next_tab_idx = 2

    with tabs[next_tab_idx]:
        st.subheader("Crops")
        if plan.crops:
            df = pd.DataFrame([{
                "Crop": c.crop_name + (f" ({c.variety})" if c.variety else ""),
                "Role": c.role.replace("_", " "),
                "Acres": c.acres_allocated,
                "1st yield (yr)": c.time_to_first_yield_years,
                "Peak (yr)": f"{c.peak_production_year_start}-{c.peak_production_year_end}",
                "Y1 invest": c.year_1_investment_inr,
                "Peak rev/ac": c.revenue_per_acre_at_peak_inr,
                "Breakeven": f"Y{c.breakeven_year}",
                "Confidence": f"{c.confidence_meta:.2f}",
            } for c in plan.crops])
            st.dataframe(df, use_container_width=True, hide_index=True)

            for c in plan.crops:
                with st.expander(f"{c.crop_name}" + (f" — {c.variety}" if c.variety else "")):
                    cols = st.columns(2)
                    with cols[0]:
                        st.write("**Why it fits:**")
                        for w in c.why_it_fits:
                            st.write(f"- {w}")
                    with cols[1]:
                        st.write("**Risk flags:**")
                        for r in c.risk_flags:
                            st.write(f"- {r}")
                    if c.market_channels:
                        st.write("**Market channels:** " + ", ".join(c.market_channels))
                    if c.govt_subsidies_available:
                        st.write("**Govt subsidies:** " + ", ".join(c.govt_subsidies_available))
                    if c.suppliers_known:
                        st.write("**Suppliers:** " + ", ".join(c.suppliers_known))
                    st.caption(f"Confidence: self={c.confidence_self:.2f} · meta={c.confidence_meta:.2f} · "
                               f"exotic={c.is_exotic_high_value} · pollinator-friendly={c.pollinator_friendly}")
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        st.subheader("Livestock")
        if not plan.livestock:
            st.info("No livestock in this plan.")
        else:
            df = pd.DataFrame([{
                "Type": l.type, "Breed": l.breed, "Count": l.count,
                "Space (sqft)": l.space_required_sqft,
                "Daily feed (kg)": l.daily_feed_kg,
                "Monthly net": l.monthly_net_inr_range,
                "Breakeven (mo)": l.breakeven_months,
            } for l in plan.livestock])
            st.dataframe(df, use_container_width=True, hide_index=True)
            for l in plan.livestock:
                if l.integration_with_crops:
                    st.write(f"**{l.type} {l.breed} integration:** " +
                             ", ".join(l.integration_with_crops))
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        if plan.apiary:
            a = plan.apiary
            st.subheader("Apiary")
            st.write(f"**Species:** {a.bee_species}")
            st.write(f"**Boxes:** {a.bee_box_count}")
            st.write(f"**Placement:** {a.placement_strategy}")
            st.write(f"**Yield:** {a.expected_yield_kg_per_box_per_year} kg/box/year")
            st.write(f"**Revenue:** {a.expected_revenue_inr_per_year}")
            st.write(f"**Pollination benefit to:** " + ", ".join(a.pollination_benefit_to_crops))
            st.caption(f"MIDH subsidy eligible: {a.midh_subsidy_eligibility}")
        else:
            st.info("No apiary in this plan.")
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        st.subheader("Sustainability Practices")
        for p in plan.sustainability_practices:
            with st.expander(p.practice.replace("_", " ").title()):
                st.write(p.why_it_fits)
                cols = st.columns(2)
                cols[0].write(f"**Investment:** {p.investment_inr}")
                cols[1].write(f"**Payback:** {p.payback_period}")
                if p.govt_schemes_applicable:
                    st.write("**Govt schemes:** " + ", ".join(p.govt_schemes_applicable))

        st.divider()
        if score.recommendations:
            st.subheader("To improve the score")
            for r in score.recommendations:
                st.write(f"- {r}")
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        st.subheader("10-Year Cash Flow")
        if plan.year_by_year_cash_flow:
            df = pd.DataFrame([{
                "Year": f"Y{y.year}",
                "Investment": y.investment_inr_total,
                "Revenue": y.revenue_inr_range,
                "Net": y.net_inr_range,
                "Notes": y.notes,
            } for y in plan.year_by_year_cash_flow])
            st.dataframe(df, use_container_width=True, hide_index=True)
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        cols = st.columns(2)
        with cols[0]:
            st.subheader("Govt subsidies to pursue")
            for s in plan.govt_subsidies_to_pursue:
                st.write(f"- {s}")
            st.subheader("Suppliers to contact")
            for s in plan.suppliers_to_contact:
                st.write(f"- {s}")
        with cols[1]:
            st.subheader("Market channels to develop")
            for m in plan.market_channels_to_develop:
                st.write(f"- {m}")
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        st.subheader("Next 30 Days — Action Items")
        for s in plan.immediate_next_steps:
            st.checkbox(s, key=f"todo_{s}")
    next_tab_idx += 1

    with tabs[next_tab_idx]:
        st.subheader("Download")
        md = engine.render_plan_markdown(plan, score)
        st.download_button(
            "Download as Markdown",
            data=md,
            file_name=f"farm_plan_{plan.plan_id}.md",
            mime="text/markdown",
        )
        if st.button("Generate PDF"):
            with st.spinner("Rendering PDF..."):
                with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    pdf_path = Path(tmp.name)
                engine.render_plan_pdf(plan, pdf_path, score)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download PDF",
                        data=f.read(),
                        file_name=f"farm_plan_{plan.plan_id}.pdf",
                        mime="application/pdf",
                    )


# =====================================================================
# Page: Sustainability Audit (standalone)
# =====================================================================

def page_sust_audit():
    st.title("Sustainability Audit (standalone)")
    plan: engine.FarmPlan | None = st.session_state.get("current_plan")
    if not plan:
        st.info("Generate a plan first to score its sustainability.")
        return
    score = engine.score_sustainability(plan)

    st.metric("Composite score", f"{score.composite_0_to_100:.1f} / 100")
    cols = st.columns(5)
    cols[0].metric("Soil health", f"{score.soil_health_0_to_20:.0f} / 20")
    cols[1].metric("Water efficiency", f"{score.water_efficiency_0_to_20:.0f} / 20")
    cols[2].metric("Biodiversity", f"{score.biodiversity_0_to_20:.0f} / 20")
    cols[3].metric("Carbon balance", f"{score.carbon_balance_0_to_20:.0f} / 20")
    cols[4].metric("Input self-suff", f"{score.input_self_sufficiency_0_to_20:.0f} / 20")

    st.divider()
    if score.recommendations:
        st.subheader("Recommendations to lift the score")
        for r in score.recommendations:
            st.write(f"- {r}")

    if score.composite_0_to_100 >= 80:
        st.success("**Strong regenerative practice.** Certified-organic pathway viable.")
    elif score.composite_0_to_100 >= 60:
        st.info("Good baseline. Clear improvement opportunities exist.")
    elif score.composite_0_to_100 >= 40:
        st.warning("Conventional with some sustainability. Substantial room to grow.")
    else:
        st.error("Heavy chemical/input dependence. High opportunity for transition.")


# =====================================================================
# Page: About
# =====================================================================

def page_about():
    st.title("About")
    st.markdown(
        """
**Suryapet Farm Planner** — Session 22 of the [AgenticCourse](https://github.com/SreeGD/AgenticCourse) curriculum.

### What this is
A knowledge-grounded farm-planning advisor for Telangana smallholder + commercial farmers.
Embeds ~7K tokens of regional expertise (variety economics, climate envelope, soil types,
govt schemes, suppliers, market channels) into a Claude system prompt so the advisor
gives **Suryapet-specific** advice, not generic LLM output.

### Districts covered
- **Suryapet** — semi-arid, red soil + chalka, 731mm rainfall
- **Jangaon** — black cotton dominant, drier (680mm)
- **Nalgonda** — Krishna canal command area, alluvial + red mix, 750-800mm

### Architecture
- **Engine** (`34_farm_planner_engine.py`) — pure Python, no UI deps; reusable
- **Streamlit UI** (this app) — thin wrapper for local use
- **FastAPI stub** (`34_farm_planner_api.py`) — REST API ready for the future React/mobile frontend

When you swap UI from Streamlit to React, the engine is unchanged.

### Data + Privacy
Profiles + plans saved as JSON files in `farm_profiles/` and `farm_plans/`. None are committed
to git except the three sample profiles. Real farmer data stays local.

### Not what this is
- Not a replacement for KVK / agricultural officer consultation
- Not a real-time mandi price feed (price ranges are baked in from public data)
- Not a govt scheme application form
- Not a guarantee of yields or revenues

Every plan includes the disclaimer to validate with local extension services before
investment.
        """
    )


# =====================================================================
# Router
# =====================================================================

PAGES = {
    "Home": page_home,
    "Farm Profile": page_profile,
    "Goals & Constraints": page_goals,
    "Generate Plan": page_generate,
    "Yield Optimizer": page_yield_optimizer,
    "View Plan": page_view_plan,
    "Sustainability Audit": page_sust_audit,
    "About": page_about,
}

PAGES[page]()
