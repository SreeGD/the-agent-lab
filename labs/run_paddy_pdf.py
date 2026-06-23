#!/usr/bin/env python3
"""Run paddy yield optimization and generate PDF report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "yield_optimizer_engine",
    Path(__file__).parent / "agritech" / "yield_optimizer_engine.py",
)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

from agritech.yield_optimizer_engine import (
    YieldOptimizationProfile,
    generate_yield_plan,
    render_yield_plan_pdf,
)

profile = YieldOptimizationProfile(
    farmer_id="farmer_001",
    focused_crop="paddy",
    crop_type="annual_grain",
    variety_preference="BPT 5204",
    focused_acres=2.5,
    district="Jangaon",
    soil_type="black cotton",
    current_yield_qtl_per_acre=22.0,
    yield_goal_pct=30,
    investment_cap_inr=60000,
    organic_required=False,
    avoid_chemicals=False,
    labor_availability="moderate",
    water_source="bore well",
    current_stage="planning",
    parcel_notes="Single bore well, black cotton vertisol, kharif season target",
)

print("Running yield optimizer for paddy...")
plan = generate_yield_plan(profile)

output_path = Path(__file__).parent / "yield_plans" / "paddy_plan.pdf"
render_yield_plan_pdf(plan, output_path)
print(f"\nPDF saved to: {output_path}")
print(f"Plan ID: {plan.plan_id}")
print(f"Variety: {plan.focused_variety}")
print(f"Confidence: {plan.critique.overall_confidence if plan.critique else 'N/A'}")
