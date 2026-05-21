# Analytic Grains

Do not use only one modeling grain. Use several. Different grains reveal different anomaly types.

## Claim level

**Best for:**

* Eligibility errors
* Missing NDC/contract/formulary mapping
* Incorrect exclusions
* Claim-level underpayment

**Problem:** Very noisy and high-volume.

**When to use:** For control testing and validation. Too granular for production anomaly detection at scale.

## NDC × client × quarter

**Best for:**

* Product-level rebate leakage
* Missing NDC launches
* Sudden yield drops
* Unit problems

This is often the best starting grain.

**Advantages:**

* Natural business unit (how contracts and invoices are organized)
* Balanced granularity (not too sparse, not too coarse)
* Captures product-specific anomalies
* Interpretable to rebate analysts

**Recommended for:** Primary anomaly detection model

## Brand × client × quarter

**Best for:**

* Brand-family contract issues
* NDC roll-up errors
* New package/NDC not mapped

**When to use:** As a secondary model to catch brand-family-level leakage that product-level models miss.

## Manufacturer × client × quarter

**Best for:**

* Invoice/payment shortfalls
* Dispute/write-off anomalies
* Guarantee issues

**When to use:** For contract-level audit and financial reconciliation.

## Contract × quarter

**Best for:**

* PBM guarantee audits
* Annual true-ups
* Aggregate leakage

**When to use:** Quarterly or annual review by contract management.

## Therapeutic class × formulary tier × quarter

**Best for:**

* Market-basket and formulary-position anomalies

**When to use:** When assessing portfolio-level rebate performance.

## How to implement multi-grain modeling

```python
# Grain 1: NDC × client × quarter
ndc_grain = (
    claims_df.groupby(["ndc11", "client_id", "quarter"])
    .agg({
        "claim_count": "nunique",
        "gross_cost": "sum",
        "expected_rebate": "sum",
        "actual_rebate": "sum",
    })
    .reset_index()
)

# Grain 2: Brand × client × quarter
brand_grain = (
    claims_df.merge(drug_master[["ndc11", "brand_family"]], on="ndc11")
    .groupby(["brand_family", "client_id", "quarter"])
    .agg({
        "claim_count": "nunique",
        "gross_cost": "sum",
        "expected_rebate": "sum",
        "actual_rebate": "sum",
    })
    .reset_index()
)

# Grain 3: Manufacturer × client × quarter
mfr_grain = (
    claims_df.merge(drug_master[["ndc11", "manufacturer"]], on="ndc11")
    .groupby(["manufacturer", "client_id", "quarter"])
    .agg({
        "invoiced_rebate": "sum",
        "paid_rebate": "sum",
        "disputed_rebate": "sum",
    })
    .reset_index()
)

# Score each grain independently
for grain_df, grain_name in [(ndc_grain, "NDC"), (brand_grain, "Brand"), (mfr_grain, "Manufacturer")]:
    anomaly_scores = score_anomalies(grain_df)
    results[grain_name] = anomaly_scores
```

## Multi-grain reconciliation

Anomalies detected at one grain should often reconcile across grains:

* If NDC × client × quarter flagged an anomaly, check if Brand × client × quarter also flags the brand
* If Manufacturer × client × quarter shows a gap, the underlying NDCs should show it too
* Disagreement across grains signals either:
  - False positive at one grain
  - Complex multi-NDC issue
  - Data quality problem

```python
# Example: Cross-check NDC and Brand grains
ndc_flagged = ndc_grain[ndc_grain["is_anomaly"]].copy()
brand_grain_merged = ndc_flagged.merge(
    drug_master[["ndc11", "brand_family"]], 
    on="ndc11"
)

brand_anomalies = brand_grain[brand_grain["is_anomaly"]]["brand_family"].unique()
brand_should_flag = set(brand_grain_merged["brand_family"].unique())

# Brands that have NDC anomalies but brand-level grain didn't flag
missed_brands = brand_should_flag - brand_anomalies
if len(missed_brands) > 0:
    print(f"Warning: {len(missed_brands)} brands with NDC anomalies not caught at brand grain")
```

## Grain selection criteria

Choose grains based on:

1. **Business relevance**: How does your organization talk about rebates? (Likely answer: NDC-client-quarter)
2. **Data completeness**: Is there enough volume at that grain to avoid spurious patterns?
3. **Stakeholder interest**: What granularity matters to your finance/compliance teams?
4. **Anomaly type**: Different grain types surface different patterns

Recommended starting set:

1. **NDC × client × quarter** (primary anomaly detection)
2. **Brand × client × quarter** (secondary verification)
3. **Manufacturer × client × quarter** (invoice/payment audit)
