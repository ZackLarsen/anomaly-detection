# Validation and Testing of Synthetic Data

Bad synthetic data will mislead your models. Comprehensive validation tests are essential.

## Why validation matters

Synthetic data often has structural errors that hide in plain sight:

* Claims reference NDCs that don't exist in the drug master
* Rebate invoices aggregate differently than the claims that generated them
* Anomalies injected at one point in the pipeline contradict data at another
* Effective dates are disrespected (e.g., using current formulary for historical claims)
* Reversals and adjustments don't net correctly

These bugs will cause your anomaly models to appear to work on synthetic data but fail on real data.

## Testing pyramid

Layer your tests from simple to complex:

```
        Integration tests (full pipeline reconciliation)
       ╱                                              ╲
      ╱    Schema + relationship tests                 ╲
     ╱         (referential integrity)                  ╲
    ╱              Unit tests                            ╲
   ╱          (individual generators)                     ╲
```

## Unit tests (generators)

Test each synthetic data generator in isolation.

### Drug master generator

```python
def test_drug_master_ndcs_are_unique():
    """Each NDC should appear only once."""
    drug_df = generate_drug_master(n_drugs=100)
    assert not drug_df["ndc11"].duplicated().any()

def test_drug_master_effective_dates_valid():
    """Effective dates must be sensible."""
    drug_df = generate_drug_master(n_drugs=100)
    assert (drug_df["eff_date"] <= drug_df["end_date"]).all()

def test_drug_master_has_manufacturer():
    """Every drug must have a manufacturer."""
    drug_df = generate_drug_master(n_drugs=100)
    assert drug_df["manufacturer"].notna().all()
```

### Claim generator

```python
def test_claims_reference_valid_ndcs():
    """Every claim NDC must exist in drug master."""
    claims_df = generate_claims(n_claims=1000)
    drug_df = generate_drug_master()
    
    orphan_ndcs = set(claims_df["ndc11"]) - set(drug_df["ndc11"])
    assert len(orphan_ndcs) == 0, f"Orphan NDCs: {orphan_ndcs}"

def test_claims_have_valid_quantities():
    """Quantity and days supply should be nonzero and plausible."""
    claims_df = generate_claims(n_claims=1000)
    
    assert (claims_df["quantity"] > 0).all()
    assert (claims_df["days_supply"] > 0).all()
    assert (claims_df["days_supply"] <= 365).all()

def test_claims_channel_is_valid():
    """Channel must be one of known values."""
    claims_df = generate_claims(n_claims=1000)
    valid_channels = {"retail", "mail", "specialty", "ltc"}
    assert set(claims_df["channel"]) <= valid_channels
```

### Contract generator

```python
def test_contracts_have_effective_dates():
    """Every contract must have effective dates."""
    contracts_df = generate_contracts(n_contracts=100)
    
    assert contracts_df["eff_date"].notna().all()
    assert contracts_df["end_date"].notna().all()

def test_contracts_rebate_rates_plausible():
    """Rebate rates should be in expected range."""
    contracts_df = generate_contracts(n_contracts=100)
    
    # Per-script rebates: typically $1-50
    per_script = contracts_df[contracts_df["rebate_basis"] == "PER_30_DAY_SCRIPT"]
    assert (per_script["rebate_rate"] >= 1).all()
    assert (per_script["rebate_rate"] <= 50).all()
    
    # Percent rebates: typically 10-40% 
    pct = contracts_df[contracts_df["rebate_basis"] == "PERCENT_GROSS_COST"]
    assert (pct["rebate_rate"] >= 0.10).all()
    assert (pct["rebate_rate"] <= 0.40).all()
```

## Schema and relationship tests

Test that tables relate correctly to each other.

### Referential integrity

```python
def test_all_claim_ndcs_in_drug_master():
    """Every claim's NDC must exist in drug master."""
    claims_df = generate_claims()
    drug_df = generate_drug_master()
    
    claim_ndcs = set(claims_df["ndc11"].unique())
    drug_ndcs = set(drug_df["ndc11"].unique())
    orphan = claim_ndcs - drug_ndcs
    
    assert len(orphan) == 0, f"Orphans: {orphan}"

def test_all_invoice_ndcs_in_drug_master():
    """Every invoice's NDC must exist in drug master."""
    invoices_df = generate_invoices()
    drug_df = generate_drug_master()
    
    invoice_ndcs = set(invoices_df["ndc11"].unique())
    drug_ndcs = set(drug_df["ndc11"].unique())
    orphan = invoice_ndcs - drug_ndcs
    
    assert len(orphan) == 0

def test_all_contracts_reference_valid_brands():
    """Every contract's brand must be valid."""
    contracts_df = generate_contracts()
    drug_df = generate_drug_master()
    
    contract_brands = set(contracts_df["brand_family"].unique())
    drug_brands = set(drug_df["brand_family"].unique())
    orphan = contract_brands - drug_brands
    
    assert len(orphan) == 0
```

