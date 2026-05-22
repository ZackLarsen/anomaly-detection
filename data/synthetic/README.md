# Synthetic Rx Rebate Dataset

This directory contains synthetic pharmacy claims data with injected anomalies for testing and evaluating anomaly detection models.

---

## Quick Load

```python
import polars as pl

invoices = pl.read_parquet("data/synthetic/invoices_with_anomalies.parquet")
drugs = pl.read_parquet("data/synthetic/drugs.parquet")
claims = pl.read_parquet("data/synthetic/claims.parquet")
formulary = pl.read_parquet("data/synthetic/formulary.parquet")
contracts = pl.read_parquet("data/synthetic/contracts.parquet")
labels = pl.read_parquet("data/synthetic/anomaly_labels.parquet")

print(f"Invoices: {len(invoices):,} rows")
print(f"Labels: {len(labels):,} anomalies")
```

---

## Dataset Contents

### Core Tables

| File | Rows | Size | Description |
|------|------|------|-------------|
| `claims.parquet` | 500,000 | 9.8 MB | Individual pharmacy claims with NDC, date, quantity, cost, channel |
| `drugs.parquet` | 300 | 5.5 KB | Drug master: NDC → brand family, manufacturer, specialty flag, GPI class |
| `formulary.parquet` | 10,500 | 24 KB | Formulary status: NDC × client → tier, preferred, PA/ST/QL flags |
| `contracts.parquet` | 10,870 | 20 KB | Rebate contracts: manufacturer × brand × client → basis type, rate, guarantee |
| `invoices.parquet` | 118,122 | 1.3 MB | Quarterly rebate invoices: NDC × client × quarter → expected, actual, disputed, paid |

### Labels & Variants

| File | Description |
|------|-------------|
| `invoices_with_anomalies.parquet` | Invoices with 7 injected anomalies (use this for model training) |
| `anomaly_labels.parquet` | Ground-truth labels: anomaly_type, entity, recoverable flag, estimated impact |

---

## Anomaly Labels

The dataset contains 7 injected anomalies with ground-truth labels:

| Anomaly Type | Count | Estimated Impact | Recovery Potential |
|--------------|-------|-------------------|-------------------|
| MISSING_REBATE | 5 | $XXX | High (refund if noticed) |
| UNMAPPED_NDC | 3 | $XXX | High (new product) |
| REBATE_YIELD_COLLAPSE | 3 | $XXX | High (rate adjustment) |
| CHANNEL_OMISSION | 4 | $XXX | Medium (channel analysis) |
| UNIT_CONVERSION_ERROR | 2 | $XXX | High (unit fix) |
| DISPUTE_SPIKE | 3 | $XXX | Medium (dispute resolution) |
| GUARANTEE_TRUE_UP_MISSING | 2 | $XXX | High (guarantee payment) |
| **Total** | **22** | **$XXX** | — |

---

## How to Generate (if needed)

### Option 1: Use Existing Data

The data is already generated. Load directly in Python or Jupyter:

```python
import polars as pl
df = pl.read_parquet("data/synthetic/invoices_with_anomalies.parquet")
```

### Option 2: Regenerate with Same Seed

To regenerate identical data (same seed = 42):

```bash
python main.py
```

Output: Overwrites all files in `data/synthetic/` (~4 seconds)

### Option 3: Regenerate with Custom Seed

To generate different data (randomized selection of anomalies):

```bash
python -m synthetic_data_gen generate --seed 999
```

### Option 4: Generate Baseline Without Anomalies

To generate clean data without injected anomalies:

```bash
python -m synthetic_data_gen generate --no-anomalies
```

### Option 5: Custom Configuration

To generate with custom parameters (different claim counts, NDCs, groups):

Edit `configs/base.yaml`:
```yaml
n_claims: 1000000         # 1M claims instead of 500K
n_ndcs: 500               # 500 drugs instead of 300
n_groups: 100             # 100 groups instead of 50
```

Then regenerate:
```bash
python main.py
```

---

## Data Dictionary

### claims.parquet

| Column | Type | Description |
|--------|------|-------------|
| claim_id | String | Unique claim ID (C000000001, C000000002, ...) |
| member_id | String | Synthetic member ID |
| group_id | String | Client/group ID (G000–G049) |
| ndc11 | String | 11-digit NDC code |
| fill_date | Date | Claim fill date (2024-01-01 to 2025-12-31) |
| days_supply | Int | Days of supply (30, 60, 84, 90) |
| quantity | Float | Quantity dispensed |
| channel | String | Pharmacy channel (retail, mail, specialty) |
| plan_paid | Float | Amount paid by plan |
| gross_drug_cost | Float | Gross cost of drug (plan_paid + patient portion) |
| claim_status | String | Claim status (approved, adjusted, pending, reversed) |

### drugs.parquet

| Column | Type | Description |
|--------|------|-------------|
| ndc11 | String | 11-digit NDC code |
| brand_family | String | Brand family name (Brand_0, Brand_1, ...) |
| manufacturer | String | Manufacturer name (M00–M19) |
| gpi_class | String | GPI therapeutic class code |
| specialty_flag | Bool | Is this a specialty drug? |
| package_size | Int | Typical package size (30, 60, 90 tablets; 1, 10, 100 injectables) |
| effective_date_start | Date | When this NDC became active |
| effective_date_end | Date | When this NDC became inactive (2026-12-31 for all in dataset) |
| launch_date | Date | Original launch date |

### formulary.parquet

