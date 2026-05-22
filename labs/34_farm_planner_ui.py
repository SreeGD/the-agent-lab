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


# =====================================================================
# Sidebar nav
# =====================================================================

st.sidebar.title(":seedling: Farm Planner")
st.sidebar.caption("Suryapet · Jangaon · Nalgonda")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Home", "Farm Profile", "Goals & Constraints", "Generate Plan",
     "View Plan", "Sustainability Audit", "About"],
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
                    "profile_synthesis": "📝 Profile synthesis + strategy (writes KB cache)",
                    "crop_intent":       "🎯 Picking crops (just names + roles)",
                    "crop_detail":       "🌾 Generating crop detail (parallel)",
                    "crop_aggregate":    "📋 Aggregating crops",
                    "livestock_apiary":  "🐄 Livestock + apiary",
                    "sustainability":    "🌱 Sustainability practices + subsidies",
                    "cashflow":          "💰 Cash flow + next steps",
                    "assemble":          "🧩 Assembling plan (deterministic)",
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
    "View Plan": page_view_plan,
    "Sustainability Audit": page_sust_audit,
    "About": page_about,
}

PAGES[page]()