### Effective dating

```python
def test_claims_before_ndc_launch_excluded():
    """Claims should not exist before NDC launch date."""
    claims_df = generate_claims()
    drug_df = generate_drug_master()
    
    merged = claims_df.merge(
        drug_df[["ndc11", "launch_date"]],
        on="ndc11"
    )
    
    before_launch = merged[merged["fill_date"] < merged["launch_date"]]
    assert len(before_launch) == 0, f"Found {len(before_launch)} claims before NDC launch"

def test_claims_after_ndc_discontinuation_excluded():
    """Claims should not exist after NDC discontinuation."""
    claims_df = generate_claims()
    drug_df = generate_drug_master()
    
    merged = claims_df.merge(
        drug_df[["ndc11", "end_date"]],
        on="ndc11"
    )
    
    after_disc = merged[merged["fill_date"] > merged["end_date"]]
    assert len(after_disc) == 0

def test_contracts_effective_on_claim_dates():
    """For each claim, a contract should be effective."""
    claims_df = generate_claims()
    contracts_df = generate_contracts()
    
    for _, claim in claims_df.iterrows():
        matching_contracts = contracts_df[
            (contracts_df["ndc11"] == claim["ndc11"])
            & (contracts_df["client_id"] == claim["client_id"])
            & (contracts_df["eff_date"] <= claim["fill_date"])
            & (contracts_df["end_date"] >= claim["fill_date"])
        ]
        assert len(matching_contracts) > 0, \
            f"No contract for NDC {claim['ndc11']} on {claim['fill_date']}"
```

## Reconciliation tests

Test that aggregates match expected values.

### Claim-to-invoice reconciliation

```python
def test_invoice_utilization_matches_claims():
    """Invoice line count should match paid claims after reversals."""
    claims_df = generate_claims()
    invoices_df = generate_invoices()
    
    # Count paid claims by NDC/client/quarter
    paid_claims = claims_df[claims_df["status"] == "PAID"].groupby(
        ["ndc11", "client_id", "quarter"]
    ).size().reset_index(name="paid_count")
    
    reversed_claims = claims_df[claims_df["status"] == "REVERSED"].groupby(
        ["ndc11", "client_id", "quarter"]
    ).size().reset_index(name="reversed_count")
    
    paid_claims = paid_claims.merge(reversed_claims, on=["ndc11", "client_id", "quarter"], how="left")
    paid_claims["reversed_count"] = paid_claims["reversed_count"].fillna(0)
    paid_claims["net_count"] = paid_claims["paid_count"] - paid_claims["reversed_count"]
    
    # Compare to invoices
    for _, row in paid_claims.iterrows():
        invoice = invoices_df[
            (invoices_df["ndc11"] == row["ndc11"])
            & (invoices_df["client_id"] == row["client_id"])
            & (invoices_df["quarter"] == row["quarter"])
        ]
        
        if len(invoice) > 0:
            assert abs(invoice.iloc[0]["utilization_count"] - row["net_count"]) < 10, \
                f"Utilization mismatch for {row['ndc11']}"

def test_invoice_gross_cost_matches_claims():
    """Invoice gross cost should aggregate from claims."""
    claims_df = generate_claims()
    invoices_df = generate_invoices()
    
    claims_grouped = claims_df[claims_df["status"] == "PAID"].groupby(
        ["ndc11", "client_id", "quarter"]
    )["gross_cost"].sum().reset_index()
    
    for _, row in claims_grouped.iterrows():
        invoice = invoices_df[
            (invoices_df["ndc11"] == row["ndc11"])
            & (invoices_df["client_id"] == row["client_id"])
            & (invoices_df["quarter"] == row["quarter"])
        ]
        
        if len(invoice) > 0:
            # Allow 1% tolerance for rounding
            tolerance = max(row["gross_cost"] * 0.01, 100)
            assert abs(invoice.iloc[0]["gross_cost"] - row["gross_cost"]) < tolerance
```

### Expected vs. actual rebate

