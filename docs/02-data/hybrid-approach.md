# Hybrid Approach: Combining Public and Synthetic Data

## Overview

The best approach combines public datasets for realism and synthetic generation for control and completeness.

```
Public drug data (FDA NDC Directory, Orange Book, RxNorm)
+ public utilization (Medicaid SDUD, Medicare Part D)
+ public formulary (CMS Part D formularies)
+ public pricing (NADAC, ASP)
        ↓
Realistic synthetic commercial claims
        ↓
Synthetic rebate contracts
        ↓
Synthetic rebate invoices/payments
        ↓
Injected rebate leakage anomalies
        ↓
Ground-truth labels
```

## Layer-by-layer breakdown

### Layer 1: Drug and formulary backbone

**Use public data:**

- FDA NDC Directory for real NDC/product/package metadata
- FDA Orange Book for brand/generic classification, approval dates
- RxNorm for normalized drug names and mappings
- CMS Part D formulary files for formulary structure (tier, PA/ST/QL)

**Advantages:**

- No need to invent NDCs
- Realistic product complexity (package sizes, dosage forms)
- Real formulary decision logic
- Maintains relationships between drugs, manufacturers, products

### Layer 2: Utilization patterns

**Use public data:**

- Medicaid State Drug Utilization Data (SDUD) for NDC-quarter volumes
- Medicare Part D Spending data for drug-level utilization
- Medicare Part D Prescriber data for prescriber concentration

**Advantages:**

- Realistic drug popularity (some drugs are rare, some are high-volume)
- Real seasonal variation (flu season, etc.)
- Real cost distributions (most drugs are cheap, some are expensive)
- State/regional variation if needed

**Synthetic layer:**

- Claim-level granularity (aggregate SDUD data into individual claims)
- Reversal/adjustment patterns
- Member IDs and group IDs
- Commercial plan structure (different from Medicare)
- Channel distribution (retail vs mail vs specialty)

### Layer 3: Formulary status

**Use public data:**

- CMS Part D formulary structures (which NDCs on each plan, what tier, what restrictions)
- Real pa/st/ql patterns

**Synthetic layer:**

- Commercial formulary equivalents (Part D structure, but for hypothetical commercial plans)
- Custom client overrides
- Timing (create historical formulary changes across quarters)

### Layer 4: Pricing and costs

**Use public data:**

- CMS NADAC for acquisition cost benchmarks
- CMS ASP for medical-benefit drug pricing
- Part D gross drug cost proxies

**Synthetic layer:**

- Commercial allowed amounts
- PBM negotiated rates
- Rebate basis and rates (these are private)
- Patient copay splits

### Layer 5: Rebate contracts (synthetic only)

This is the business-critical layer. No public data exists.

**Generate synthetically:**

- Contract manufacturers × brands × clients × effective dates
- Rebate basis (per-script, per-unit, percent of WAC, PMPM guarantee)
- Rebate rates (realistic ranges: 10–40% of WAC or $1–50 per script)
- Channel exclusions (e.g., specialty excluded)
- LOB exclusions (e.g., Medicaid excluded)
- Admin fees
- True-up rules

### Layer 6: Rebate invoices and payments (synthetic)

**Generate synthetically:**

- Invoice lines aggregated from synthetic claims
- Expected rebate calculated from contracts
- Actual rebate = expected rebate + noise (normally 95–105%)
- Disputed rebates (rare, ~1–5% of invoices)
- Paid rebates
- True-up amounts

### Layer 7: Anomalies and labels (synthetic + controlled injection)

**Inject anomalies:**

- Missing rebate (expected > 0, actual = 0)
- Rebate yield collapse (actual = 0.3× expected)
- New NDC unmapped (claims exist, but absent from invoice)
- Specialty channel omission
- Unit conversion errors
- Guarantee shortfalls
- Manufacturer dispute spikes

**Generate labels:**

- Anomaly type
- Affected entity (NDC, group, quarter, etc.)
- Expected impact (dollars)
- Recoverability (yes/no)
- Root cause

## Implementation workflow

### Step 1: Ingest public datasets

```python
# Download and load
ndc_df = pd.read_csv("fda_ndc_directory.csv")
orange_book_df = pd.read_csv("orange_book.csv")
rxnorm_df = pd.read_csv("rxnorm_prescribable.csv")
formulary_df = pd.read_csv("cms_part_d_formulary.csv")
sdud_df = pd.read_csv("medicaid_sdud.csv")
nadac_df = pd.read_csv("nadac.csv")

# Store in warehouse or feature store
warehouse.save("public_drug_master", ndc_df)
warehouse.save("public_formulary", formulary_df)
warehouse.save("public_utilization", sdud_df)
```

### Step 2: Generate synthetic claims using public data

