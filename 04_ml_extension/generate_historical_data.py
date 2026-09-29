"""
Construction Project Analytics - ML Extension
Step 1: Generate historical training data
----------------------------------------------
Your live dashboard only has 12 projects - not enough to train a model on.
This script generates 300 synthetic PAST/COMPLETED projects with realistic
feature -> outcome relationships (bigger budget & longer duration => higher
overrun risk, certain locations & high overtime => higher delay risk, etc.)
so the model in step 2 has something real to learn from.

Run:  python generate_historical_data.py
Output: historical_projects.csv (in this folder)
"""
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 7
rng = np.random.default_rng(SEED)
N = 300
OUT = Path(__file__).resolve().parent / "historical_projects.csv"

LOCATIONS = ["Downtown", "Harbor District", "North Hills", "City Center",
             "Lakeview", "Riverside", "Tech Corridor", "Eastgate", "Airport Zone"]
# each location gets a mild baseline risk multiplier (site conditions, permitting, etc.)
LOCATION_RISK = {loc: rng.uniform(0.85, 1.2) for loc in LOCATIONS}

rows = []
for i in range(N):
    loc = rng.choice(LOCATIONS)
    planned_budget = rng.lognormal(mean=16.7, sigma=0.55)          # ~ 1M - 90M range
    planned_duration = int(rng.uniform(120, 760))                   # days
    num_workers = max(4, int(planned_budget / rng.uniform(250_000, 450_000)))
    overtime_ratio = float(np.clip(rng.normal(0.18, 0.12), 0, 0.9))
    material_wastage_pct = float(np.clip(rng.normal(4.5, 3.0), -10, 25))
    start_month = int(rng.integers(1, 13))
    manager_experience_years = int(rng.uniform(1, 20))

    # --- true (hidden) risk signal the model has to learn ---
    risk_score = (
        0.55 * (planned_budget > 30_000_000)
        + 0.45 * (planned_duration > 450)
        + 1.30 * overtime_ratio
        + 0.06 * material_wastage_pct
        - 0.03 * manager_experience_years
        + 0.7 * (LOCATION_RISK[loc] - 1)
        + rng.normal(0, 0.55)  # noise: real projects are not fully predictable
    )
    cost_overrun = int(risk_score > 0.55)
    delayed = int(risk_score > 0.35)  # delay is a bit easier to trigger than overrun

    # realized magnitudes (only meaningful if the flag is 1, else small/negative)
    if cost_overrun:
        overrun_pct = float(np.clip(rng.normal(12, 6), 1, 40))
    else:
        overrun_pct = float(np.clip(rng.normal(-3, 4), -20, 3))

    if delayed:
        delay_days = int(np.clip(rng.normal(35, 20), 3, 180))
    else:
        delay_days = int(np.clip(rng.normal(-3, 6), -30, 5))

    rows.append({
        "Project ID": f"H{i+1:04d}",
        "Location": loc,
        "Planned Budget": round(planned_budget, 2),
        "Planned Duration Days": planned_duration,
        "Num Workers": num_workers,
        "Overtime Ratio": round(overtime_ratio, 4),
        "Material Wastage %": round(material_wastage_pct, 2),
        "Start Month": start_month,
        "Manager Experience Years": manager_experience_years,
        "Cost Overrun": cost_overrun,
        "Delayed": delayed,
        "Cost Overrun %": round(overrun_pct, 2),
        "Delay Days": delay_days,
    })

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)

print(f"Wrote {len(df)} historical projects to {OUT}")
print(f"Cost overrun rate: {df['Cost Overrun'].mean():.1%}")
print(f"Delayed rate:      {df['Delayed'].mean():.1%}")
