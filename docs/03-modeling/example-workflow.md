# Example Modeling Workflow

A complete end-to-end example showing how to build the five-layer architecture.

## Step 1: Build expected rebate table

Pseudo-SQL:

```sql
CREATE TABLE expected_rebate AS
SELECT
    c.claim_id,
    c.ndc11,
    d.brand_name,
    d.manufacturer,
    c.group_id,
    c.fill_date,
    DATE_TRUNC('quarter', c.fill_date) AS fill_quarter,
    c.quantity,
    c.days_supply,
    c.gross_cost,
    c.plan_paid,
    f.formulary_id,
    f.tier,
    f.preferred_flag,
    k.contract_id,
    k.rebate_basis,
    k.rebate_rate,
    CASE
        WHEN k.rebate_basis = 'PER_30_DAY_SCRIPT'
            THEN (c.days_supply / 30.0) * k.rebate_rate
        WHEN k.rebate_basis = 'PER_UNIT'
            THEN c.quantity * k.rebate_rate
        WHEN k.rebate_basis = 'PERCENT_WAC'
            THEN c.estimated_wac_sales * k.rebate_rate
        ELSE NULL
    END AS expected_rebate
FROM pharmacy_claims c
JOIN drug_master d
  ON c.ndc11 = d.ndc11
 AND c.fill_date BETWEEN d.eff_date AND d.end_date
LEFT JOIN formulary_history f
  ON c.ndc11 = f.ndc11
 AND c.group_id = f.group_id
 AND c.fill_date BETWEEN f.eff_date AND f.end_date
LEFT JOIN rebate_contract_terms k
  ON d.brand_family_id = k.brand_family_id
 AND c.group_id = k.group_id
 AND c.fill_date BETWEEN k.eff_date AND k.end_date
WHERE c.claim_status = 'PAID';
```

## Step 2: Aggregate to modeling grain

```python
import pandas as pd
import numpy as np

df = claims_with_rebates.copy()

df["script_30_equiv"] = df["days_supply"] / 30.0

agg = (
    df.groupby(["ndc11", "brand_name", "manufacturer", "group_id", "fill_quarter", "channel"])
    .agg(
        claim_count=("claim_id", "nunique"),
        script_30_equiv=("script_30_equiv", "sum"),
        gross_cost=("gross_cost", "sum"),
        plan_paid=("plan_paid", "sum"),
        expected_rebate=("expected_rebate", "sum"),
        actual_rebate=("actual_rebate", "sum"),
        member_count=("member_id", "nunique"),
        reversal_rate=("reversal_flag", "mean"),
        preferred_rate=("preferred_flag", "mean"),
        specialty_rate=("specialty_flag", "mean"),
        missing_contract_rate=("contract_id", lambda x: x.isna().mean()),
        missing_invoice_rate=("invoice_id", lambda x: x.isna().mean()),
    )
    .reset_index()
)

agg["rebate_gap"] = agg["expected_rebate"] - agg["actual_rebate"].fillna(0)
agg["rebate_realization"] = agg["actual_rebate"] / agg["expected_rebate"].replace(0, np.nan)
agg["rebate_per_30"] = agg["actual_rebate"] / agg["script_30_equiv"].replace(0, np.nan)
agg["expected_rebate_per_30"] = agg["expected_rebate"] / agg["script_30_equiv"].replace(0, np.nan)
agg["gross_cost_per_30"] = agg["gross_cost"] / agg["script_30_equiv"].replace(0, np.nan)
```

## Step 3: Add historical comparison features

```python
agg = agg.sort_values(["ndc11", "group_id", "channel", "fill_quarter"])

group_cols = ["ndc11", "group_id", "channel"]

agg["rebate_realization_lag1"] = (
    agg.groupby(group_cols)["rebate_realization"].shift(1)
)

agg["rebate_realization_roll4_median"] = (
    agg.groupby(group_cols)["rebate_realization"]
       .shift(1)
       .rolling(4, min_periods=2)
       .median()
       .reset_index(level=group_cols, drop=True)
)

agg["rebate_realization_delta"] = (
    agg["rebate_realization"] - agg["rebate_realization_roll4_median"]
)

agg["claim_count_lag1"] = agg.groupby(group_cols)["claim_count"].shift(1)
agg["claim_count_qoq_change"] = (
    agg["claim_count"] / agg["claim_count_lag1"].replace(0, np.nan) - 1
)
```

## Step 4: Train Isolation Forest

