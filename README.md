# Construction Project Analytics

A Power Query + Power BI dashboard that monitors 12 construction projects across budget, schedule, workforce, materials and cost — and flags risk early instead of only reporting after the fact.

## Project Objective

Combine project, worker, material, cost and daily progress data into one model to answer:
- Which projects are over budget or behind schedule?
- Where is labor cost high but productivity low?
- Which materials and suppliers are driving overuse?
- Which projects need attention *now*, not at close-out?

## Tools

- **Power BI Desktop** — data model, DAX, report
- **Power Query** — cleaning and transformation
- **Python** (pandas, numpy, faker) — synthetic dataset generation
- **Excel** — source data format

## Folder Structure

```
Construction_Analytics/
├── 01_data_generation/generate_data.py
├── 02_raw_data/
│   ├── Projects.csv, Workers.csv, Materials.csv, Daily_Progress.csv
│   └── Expenses/ (18 monthly files, Jan 2025 – Jun 2026)
├── 03_powerbi/Construction_Analytics.pbix
├── 04_ml_extension/  (planned)
└── README.md
```

## Datasets

| Table | Rows (approx) | Grain |
|---|---|---|
| Projects | 12 | one row per project |
| Workers | 130+ | one row per worker per project |
| Materials | 240+ | one row per material purchase |
| Daily_Progress | 2,700+ | one row per project per work day |
| Expenses | 1,500+ | one row per expense transaction |

Data was intentionally generated with realistic dirt: duplicate rows, inconsistent casing/spacing in names and categories, missing values, and a few negative quantities — all fixed in Power Query below.

## Power Query Cleaning (by table)

**Projects**
- Trimmed and capitalized `Project Name`; standardized `Project Status` (e.g. "in progress" → "In Progress")
- Filled missing `Project Manager` with "Unassigned"
- Removed duplicate rows
- Added calculated columns: `Project Duration (Days)`, `Delay Days`, `Cost Variance`

**Workers**
- Stripped `%` from `Attendance` and converted to Decimal Number
- Trimmed/capitalized `Job Role`
- Filled missing `Work Hours` / `Overtime Hours` with 0
- Removed duplicates
- Added `Labor Cost` = (Work Hours × hourly rate) + 1.5× overtime pay

**Materials**
- Fixed negative `Quantity Used` with `Number.Abs()`
- Trimmed/capitalized `Material Name`
- Filled missing `Supplier` with "Unknown"
- Removed duplicates
- Added `Material Cost` and `Material Wastage %`

**Daily_Progress**
- Filled missing `Actual Progress %` using Fill Down (progress is cumulative, so it shouldn't reset to 0)
- Removed duplicates
- Added `Progress Gap` = Actual − Planned

**Expenses**
- Combined 18 monthly CSVs via Get Data → Folder → Combine & Transform (demonstrates Append)
- Standardized `Expense Category` (e.g. "labour"/"LABOR" → "Labor") — down to a clean 6 categories
- Filled missing `Vendor` with "Unknown", removed blank-amount rows
- Removed duplicates
- Added `Year`, `Month`, `Month Name`

## Data Model

Star schema: `Projects` is the central table, with `Workers`, `Materials`, `Daily_Progress` and `Expenses` joined on `Project ID` (many-to-one). A standalone `Calendar` table links to `Daily_Progress[Date]` and `Expenses[Date]` for consistent time-based filtering.

## Key DAX Measures

- `Cost Variance Total`, `Cost Variance %` — budget vs actual
- `Avg Planned Progress`, `Avg Actual Progress`, `Progress Gap`
- `Productivity` = Completed Units ÷ Total Work Hours
- `Wastage %` = (Used − Planned) ÷ Planned, by material
- `Budget Used %` = Total Expenses ÷ Total Planned Budget
- `Project Risk Status` — combines cost overrun + schedule slip into a single 🔴/🟠/🟢 flag per project

## Dashboard Pages

1. **Executive Overview** — KPI cards, project status donut, budget vs actual, progress trend, per-project risk table
2. **Project Performance** — planned vs actual progress by project, cost variance chart, delayed projects list, drill-through from Overview
3. **Workforce Analytics** — labor cost, productivity, attendance, overtime, headcount by role
4. **Material Analytics** — wastage % by material, supplier performance, excess material cost
5. **Cost Analysis** — expense breakdown by category, monthly spend trend, budget used % per project
6. **Early Warning** — combined risk flag board (cost, schedule, material, overtime) with slicers by status and location

## Key Insights

- **12 projects** total — 7 In Progress, 4 Completed, 1 On Hold. Overall cost variance is **-22.22%** at the portfolio level, but this blends large overruns on a few projects with early-stage underspend on others — the per-project view tells the real story.
- **5 projects are flagged High Risk**: Central School Complex, Eastgate Warehouse, Greenfield Residency, Metro Plaza Mall, and Skyline Tower — all showing both cost overrun and schedule slip.
- **Central School Complex, Eastgate Warehouse, Greenfield Residency, Skyline Tower** have already exceeded 100% of planned budget in spend to date (Budget Used % from 105% to 118%).
- **Metro Plaza Mall and Central School Complex** combine high labor cost with comparatively low productivity — the exact pattern the Workforce page was built to surface.
- **Cement, PVC Pipes and Sand** show the highest material wastage %, with Apex Materials and Delta Supplies contributing the largest excess material cost.
- **Central School Complex and Metro Plaza Mall** also carry the highest overtime ratios, both flagged 🟠 High Overtime on the Early Warning page.

## Known Limitations

- Cost Variance and Budget Used % compare spend-to-date against the **full** planned budget for in-progress projects, so a low percentage there just reflects an early project stage, not savings. Flags are most meaningful for Completed projects.
- `Total Expenses` (Expenses table) differs slightly from `Total Actual Cost` (Projects table) — a normal side effect of removing duplicate/blank rows during cleaning.
- The Early Warning donut chart uses a calculated column (`Risk Level`), so it doesn't respond to page slicers the way the flag table does.
- Bricks dominates the "Planned vs Used" quantity chart on Material Analytics since units aren't normalized across materials — Wastage % is the more reliable comparison.

## Possible Extensions

- **Construction Project Risk Prediction**: use the cleaned historical data to train a model predicting delay probability, cost overrun probability, and expected completion time (Python + scikit-learn), feeding predictions back into Power BI.
- Normalize an amber "at risk" tier (90–100% budget used) alongside the current red/green split.
- Publish to Power BI Service for a shareable link.