```python
# Use SDUD to define which NDCs/drugs to generate claims for
ndcs_to_generate = sdud_df["NDC"].unique()

# For each NDC, generate claim volume matching SDUD distribution
claims = []
for ndc in ndcs_to_generate:
    sdud_volume = sdud_df[sdud_df["NDC"] == ndc]["prescriptions"].values[0]
    
    # Generate synthetic claims at 2x/5x/10x SDUD scale for commercial
    num_claims = int(sdud_volume * 5)  # commercial is bigger than Medicaid
    
    for i in range(num_claims):
        claim = {
            "claim_id": f"C{i:09d}",
            "ndc11": ndc,
            "fill_date": np.random.choice(pd.date_range("2024-01-01", "2025-12-31")),
            "days_supply": np.random.choice([30, 60, 84, 90]),
            "quantity": np.random.gamma(2.0, 15.0),
            "channel": np.random.choice(["retail", "mail", "specialty"]),
            # ... other fields
        }
        claims.append(claim)

claims_df = pd.DataFrame(claims)
```

### Step 3: Add formulary status from public data

```python
# Join claims to CMS Part D formulary
# (Simulate commercial formularies by sampling from Part D structure)

claims_df = claims_df.merge(
    formulary_df,
    on="ndc11",
    how="left"
)

# Mark any unmatched NDCs
claims_df["formulary_status"] = claims_df["tier"].fillna("UNMAPPED")
```

### Step 4: Add pricing from public benchmarks

```python
# Join to NADAC for cost estimates
claims_df = claims_df.merge(
    nadac_df[["ndc11", "nadac_per_unit"]],
    on="ndc11",
    how="left"
)

# Estimate gross cost
claims_df["gross_cost"] = claims_df["nadac_per_unit"] * claims_df["quantity"]

# Add commercial markup (real drugs are more expensive in commercial)
claims_df["plan_paid"] = claims_df["gross_cost"] * 0.9  # realistic plan allowance
```

### Step 5: Generate synthetic contracts

```python
# Create contracts independently of public data
contracts = []

for manufacturer in manufacturers_list:
    for brand_family in brand_families:
        for client in clients:
            contract = {
                "manufacturer": manufacturer,
                "brand_family": brand_family,
                "client": client,
                "effective_date": "2024-Q1",
                "end_date": "2025-Q4",
                "rebate_basis": np.random.choice(["PER_30_DAY_SCRIPT", "PERCENT_GROSS_COST"]),
                "rebate_rate": np.random.uniform(0.1, 0.4),
                # ... other fields
            }
            contracts.append(contract)

contracts_df = pd.DataFrame(contracts)
```

### Step 6: Calculate expected and actual rebates

```python
# Calculate expected rebate from contracts
claims_df = claims_df.merge(contracts_df, on=["manufacturer", "brand_family"], how="left")

claims_df["expected_rebate"] = claims_df.apply(calculate_rebate, axis=1)

# Aggregate to invoice grain
invoices = claims_df.groupby(["ndc11", "client", "quarter"]).agg({
    "expected_rebate": "sum",
    "claim_count": "count",
    # ...
}).reset_index()

# Add actual rebates (normally close to expected)
invoices["actual_rebate"] = invoices["expected_rebate"] * np.random.uniform(0.95, 1.05)
```

### Step 7: Inject anomalies

```python
# Scenario: Missing rebate
invoices.loc[
    (invoices["ndc11"] == "12345678901")
    & (invoices["quarter"] == "2025-Q1"),
    "actual_rebate"
] = 0.0

# Scenario: Rebate yield collapse
invoices.loc[
    (invoices["ndc11"] == "98765432109"),
    "actual_rebate"
] *= 0.3

# ... inject other scenarios
```

### Step 8: Create labels

```python
labels = pd.DataFrame({
    "ndc11": ["12345678901"],
    "client": ["G001"],
    "quarter": ["2025-Q1"],
    "anomaly_type": ["MISSING_REBATE"],
    "recoverable": [True],
    "estimated_impact": [invoices.loc[
        (invoices["ndc11"] == "12345678901") & (invoices["quarter"] == "2025-Q1"),
        "expected_rebate"
    ].sum()]
})
```

## Benefits of this approach

1. **Realism without cheating**: Uses real drug, utilization, and formulary data
2. **Control**: Synthetic contracts and anomalies are deterministic and labeled
3. **Scale**: Can generate millions of claims
4. **Reproducibility**: Same config produces same dataset
5. **Auditability**: Can trace any rebate gap back to claim and contract
6. **Privacy**: No real member IDs, group IDs, or PHI

## When to use public-data-backed synthesis vs. fully synthetic

### Use public-data-backed when:

- You need to convince stakeholders the data is realistic
- You want to test on real drug/utilization patterns
- You have access to the public datasets
- You want to onboard analysts on realistic examples

### Use fully synthetic when:

- Speed and simplicity are priorities
- You only care about anomaly detection logic, not realism
- Public data access is restricted
- You need highly controlled edge cases

## Trade-offs

| Aspect | Public-backed | Fully synthetic |
| --- | --- | --- |
| Realism | High | Medium |
| Speed | Slower (data pipeline) | Fast |
| Data quality | Depends on public sources | Perfect |
| Complexity | Higher (more joins) | Lower |
| Stakeholder buy-in | Higher | Lower |
| Flexibility | Lower (bound by public data) | Higher |

For production work, lean toward public-data-backed. For initial exploration and prototyping, fully synthetic is often faster.
