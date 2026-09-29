"""
Construction Project Analytics - synthetic data generator
---------------------------------------------------------
Creates 5 linked raw datasets (Projects, Workers, Materials, Daily Progress,
Expenses) with INTENTIONALLY messy data so Power Query cleaning is meaningful.

Run:  python generate_data.py
Output: ../02_raw_data/*.csv  (Expenses are split into monthly files)

Requires: pandas, numpy
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

AS_OF = pd.Timestamp("2026-06-30")  # "today" for the dataset
BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "02_raw_data"
(RAW / "Expenses").mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# 1. Project definitions (clean "truth")
# --------------------------------------------------------------------------
# status: Completed / In Progress / On Hold
# delay : days late (negative = early) for completed projects
# speed : progress speed vs plan for unfinished projects (<1 = behind)
# ovr   : cost overrun factor (1.10 = 10% over budget at the same progress)
PROJECTS = [
    dict(id="P001", name="Skyline Tower", loc="Downtown", mgr="Michael Reeves",
         start="2025-01-06", end="2025-11-28", budget=48_000_000,
         status="Completed", delay=25, ovr=1.12),
    dict(id="P002", name="Harbor Bridge Retrofit", loc="Harbor District", mgr="Sarah Collins",
         start="2025-02-03", end="2025-10-31", budget=32_000_000,
         status="Completed", delay=-5, ovr=0.97),
    dict(id="P003", name="Greenfield Residency", loc="North Hills", mgr="David Turner",
         start="2025-03-10", end="2026-03-31", budget=27_000_000,
         status="Completed", delay=40, ovr=1.18),
    dict(id="P004", name="Metro Plaza Mall", loc="City Center", mgr="Emily Brooks",
         start="2025-04-01", end="2026-06-15", budget=55_000_000,
         status="In Progress", speed=0.85, ovr=1.15),
    dict(id="P005", name="Lakeview Apartments", loc="Lakeview", mgr="Robert Hayes",
         start="2025-05-05", end="2026-08-30", budget=22_000_000,
         status="In Progress", speed=0.95, ovr=0.98),
    dict(id="P006", name="Riverside Hospital Wing", loc="Riverside", mgr="Sarah Collins",
         start="2025-06-02", end="2026-12-18", budget=41_000_000,
         status="In Progress", speed=1.05, ovr=1.05),
    dict(id="P007", name="Tech Park Phase 1", loc="Tech Corridor", mgr="Michael Reeves",
         start="2025-07-07", end="2027-01-29", budget=60_000_000,
         status="In Progress", speed=0.80, ovr=1.02),
    dict(id="P008", name="Central School Complex", loc="City Center", mgr="Emily Brooks",
         start="2025-08-04", end="2026-07-31", budget=18_000_000,
         status="In Progress", speed=0.82, ovr=1.22),
    dict(id="P009", name="Eastgate Warehouse", loc="Eastgate", mgr="David Turner",
         start="2025-09-01", end="2026-05-29", budget=14_000_000,
         status="Completed", delay=20, ovr=1.08),
    dict(id="P010", name="Sunrise Villas", loc="North Hills", mgr="Robert Hayes",
         start="2025-10-06", end="2027-02-26", budget=30_000_000,
         status="In Progress", speed=0.98, ovr=0.95),
    dict(id="P011", name="City Water Pipeline", loc="Harbor District", mgr="Sarah Collins",
         start="2025-11-03", end="2027-03-31", budget=25_000_000,
         status="On Hold", speed=0.90, ovr=1.00, hold="2026-02-27"),
    dict(id="P012", name="Airport Road Flyover", loc="Airport Zone", mgr="Emily Brooks",
         start="2026-01-12", end="2027-06-30", budget=45_000_000,
         status="In Progress", speed=1.02, ovr=0.90),
]

# Projects with heavy overtime (drives the "High Overtime" warning)
HIGH_OT = {"P004": 1.9, "P008": 2.1}


def s_curve(f):
    f = np.clip(f, 0, 1)
    return 3 * f**2 - 2 * f**3


def work_type(pct):
    if pct < 12:
        pool = ["Excavation", "Foundation"]
    elif pct < 45:
        pool = ["Foundation", "Structure", "Structure"]
    elif pct < 70:
        pool = ["Structure", "Masonry", "Electrical", "Plumbing"]
    else:
        pool = ["Electrical", "Plumbing", "Finishing", "Finishing"]
    return rng.choice(pool)


# --------------------------------------------------------------------------
# 2. Daily progress (built first: it defines each project's real end date)
# --------------------------------------------------------------------------
progress_rows = []
proj_info = {}

for p in PROJECTS:
    start = pd.Timestamp(p["start"])
    planned_end = pd.Timestamp(p["end"])
    planned_dur = (planned_end - start).days

    if p["status"] == "Completed":
        actual_end = planned_end + pd.Timedelta(days=p["delay"])
        last_day = actual_end
    elif p["status"] == "On Hold":
        actual_end = None
        last_day = pd.Timestamp(p["hold"])
    else:
        actual_end = None
        last_day = AS_OF

    days = pd.bdate_range(start, last_day)
    t = (days - start).days.values.astype(float)

    planned = s_curve(t / planned_dur) * 100
    if actual_end is not None:
        actual_dur = (actual_end - start).days
        actual = s_curve(t / actual_dur) * 100
    else:
        actual = np.minimum(s_curve(t * p["speed"] / planned_dur) * 100, 99.0)

    actual = actual + rng.normal(0, 0.5, len(actual))
    actual = np.clip(np.maximum.accumulate(actual), 0, 100)
    if actual_end is not None:
        actual[-1] = 100.0

    total_units = p["budget"] / 5000
    units = np.diff(actual, prepend=0) / 100 * total_units
    units = np.clip(units * rng.normal(1, 0.15, len(units)), 0, None)

    for d, pl, ac, un in zip(days, planned, actual, units):
        progress_rows.append({
            "Project ID": p["id"],
            "Date": d.strftime("%Y-%m-%d"),
            "Work Type": work_type(ac),
            "Planned Progress %": round(pl, 2),
            "Actual Progress %": round(ac, 2),
            "Completed Units": round(un, 1),
        })

    proj_info[p["id"]] = dict(
        start=start, last_day=last_day, actual_end=actual_end,
        workdays=len(days), final_actual=float(actual[-1]), days=days,
    )

progress = pd.DataFrame(progress_rows)

# --------------------------------------------------------------------------
# 3. Expenses
# --------------------------------------------------------------------------
CATEGORIES = ["Labor", "Materials", "Equipment", "Transportation", "Maintenance", "Other"]
CAT_P = [0.30, 0.35, 0.15, 0.06, 0.06, 0.08]
VENDORS = {
    "Labor": ["BuildForce Staffing", "SiteCrew Contractors", "ProLabor Services"],
    "Materials": ["Apex Materials", "Prime Steel & Cement", "UrbanBuild Supply"],
    "Equipment": ["HeavyLift Rentals", "CraneWorks", "MachineHub"],
    "Transportation": ["FastHaul Logistics", "RoadRunner Freight"],
    "Maintenance": ["FixIt Maintenance", "SafeSite Services"],
    "Other": ["General Vendor", "Permit Office", "SafetyFirst Supplies"],
}
DESCRIPTIONS = {
    "Labor": ["Weekly labor payment", "Subcontractor invoice", "Skilled crew payment"],
    "Materials": ["Bulk material purchase", "Material top-up order", "Site material delivery"],
    "Equipment": ["Excavator rental", "Crane hire", "Scaffolding rental"],
    "Transportation": ["Material transport", "Debris removal", "Equipment transport"],
    "Maintenance": ["Machine servicing", "Site repair works", "Generator maintenance"],
    "Other": ["Permit and licence fees", "Safety gear", "Site office expenses"],
}

targets = {}
for p in PROJECTS:
    frac = 1.0 if p["status"] == "Completed" else proj_info[p["id"]]["final_actual"] / 100
    targets[p["id"]] = p["budget"] * p["ovr"] * frac
total_target = sum(targets.values())

expense_rows = []
for p in PROJECTS:
    info = proj_info[p["id"]]
    n = max(25, int(round(targets[p["id"]] / total_target * 1500)))
    w = rng.lognormal(0, 0.8, n)
    amounts = w / w.sum() * targets[p["id"]]
    dates = rng.choice(info["days"], n)
    cats = rng.choice(CATEGORIES, n, p=CAT_P)
    for d, a, c in zip(dates, amounts, cats):
        expense_rows.append({
            "Project ID": p["id"],
            "Date": pd.Timestamp(d).strftime("%Y-%m-%d"),
            "Expense Category": c,
            "Description": rng.choice(DESCRIPTIONS[c]),
            "Amount": round(float(a), 2),
            "Vendor": rng.choice(VENDORS[c]),
        })

expenses = pd.DataFrame(expense_rows)
actual_cost = expenses.groupby("Project ID")["Amount"].sum().round(2)

# --------------------------------------------------------------------------
# 4. Projects table
# --------------------------------------------------------------------------
proj_rows = []
for p in PROJECTS:
    info = proj_info[p["id"]]
    proj_rows.append({
        "Project ID": p["id"],
        "Project Name": p["name"],
        "Location": p["loc"],
        "Project Manager": p["mgr"],
        "Start Date": p["start"],
        "Planned End Date": p["end"],
        "Actual End Date": info["actual_end"].strftime("%Y-%m-%d") if info["actual_end"] is not None else np.nan,
        "Planned Budget": p["budget"],
        "Actual Cost": actual_cost[p["id"]],
        "Project Status": p["status"],
    })
projects = pd.DataFrame(proj_rows)

# --------------------------------------------------------------------------
# 5. Workers
# --------------------------------------------------------------------------
FIRST = ["Ravi", "Anil", "James", "Carlos", "Mohan", "Peter", "Samuel", "Karthik", "Luis", "Omar",
         "Daniel", "Vikram", "Joseph", "Ahmed", "Ben", "Suresh", "Marcus", "Hassan", "Tom", "Ali"]
LAST = ["Kumar", "Singh", "Smith", "Garcia", "Patel", "Khan", "Johnson", "Silva", "Brown", "Nair",
        "Lopez", "Reddy", "Wilson", "Sharma", "Davis", "Iyer", "Miller", "Das", "Moore", "Rao"]
ROLES = {
    "Laborer": 600, "Mason": 900, "Carpenter": 850, "Electrician": 1000, "Plumber": 950,
    "Crane Operator": 1300, "Site Engineer": 1800, "Supervisor": 1500,
}
ROLE_P = [0.32, 0.16, 0.14, 0.08, 0.08, 0.05, 0.07, 0.10]

total_budget = sum(p["budget"] for p in PROJECTS)
worker_rows = []
wid = 1
for p in PROJECTS:
    info = proj_info[p["id"]]
    n = max(6, int(round(p["budget"] / total_budget * 130)))
    ot_rate = HIGH_OT.get(p["id"], rng.uniform(0.3, 1.0))
    for _ in range(n):
        role = rng.choice(list(ROLES), p=ROLE_P)
        join_frac = rng.uniform(0.5, 1.0)
        att = rng.uniform(82, 98)
        present_days = info["workdays"] * join_frac * att / 100
        worker_rows.append({
            "Worker ID": f"W{wid:03d}",
            "Worker Name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "Project ID": p["id"],
            "Job Role": role,
            "Work Hours": int(present_days * 8 * rng.uniform(0.95, 1.0)),
            "Overtime Hours": int(present_days * ot_rate * rng.uniform(0.7, 1.3)),
            "Attendance": round(att, 1),
            "Daily Wage": round(ROLES[role] * rng.uniform(0.9, 1.1), 0),
        })
        wid += 1
workers = pd.DataFrame(worker_rows)

# --------------------------------------------------------------------------
# 6. Materials
# --------------------------------------------------------------------------
MATERIALS = {  # name: (base qty per 10M budget, unit cost)
    "Cement": (2500, 420), "Steel Rebar": (900, 6200), "Sand": (1800, 1100),
    "Bricks": (60000, 9), "Concrete Mix": (1200, 5200), "Paint": (700, 380),
    "Tiles": (5000, 65), "PVC Pipes": (1500, 210), "Electrical Cable": (3000, 95),
    "Timber": (800, 1500), "Glass Panels": (300, 2400),
}
SUPPLIERS = ["Apex Materials", "Prime Steel & Cement", "UrbanBuild Supply",
             "GreenBuild Traders", "Metro Hardware", "Delta Supplies"]

mat_rows = []
mid = 1
for p in PROJECTS:
    info = proj_info[p["id"]]
    use_mean = 0.95 + (p["ovr"] - 0.9) * 0.6
    for _ in range(20):
        name = rng.choice(list(MATERIALS))
        base_qty, unit_cost = MATERIALS[name]
        planned = base_qty * p["budget"] / 10_000_000 * rng.uniform(0.3, 0.8)
        used = planned * float(np.clip(rng.normal(use_mean, 0.06), 0.8, 1.5))
        purchase = pd.Timestamp(rng.choice(info["days"]))
        mat_rows.append({
            "Material ID": f"M{mid:04d}",
            "Project ID": p["id"],
            "Material Name": name,
            "Quantity Planned": int(planned),
            "Quantity Used": int(used),
            "Unit Cost": round(unit_cost * rng.uniform(0.95, 1.08), 2),
            "Supplier": rng.choice(SUPPLIERS),
            "Purchase Date": purchase.strftime("%Y-%m-%d"),
        })
        mid += 1
materials = pd.DataFrame(mat_rows)


# --------------------------------------------------------------------------
# 7. Inject realistic dirt
# --------------------------------------------------------------------------
def add_duplicates(df, n):
    dups = df.sample(n, random_state=SEED)
    return pd.concat([df, dups]).sort_index(kind="stable").reset_index(drop=True)


# Projects: inconsistent names / status, missing manager, duplicates
projects.loc[0, "Project Name"] = " skyline tower"
projects.loc[3, "Project Name"] = "METRO PLAZA MALL"
projects.loc[5, "Project Name"] = "riverside hospital wing "
projects.loc[7, "Project Name"] = "Central School  Complex"
projects.loc[4, "Project Status"] = "in progress"
projects.loc[6, "Project Status"] = "In-Progress"
projects.loc[9, "Project Manager"] = np.nan
projects = add_duplicates(projects, 2)

# Workers: nulls, text attendance, role case variants, duplicates
workers["Attendance"] = workers["Attendance"].astype(object)
for i in rng.choice(workers.index, 8, replace=False):
    workers.at[i, "Work Hours"] = np.nan
for i in rng.choice(workers.index, 5, replace=False):
    workers.at[i, "Overtime Hours"] = np.nan
for i in rng.choice(workers.index, 10, replace=False):
    workers.at[i, "Attendance"] = f"{float(workers.at[i, 'Attendance']):.0f}%"
for i in rng.choice(workers.index, 10, replace=False):
    r = workers.at[i, "Job Role"]
    workers.at[i, "Job Role"] = rng.choice([r.lower(), r.upper(), r + " "])
workers = add_duplicates(workers, 6)

# Materials: negative qty, missing supplier, name variants, duplicates
for i in rng.choice(materials.index, 5, replace=False):
    materials.at[i, "Quantity Used"] = -abs(materials.at[i, "Quantity Used"])
for i in rng.choice(materials.index, 6, replace=False):
    materials.at[i, "Supplier"] = np.nan
for i in rng.choice(materials.index, 8, replace=False):
    m = materials.at[i, "Material Name"]
    materials.at[i, "Material Name"] = rng.choice([m.lower(), m.upper(), m + " "])
materials = add_duplicates(materials, 4)

# Progress: missing actual %, duplicates
for i in rng.choice(progress.index, 25, replace=False):
    progress.at[i, "Actual Progress %"] = np.nan
progress = add_duplicates(progress, 15)

# Expenses: category variants, blank vendor / amount, duplicates
VARIANTS = {
    "Labor": ["labour", "LABOR", "Labor "],
    "Materials": ["material", "MATERIALS"],
    "Equipment": ["equipment ", "EQUIPMENT"],
    "Transportation": ["transport", "TRANSPORTATION"],
    "Maintenance": ["maintenance ", "MAINTENANCE"],
    "Other": ["other", "Misc"],
}
for i in rng.choice(expenses.index, 60, replace=False):
    c = expenses.at[i, "Expense Category"]
    expenses.at[i, "Expense Category"] = rng.choice(VARIANTS[c])
for i in rng.choice(expenses.index, 20, replace=False):
    expenses.at[i, "Vendor"] = np.nan
for i in rng.choice(expenses.index, 10, replace=False):
    expenses.at[i, "Amount"] = np.nan
expenses = add_duplicates(expenses, 25)

# --------------------------------------------------------------------------
# 8. Save
# --------------------------------------------------------------------------
projects.to_csv(RAW / "Projects.csv", index=False)
workers.to_csv(RAW / "Workers.csv", index=False)
materials.to_csv(RAW / "Materials.csv", index=False)
progress.to_csv(RAW / "Daily_Progress.csv", index=False)

expenses["_ym"] = expenses["Date"].str[:7]
for ym, chunk in expenses.groupby("_ym"):
    fname = f"Expenses_{ym.replace('-', '_')}.csv"
    chunk.drop(columns="_ym").to_csv(RAW / "Expenses" / fname, index=False)

print("Done. Files written to:", RAW)
print(f"Projects: {len(projects)} | Workers: {len(workers)} | Materials: {len(materials)} "
      f"| Progress: {len(progress)} | Expenses: {len(expenses)} "
      f"({expenses['_ym'].nunique()} monthly files)")
