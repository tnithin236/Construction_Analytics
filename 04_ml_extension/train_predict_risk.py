"""
Construction Project Analytics - ML Extension
Step 2: Train risk model + predict on the 12 live projects
------------------------------------------------------------
1. Loads historical_projects.csv (synthetic training data, see step 1)
2. Trains two classifiers: Cost Overrun risk, Delay risk
3. Builds the SAME features for your 12 real projects by aggregating the
   actual cleaned CSVs in 02_raw_data (no synthetic data used for the
   live projects - only for training)
4. Predicts risk probabilities for the 12 live projects
5. Writes risk_predictions.csv, ready to re-import into Power BI as a
   7th page ("Risk Prediction")

Run:  python train_predict_risk.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "02_raw_data"

FEATURES_NUM = ["Planned Budget", "Planned Duration Days", "Num Workers",
                 "Overtime Ratio", "Material Wastage %", "Start Month"]
FEATURES_CAT = ["Location"]
FEATURES = FEATURES_NUM + FEATURES_CAT

# --------------------------------------------------------------------------
# 1. Load historical (training) data
# --------------------------------------------------------------------------
hist = pd.read_csv(HERE / "historical_projects.csv")


def make_pipeline():
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CAT),
    ], remainder="passthrough")
    clf = RandomForestClassifier(
        n_estimators=300, max_depth=6, min_samples_leaf=4,
        random_state=42, class_weight="balanced",
    )
    return Pipeline([("prep", pre), ("clf", clf)])


def train_and_report(df, target, label):
    X = df[FEATURES]
    y = df[target]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    pipe = make_pipeline()
    pipe.fit(X_train, y_train)
    proba_test = pipe.predict_proba(X_test)[:, 1]
    pred_test = (proba_test >= 0.5).astype(int)
    auc = roc_auc_score(y_test, proba_test)
    acc = accuracy_score(y_test, pred_test)
    print(f"[{label}]  AUC: {auc:.3f}   Accuracy: {acc:.3f}   "
          f"(base rate: {y.mean():.1%}, n={len(df)})")
    # refit on ALL historical data before predicting on the live projects
    pipe.fit(X, y)
    return pipe


overrun_model = train_and_report(hist, "Cost Overrun", "Cost Overrun")
delay_model = train_and_report(hist, "Delayed", "Delayed")

# --------------------------------------------------------------------------
# 2. Build the same features for the 12 REAL live projects
# --------------------------------------------------------------------------
projects = pd.read_csv(RAW / "Projects.csv")
workers = pd.read_csv(RAW / "Workers.csv")
materials = pd.read_csv(RAW / "Materials.csv")

# same light cleanup the Power Query steps applied, done here in pandas
projects["Project Name"] = projects["Project Name"].str.strip().str.title()
projects = projects.drop_duplicates(subset="Project ID")
projects["Start Date"] = pd.to_datetime(projects["Start Date"], errors="coerce")
projects["Planned End Date"] = pd.to_datetime(projects["Planned End Date"], errors="coerce")

workers["Work Hours"] = pd.to_numeric(workers["Work Hours"], errors="coerce").fillna(0)
workers["Overtime Hours"] = pd.to_numeric(workers["Overtime Hours"], errors="coerce").fillna(0)
workers = workers.drop_duplicates()

materials["Quantity Used"] = materials["Quantity Used"].abs()
materials = materials.drop_duplicates()
materials["Wastage %"] = np.where(
    materials["Quantity Planned"] > 0,
    (materials["Quantity Used"] - materials["Quantity Planned"])
    / materials["Quantity Planned"] * 100,
    np.nan,
)

worker_agg = workers.groupby("Project ID").agg(
    **{"Num Workers": ("Worker ID", "nunique"),
       "_work_hours": ("Work Hours", "sum"),
       "_ot_hours": ("Overtime Hours", "sum")}
).reset_index()
worker_agg["Overtime Ratio"] = np.where(
    worker_agg["_work_hours"] > 0,
    worker_agg["_ot_hours"] / worker_agg["_work_hours"], 0,
)

material_agg = materials.groupby("Project ID").agg(
    **{"Material Wastage %": ("Wastage %", "mean")}
).reset_index()

live = projects.merge(worker_agg, on="Project ID", how="left") \
               .merge(material_agg, on="Project ID", how="left")

live["Planned Duration Days"] = (live["Planned End Date"] - live["Start Date"]).dt.days
live["Start Month"] = live["Start Date"].dt.month
live = live.rename(columns={"Planned Budget": "Planned Budget"})  # already matches

for col in ["Num Workers", "Overtime Ratio", "Material Wastage %"]:
    live[col] = live[col].fillna(live[col].median())

# --------------------------------------------------------------------------
# 3. Predict
# --------------------------------------------------------------------------
X_live = live[FEATURES]
live["Predicted Cost Overrun Prob"] = overrun_model.predict_proba(X_live)[:, 1]
live["Predicted Delay Prob"] = delay_model.predict_proba(X_live)[:, 1]


def risk_band(p):
    if p >= 0.6:
        return "🔴 High"
    if p >= 0.35:
        return "🟠 Medium"
    return "🟢 Low"


live["Predicted Cost Risk"] = live["Predicted Cost Overrun Prob"].apply(risk_band)
live["Predicted Delay Risk"] = live["Predicted Delay Prob"].apply(risk_band)

out_cols = [
    "Project ID", "Project Name", "Location", "Project Status",
    "Planned Budget", "Planned Duration Days", "Num Workers",
    "Overtime Ratio", "Material Wastage %",
    "Predicted Cost Overrun Prob", "Predicted Cost Risk",
    "Predicted Delay Prob", "Predicted Delay Risk",
]
result = live[out_cols].sort_values("Predicted Cost Overrun Prob", ascending=False)
result.to_csv(HERE / "risk_predictions.csv", index=False)

pd.set_option("display.width", 140)
print("\nPredictions for live projects (sorted by cost overrun risk):\n")
print(result[["Project Name", "Predicted Cost Overrun Prob", "Predicted Cost Risk",
              "Predicted Delay Prob", "Predicted Delay Risk"]]
      .to_string(index=False, formatters={
          "Predicted Cost Overrun Prob": "{:.1%}".format,
          "Predicted Delay Prob": "{:.1%}".format,
      }))
print(f"\nSaved: {HERE / 'risk_predictions.csv'}")