```python
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

model_df = agg.copy()

numeric_features = [
    "claim_count",
    "script_30_equiv",
    "gross_cost",
    "plan_paid",
    "expected_rebate",
    "actual_rebate",
    "rebate_gap",
    "rebate_realization",
    "rebate_per_30",
    "expected_rebate_per_30",
    "gross_cost_per_30",
    "reversal_rate",
    "preferred_rate",
    "specialty_rate",
    "missing_contract_rate",
    "missing_invoice_rate",
    "rebate_realization_delta",
    "claim_count_qoq_change",
]

categorical_features = [
    "manufacturer",
    "channel",
]

# Log-transform skewed features
for col in ["claim_count", "script_30_equiv", "gross_cost", "plan_paid", "expected_rebate", "actual_rebate", "rebate_gap"]:
    model_df[f"log1p_{col}"] = np.log1p(model_df[col].clip(lower=0))

numeric_features = [
    f"log1p_{col}" if col in ["claim_count", "script_30_equiv", "gross_cost", "plan_paid", "expected_rebate", "actual_rebate", "rebate_gap"]
    else col
    for col in numeric_features
]

preprocess = ColumnTransformer(
    transformers=[
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler())
        ]), numeric_features),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20))
        ]), categorical_features),
    ]
)

iso = IsolationForest(
    n_estimators=500,
    contamination=0.02,
    max_samples="auto",
    random_state=42,
    n_jobs=-1
)

pipe = Pipeline([
    ("preprocess", preprocess),
    ("model", iso)
])

train_mask = model_df["fill_quarter"] < "2025-01-01"
score_mask = model_df["fill_quarter"] >= "2025-01-01"

pipe.fit(model_df.loc[train_mask, numeric_features + categorical_features])

# Lower decision_function scores are more anomalous.
model_df.loc[score_mask, "anomaly_score_raw"] = pipe.decision_function(
    model_df.loc[score_mask, numeric_features + categorical_features]
)

model_df.loc[score_mask, "is_anomaly"] = pipe.predict(
    model_df.loc[score_mask, numeric_features + categorical_features]
) == -1

# Business priority score
model_df["estimated_recoverable_gap"] = model_df["rebate_gap"].clip(lower=0)

model_df["priority_score"] = (
    model_df["is_anomaly"].astype(int)
    * model_df["estimated_recoverable_gap"]
    * model_df["expected_rebate"].notna().astype(int)
)

top_cases = (
    model_df[model_df["is_anomaly"]]
    .sort_values(["priority_score", "estimated_recoverable_gap"], ascending=False)
    .head(100)
)
```

## Step 5: Add rule-based flags

```python
model_df["flag_missing_rebate"] = (
    (model_df["expected_rebate"] > 1000)
    & (model_df["actual_rebate"].fillna(0) == 0)
)

model_df["flag_low_realization"] = (
    (model_df["expected_rebate"] > 10000)
    & (model_df["rebate_realization"] < 0.75)
)

model_df["flag_missing_contract"] = (
    (model_df["gross_cost"] > 10000)
    & (model_df["missing_contract_rate"] > 0.2)
)

model_df["flag_material_gap"] = model_df["rebate_gap"] > 25000

model_df["rule_flag_count"] = model_df[
    [
        "flag_missing_rebate",
        "flag_low_realization",
        "flag_missing_contract",
        "flag_material_gap",
    ]
].sum(axis=1)
```

## Step 6: Create final audit queue

```python
model_df["final_priority_score"] = (
    3.0 * model_df["flag_missing_rebate"].astype(int)
    + 2.0 * model_df["flag_low_realization"].astype(int)
    + 1.5 * model_df["flag_missing_contract"].astype(int)
    + 1.0 * model_df["is_anomaly"].astype(int)
) * np.log1p(model_df["estimated_recoverable_gap"])

audit_queue = (
    model_df[
        (model_df["estimated_recoverable_gap"] > 5000)
        & (
            model_df["is_anomaly"]
            | (model_df["rule_flag_count"] > 0)
        )
    ]
    .sort_values("final_priority_score", ascending=False)
)

# Export for analyst review
audit_queue[[
    "ndc11",
    "brand_name",
    "manufacturer",
    "group_id",
    "fill_quarter",
    "channel",
    "claim_count",
    "expected_rebate",
    "actual_rebate",
    "rebate_gap",
    "rebate_realization",
    "rule_flag_count",
    "final_priority_score",
]].to_csv("audit_queue.csv", index=False)

print(f"Audit queue: {len(audit_queue)} cases")
print(f"Estimated total leakage: ${audit_queue['estimated_recoverable_gap'].sum():,.0f}")
print(f"Average case size: ${audit_queue['estimated_recoverable_gap'].mean():,.0f}")
```

## Result

This workflow produces:

1. Expected rebate reconciliation (Layer 1)
2. Rule-based flags (Layer 2)
3. Statistical features (Layer 3 - rolling medians, QoQ changes)
4. ML anomaly scores (Layer 4 - Isolation Forest)
5. Final prioritized queue (Layer 5)

The top 100 cases in `audit_queue.csv` represent the highest-value leakage opportunities for immediate analyst review.

## Next steps

1. Have analysts review top 50–100 cases
2. Capture review outcomes (valid/invalid/research needed)
3. Log recovered dollars by case
4. Retrain supervised model on labeled outcomes
5. Iterate quarterly as new quarters of data arrive
