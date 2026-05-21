# Training Strategy

## 1. Build a gold-standard analytic table

Start with a well-structured table at the right grain.

**Recommended row grain:**

```text
NDC × client/group × formulary × contract × quarter × channel
```

**Candidate columns:**

```text
claim_count
script_30_equiv
member_count
member_months
gross_cost
plan_paid
wac_sales
expected_rebate
actual_rebate
paid_rebate
disputed_rebate
writeoff_rebate
rebate_realization
rebate_per_30
formulary_tier
preferred_flag
specialty_flag
channel_mix
reversal_rate
qoq_util_change
qoq_rebate_yield_change
missing_contract_flag
missing_invoice_flag
invalid_ndc_flag
```

**Implementation:**

```python
agg = (
    claims_df.groupby(["ndc11", "client_id", "quarter", "channel"])
    .agg(
        claim_count=("claim_id", "nunique"),
        member_count=("member_id", "nunique"),
        gross_cost=("gross_cost", "sum"),
        plan_paid=("plan_paid", "sum"),
        expected_rebate=("expected_rebate", "sum"),
        actual_rebate=("actual_rebate", "sum"),
        missing_contract_rate=("contract_id", lambda x: x.isna().mean()),
    )
    .reset_index()
)
```

## 2. Train only on reasonably "normal" history

If you train on a dataset full of known leakage, the model learns leakage as normal.

**Exclude or downweight:**

* Known bad contract periods
* Major PBM transitions
* Known formulary migrations
* One-time true-up quarters
* Incomplete invoice quarters
* Quarters still in runout
* Products with unresolved disputes
* New launches with insufficient history

**Implementation:**

```python
# Define "normal" training window
train_start = "2023-01-01"
train_end = "2024-12-31"

# Exclude known bad periods
exclude_quarters = ["2024-Q3"]  # major PBM transition

train_mask = (
    (agg["quarter"] >= train_start)
    & (agg["quarter"] <= train_end)
    & (~agg["quarter"].isin(exclude_quarters))
    & (agg["claim_count"] >= 10)  # minimum volume
    & (~agg["ndc11"].isin(new_launches))  # exclude < 6 months
)

X_train = agg[train_mask]
```

## 3. Handle time carefully

Do not randomly split rows across time. Use time-based validation.

**Example:**

```python
train_mask = agg["quarter"] < "2025-01-01"  # 2023-2024
validate_mask = (agg["quarter"] >= "2025-01-01") & (agg["quarter"] < "2025-06-01")
test_mask = agg["quarter"] >= "2025-06-01"

X_train = agg[train_mask]
X_validate = agg[validate_mask]
X_test = agg[test_mask]
```

This mimics real deployment: scoring future quarters from past patterns.

## 4. Segment models

One global model may be too blunt.

**Consider separate models by:**

* Commercial vs Medicare vs Medicaid/Exchange
* Retail vs mail vs specialty
* Brand vs generic
* Specialty vs non-specialty
* Manufacturer
* Therapeutic class
* Contract type
* High-volume versus low-volume products

**At minimum, normalize features within peer groups:**

```python
for col in ["rebate_realization", "rebate_per_30"]:
    # Normalize within peer groups
    agg[f"{col}_normalized"] = (
        agg.groupby("therapeutic_class")[col]
        .transform(lambda x: (x - x.mean()) / x.std())
    )
```

## 5. Feature scaling and encoding

### Numeric features

For distance-based models:

```python
from sklearn.preprocessing import RobustScaler

numeric_features = [
    "claim_count",
    "gross_cost",
    "expected_rebate",
    "actual_rebate",
]

# Log-transform skewed features
for col in numeric_features:
    agg[f"log1p_{col}"] = np.log1p(agg[col].clip(lower=0))

# Robust scale
scaler = RobustScaler()
agg[numeric_features] = scaler.fit_transform(agg[numeric_features])
```

### Categorical features

```python
from sklearn.preprocessing import OneHotEncoder

# Low-cardinality: one-hot
low_card = ["channel", "formulary_tier"]
agg = pd.get_dummies(agg, columns=low_card)

# High-cardinality: target encode
from sklearn.preprocessing import OrdinalEncoder
high_card = ["ndc11", "manufacturer"]
encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
agg[high_card] = encoder.fit_transform(agg[high_card])
```

## 6. Avoid leakage in the ML sense

Do not include features that would not be available at scoring time.

**Example:** When scoring preliminary invoice anomalies, you may not yet know final paid rebate or final dispute disposition.

**Create separate models for:**

* Pre-invoice detection (have: claims, contracts, formularies)
* Post-invoice detection (have: claims, invoices, but not final payments)
* Post-payment recovery (have: everything)
* Annual true-up audit (have: full year of data)

## 7. Use semi-supervised learning when labels are sparse

Most organizations do not have clean labels. Use:

* Unsupervised anomaly detection for discovery
* Analyst review labels for feedback
* Confirmed recovery outcomes for supervised ranking later

**Practical workflow:**

```python
# 1. Run rules and anomaly models
anomalies = detect_anomalies(agg)

# 2. Send top 100–500 cases to rebate analysts
audit_queue = anomalies.nlargest(100, "priority_score")
audit_queue.to_csv("analyst_queue.csv")

# 3. Capture review outcomes (analyst inputs)
analyst_feedback = pd.read_csv("analyst_feedback.csv")

# 4. Label cases
labels = pd.DataFrame({
    "case_id": analyst_feedback["case_id"],
    "is_recoverable": analyst_feedback["decision"] == "VALID_LEAKAGE",
    "recovered_dollars": analyst_feedback["recovered_amount"],
})

# 5. Train supervised model to rank future cases
X_labeled = agg.merge(labels, on="case_id", how="inner")
y = X_labeled["is_recoverable"]

supervised_model = RandomForestClassifier()
supervised_model.fit(X_labeled[feature_cols], y)

# 6. Continue active learning (retrain quarterly with new labels)
```

## Summary

1. Use time-based validation, not random split
2. Train on "normal" history (exclude known anomalies)
3. Consider segment models for large populations
4. Scale numeric features robustly
5. Avoid leakage at scoring time
6. Start unsupervised; move to supervised as labels accumulate
