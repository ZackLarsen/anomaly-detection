# Feature Engineering

Feature engineering is where most of the value comes from in rebate anomaly detection. This document catalogs the most useful features across different analytical grains.

## 1. Claim-level features

### Utilization features

* Claim count by NDC/brand/group/quarter
* Unique members
* Unique prescribers
* Unique pharmacies
* Total quantity
* Total days supply
* Scripts normalized to 30-day equivalents
* Scripts normalized to 84/90-day equivalents
* New starts versus refills
* Reversal rate
* Adjustment rate
* Late claim rate
* COB rate
* DAW rate
* Specialty channel share
* Mail share
* Retail share

Example:

```python
script_30_equiv = days_supply / 30
rebate_per_30_day_script = rebate_amount / script_30_equiv
```

### Financial features

* Plan paid per script
* Gross cost per script
* Ingredient cost per unit
* WAC per unit
* AWP discount
* Patient pay share
* Rebate per script
* Rebate per 30-day equivalent
* Rebate as percent of gross cost
* Rebate as percent of WAC
* Net cost = gross cost - rebate
* Net cost PMPM
* Spread between expected and actual rebate

### Drug identity features

* NDC11
* NDC9
* Labeler
* Manufacturer
* Brand family
* GPI2/GPI4/GPI6/GPI10/GPI14
* Therapeutic class
* Brand/generic
* Specialty flag
* Biosimilar flag
* Launch age in months
* Discontinued flag
* Package-size bucket
* Unit-of-measure type

### Benefit/formulary features

* Tier
* Preferred status
* Non-preferred status
* Excluded flag
* PA/ST/QL flags
* Formulary effective-date distance
* Tier change in prior quarter
* Custom client override flag
* Number of formulary changes in last 12 months

### Eligibility features

* Commercial/Medicare/Medicaid/Exchange
* Self-funded/fully insured
* Client size
* Member months
* Geography
* PBM contract version
* Carve-in/carve-out flag

### Temporal features

* Quarter
* Month
* Days since contract start
* Days until contract end
* Quarter-over-quarter utilization change
* Year-over-year utilization change
* Rolling 3-quarter average rebate yield
* Rolling z-score
* Seasonality-adjusted residual
* Late adjustment lag

## 2. Rebate-specific engineered features

These are especially important for this use case.

### Expected rebate features

Create an expected rebate engine using contract rules:

```python
expected_rebate = eligible_units × contract_rate
```

or:

```python
expected_rebate = eligible_30_day_scripts × guaranteed_rebate_per_30_day_script
```

or:

```python
expected_rebate = WAC_sales × rebate_percentage
```

Then engineer:

* Expected rebate per script
* Expected rebate per unit
* Expected rebate per 30-day equivalent
* Expected rebate PMPM
* Contract minimum amount
* Actual minus expected
* Actual divided by expected
* Expected eligibility flag
* Contract rule matched flag
* Number of matched contract rules
* Ambiguous contract rule flag
* Missing contract rule flag

### Rebate yield features

At different grains:

* NDC-quarter rebate yield
* Brand-quarter rebate yield
* Manufacturer-quarter rebate yield
* Client-quarter rebate yield
* Formulary-tier-quarter rebate yield
* Therapeutic-class rebate yield

Useful ratios:

```python
rebate_yield_gross = actual_rebate / gross_drug_cost
rebate_yield_wac = actual_rebate / estimated_wac_sales
rebate_per_script = actual_rebate / claim_count
rebate_per_30 = actual_rebate / sum(days_supply / 30)
rebate_realization = actual_rebate / expected_rebate
```

### Contract compliance features

* Product was preferred but paid as non-preferred
* Product was non-preferred but received preferred-level rebate
* Product missing from invoice after becoming preferred
* Product excluded despite contract eligibility
* Product included despite exclusion
* Guarantee true-up missing
* Market-share tier changed but rebate rate did not

### Comparison features

Compare each observation to relevant peers:

* Same brand, prior quarters
* Same NDC, other clients
* Same manufacturer, same quarter
* Same therapeutic class
* Same formulary tier
* Same channel
* Same PBM contract
* Same plan type

Examples:

```python
brand_rebate_yield_vs_rolling_median
client_rebate_pmpm_vs_peer_median
ndc_rebate_per_unit_vs_brand_median
actual_expected_ratio_vs_same_contract_products
```

## 3. Data quality features

Many rebate anomalies are really data-quality anomalies. Create explicit flags for:

* Invalid NDC
* NDC not found in drug master
* NDC inactive on fill date
* Missing manufacturer
* Missing brand family
* Missing formulary ID
* Missing contract ID
* Missing invoice line
* Unit mismatch
* Quantity outlier
* Days supply outlier
* Reversal without original
* Original without reversal
* Claim paid after invoice cutoff
* Invoice quarter mismatch
* Product mapped to multiple manufacturers
* Product mapped to multiple contracts

**Do not hide these inside ML.** Surface them directly.

## Feature scaling for ML

### Log transforms

Apply log1p to heavily skewed metrics:

```python
for col in ["claim_count", "script_30_equiv", "gross_cost", "expected_rebate", "actual_rebate"]:
    model_df[f"log1p_{col}"] = np.log1p(model_df[col].clip(lower=0))
```

### Robust scaling

For distance-based models, use robust scaling to handle outliers:

```python
from sklearn.preprocessing import RobustScaler

scaler = RobustScaler()
for col in numeric_features:
    model_df[f"{col}_scaled"] = scaler.fit_transform(model_df[[col]])
```

### Categorical encoding

* **Low-cardinality** (< 50 categories): One-hot encode
* **High-cardinality** (> 50 categories): Target encode or frequency encode

```python
# One-hot for low-cardinality
categorical_low = ["channel", "tier", "line_of_business"]
model_df = pd.get_dummies(model_df, columns=categorical_low)

# Target encode for high-cardinality
from sklearn.preprocessing import OrdinalEncoder
encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
model_df[["ndc_encoded", "client_encoded"]] = encoder.fit_transform(model_df[["ndc11", "client_id"]])
```

## Feature selection

Not all engineered features are useful. Use these methods to select:

1. **Variance threshold**: Remove features with very low variance
2. **Correlation analysis**: Remove highly correlated feature pairs
3. **Feature importance**: For tree-based models, rank by importance
4. **Domain knowledge**: Keep features that have business meaning

```python
from sklearn.feature_selection import VarianceThreshold

selector = VarianceThreshold(threshold=0.01)
X_selected = selector.fit_transform(X)
```

## Summary

Create features at three levels:

1. **Utilization & financial**: Claim counts, costs, rebates
2. **Rebate-specific**: Expected vs actual, yield, realization
3. **Data quality**: Flags for missing data, mismatches, outliers

Combine these with comparison features (historical, peer-based) and temporal features (seasonal, trends). Don't engineer in a vacuum—validate that features have business meaning and help the model.