| Column | Type | Description |
|--------|------|-------------|
| client_id | String | Client/group ID (G000–G049) |
| ndc11 | String | NDC code |
| brand_family | String | Brand family name |
| tier | Int | Formulary tier (1–6, lower is preferred) |
| preferred_flag | Bool | Is this a preferred product? (true if tier ≤ 2) |
| pa_required | Bool | Prior authorization required? |
| st_required | Bool | Step therapy required? |
| ql_required | Bool | Quantity limit? |
| effective_date_start | Date | Effective date (2024-01-01) |
| effective_date_end | Date | End date (2025-12-31) |

### contracts.parquet

| Column | Type | Description |
|--------|------|-------------|
| manufacturer | String | Manufacturer name (M00–M19) |
| brand_family | String | Brand family name |
| client_id | String | Client/group ID |
| effective_date_start | Date | Contract start date (2024-01-01) |
| effective_date_end | Date | Contract end date (2025-12-31) |
| rebate_basis | String | Calculation basis: PER_30_DAY_SCRIPT, PERCENT_GROSS_COST, PER_UNIT, PMPM_GUARANTEE |
| rebate_rate | Float | Rebate amount/percentage (depends on basis) |
| minimum_guarantee | Float | Minimum payment (for PMPM_GUARANTEE contracts) |
| channel_exclusions | List[String] | Excluded channels (retail, mail, specialty) |
| lob_exclusions | List[String] | Excluded lines of business (Medicaid, Medicare, etc.) |

### invoices.parquet

| Column | Type | Description |
|--------|------|-------------|
| invoice_quarter | String | Quarterly period (2024-Q1, 2024-Q2, ..., 2025-Q4) |
| manufacturer | String | Manufacturer name |
| ndc11 | String | NDC code |
| client_id | String | Client/group ID |
| invoiced_utilization | Float | Total quantity billed in quarter |
| expected_rebate | Float | Calculated rebate per contract terms |
| actual_rebate | Float | Actual rebate received (expected ± 5% noise) |
| disputed_rebate | Float | Amount in dispute (0 for baseline) |
| paid_rebate | Float | Actual payment received (actual_rebate - disputed_rebate) |
| channel | String | Pharmacy channel (default: "all" for aggregated; splits on anomaly injection) |

### anomaly_labels.parquet

| Column | Type | Description |
|--------|------|-------------|
| entity_type | String | Granularity level (ndc_group_quarter, manufacturer_brand_quarter, etc.) |
| ndc11 | String | NDC code (if applicable) |
| client_id | String | Client/group ID (if applicable) |
| manufacturer | String | Manufacturer name (if applicable) |
| brand_family | String | Brand family name (if applicable) |
| quarter | String | Quarterly period (if applicable) |
| channel | String | Pharmacy channel (if applicable) |
| anomaly_type | String | Type of anomaly injected |
| recoverable | Bool | Is this anomaly recoverable? (true for most) |
| estimated_impact | Float | Estimated rebate gap / recovery potential |
| root_cause | String | Human-readable explanation |

---

## Using in Notebooks

### Notebook 1: Data Exploration

```bash
jupyter notebook
# Open: notebooks/01_generate_demo_data.ipynb
```

This notebook:
- Loads all 6 tables
- Shows distributions (channel, days supply, cost, tier, rebate basis)
- Creates 7 interactive visualizations
- Runs referential integrity checks
- Identifies the 7 injected anomalies

### Notebook 2: Model Training

```bash
jupyter notebook
# Open: notebooks/02_train_anomaly_models.ipynb
```

This notebook:
- Engineers features (rebate_realization, rebate_gap, etc.)
- Creates time-series features (QoQ change, rolling average)
- Trains Isolation Forest
- Adds rule-based anomaly flags
- Evaluates precision@K and dollars@K
- Generates audit queue with top-50 anomalies

---

## Data Characteristics

### Claims
- **Period:** 2024-01-01 to 2025-12-31 (24 months, ~21K claims/month)
- **Channel distribution:** Retail 70%, Mail 20%, Specialty 10%
- **Days supply:** 30-day dominant (65%), 90-day in mail (20%)
- **Cost distribution:** Specialty drugs 8x retail cost

### Invoices
- **Grain:** NDC × client × quarter
- **Rows:** 118,122 (8 quarters × ~14,765 combinations)
- **Rebate basis types:** 25% PER_30_DAY, 25% PERCENT_GROSS, 25% PER_UNIT, 25% PMPM
- **Normal variance:** ±5% noise (0.95–1.05x expected)

### Anomalies
- **7 types injected** with ground-truth labels
- **Total estimated impact:** ~$XXX
- **Detectability:** All 7 should be findable in top-100 audit queue with proper feature engineering

---

## Quality Checks

Run validation to verify data consistency:

```python
from synthetic_data_gen.validate import run_all_validations

results = run_all_validations(claims, drugs, formulary, contracts, invoices, labels)

for check_name, (passed, messages) in results.items():
    status = "✓" if passed else "✗"
    print(f"{status} {check_name}")
    if not passed:
        for msg in messages:
            print(f"  - {msg}")
```

All checks should pass on the provided data.

---

## Tips

1. **Start small:** Load just `invoices_with_anomalies.parquet` to begin
2. **Use polars:** All data is polars-native; `.read_parquet()` is fast
3. **Filter by quarter:** Group data by `invoice_quarter` to analyze trends
4. **Map to drugs:** Join `invoices` + `drugs` to get brand/manufacturer names
5. **Check labels:** Always filter `anomaly_labels` by `anomaly_type` to find specific issues

---

## Regeneration Steps

If you need to regenerate from scratch:

```bash
# 1. Ensure Python 3.12+ and dependencies
uv sync

# 2. Regenerate
python main.py

# 3. Verify
pytest tests/ -v

# 4. Explore
jupyter notebook
```

See [../../CLAUDE.md](../../CLAUDE.md) for full development guide.