```python
def test_expected_rebate_non_negative():
    """Expected rebate should never be negative."""
    invoices_df = generate_invoices()
    assert (invoices_df["expected_rebate"] >= 0).all()

def test_actual_rebate_normally_close_to_expected():
    """In normal world, actual should be ~95-105% of expected."""
    invoices_df = generate_invoices()
    
    # Exclude obvious anomalies (we'll inject those separately)
    normal = invoices_df[invoices_df["anomaly_type"].isna()]
    
    ratio = normal["actual_rebate"] / normal["expected_rebate"].replace(0, np.nan)
    
    # 95% of observations should be in 0.90–1.10 range
    within_range = ((ratio >= 0.90) & (ratio <= 1.10)).sum()
    assert within_range / len(normal) > 0.95, \
        f"Only {within_range/len(normal)*100:.1f}% of ratios in expected range"
```

## Anomaly injection tests

Test that injected anomalies have the right properties.

### Missing rebate scenario

```python
def test_missing_rebate_anomalies_have_positive_expected():
    """Missing rebate anomalies should have positive expected rebate."""
    invoices_df = generate_invoices()
    labels_df = generate_labels()
    
    missing_labels = labels_df[labels_df["anomaly_type"] == "MISSING_REBATE"]
    
    for _, label in missing_labels.iterrows():
        invoice = invoices_df[
            (invoices_df["ndc11"] == label["ndc11"])
            & (invoices_df["client_id"] == label["client_id"])
            & (invoices_df["quarter"] == label["quarter"])
        ]
        
        assert len(invoice) > 0
        assert invoice.iloc[0]["expected_rebate"] > 0, \
            "Missing rebate must have positive expected"
        assert invoice.iloc[0]["actual_rebate"] == 0, \
            "Missing rebate must have zero actual"

def test_yield_collapse_anomalies_have_utilization():
    """Yield collapse anomalies should have claims but low rebates."""
    claims_df = generate_claims()
    invoices_df = generate_invoices()
    labels_df = generate_labels()
    
    collapse_labels = labels_df[labels_df["anomaly_type"] == "YIELD_COLLAPSE"]
    
    for _, label in collapse_labels.iterrows():
        # Should have claims
        claims = claims_df[
            (claims_df["ndc11"] == label["ndc11"])
            & (claims_df["quarter"] == label["quarter"])
        ]
        assert len(claims) > 0
        
        # Invoice should show low ratio
        invoice = invoices_df[
            (invoices_df["ndc11"] == label["ndc11"])
            & (invoices_df["quarter"] == label["quarter"])
        ]
        if len(invoice) > 0:
            ratio = invoice.iloc[0]["actual_rebate"] / invoice.iloc[0]["expected_rebate"]
            assert ratio < 0.5, "Yield collapse should have ratio < 0.5"
```

## Integration tests

Test the full pipeline end-to-end.

```python
def test_full_pipeline_produces_valid_data():
    """Generate full synthetic dataset and validate."""
    # Generate all tables
    drug_df = generate_drug_master(n_drugs=50)
    formulary_df = generate_formulary(n_plans=10)
    claims_df = generate_claims(n_claims=10000)
    contracts_df = generate_contracts(n_contracts=100)
    invoices_df = generate_invoices()
    labels_df = generate_labels()
    
    # Run all validation tests
    assert len(drug_df) > 0
    assert len(claims_df) > 0
    assert len(invoices_df) > 0
    
    # Check referential integrity
    claim_ndcs = set(claims_df["ndc11"].unique())
    drug_ndcs = set(drug_df["ndc11"].unique())
    assert claim_ndcs <= drug_ndcs
    
    # Check reconciliation
    # ... (use tests from reconciliation section above)
    
    # Check anomalies
    # ... (use tests from anomaly injection section above)
    
    print(f"✓ Drug master: {len(drug_df)} drugs")
    print(f"✓ Claims: {len(claims_df)} claims")
    print(f"✓ Invoices: {len(invoices_df)} invoice lines")
    print(f"✓ Anomalies: {len(labels_df)} labeled anomalies")
    print(f"✓ All validation tests passed")
```

## Validation checklist

Before using synthetic data for modeling, confirm:

- [ ] No orphan NDCs (all claim NDCs exist in drug master)
- [ ] No orphan contracts (all claims can be matched to a contract)
- [ ] Effective dates respected (claims before NDC launch excluded)
- [ ] Reversals net correctly (paid - reversed = invoice utilization)
- [ ] Gross cost aggregates (invoice total = sum of claim costs)
- [ ] Expected rebate non-negative
- [ ] Normal rebates within 90–110% of expected (before anomaly injection)
- [ ] Anomalies correctly labeled
- [ ] Anomaly labels complete (every injected anomaly is labeled)
- [ ] Data volume reasonable (not too sparse, not degenerate)

Fail fast: If any test fails, stop and debug. Bad synthetic data will waste weeks of modeling time.
