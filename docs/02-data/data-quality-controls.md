# Data Quality Controls

Before modeling, implement these controls. They prevent garbage-in-garbage-out.

## Claim controls

* Paid minus reversed claims reconciles to invoice utilization.
* Days supply and quantity are nonzero and plausible.
* NDC is normalized to 11 digits.
* Claim quarter matches invoice quarter logic.
* Duplicate claims are removed.
* Adjustments are netted correctly.

## Drug controls

* Every claim NDC maps to drug master.
* Every brand maps to manufacturer.
* Every NDC maps to package size and unit.
* NDC effective dates are respected.
* New NDCs are detected monthly.

## Contract controls

* Every rebate-eligible product maps to a contract rule.
* Overlapping contract rules are flagged.
* Contract amendments are versioned.
* Formulary requirements are effective-dated.
* Guarantees are represented explicitly.

## Invoice/payment controls

* Invoice lines reconcile to claim aggregates.
* Payment lines reconcile to invoices.
* Disputes reconcile to unpaid amounts.
* Prior-period adjustments are traceable.
* True-ups are linked to guarantees.

## Implementation approach

### Test framework

Create a suite of tests that runs before every modeling run:

```python
def test_all_claim_ndcs_in_drug_master():
    """Every NDC on a claim must exist in drug master."""
    claim_ndcs = set(claims['ndc11'].unique())
    drug_master_ndcs = set(drug_master['ndc11'].unique())
    orphan_ndcs = claim_ndcs - drug_master_ndcs
    assert len(orphan_ndcs) == 0, f"Orphan NDCs: {orphan_ndcs}"

def test_paid_reversed_reconciles():
    """Paid minus reversed should reconcile to invoice utilization."""
    paid = claims[claims['status'] == 'PAID'].shape[0]
    reversed = claims[claims['status'] == 'REVERSED'].shape[0]
    net = paid - reversed
    
    invoice_util = invoices['utilization_count'].sum()
    assert abs(net - invoice_util) < 100, f"Reconciliation gap: {abs(net - invoice_util)}"

def test_no_duplicate_claims():
    """Duplicate claims should be removed before analysis."""
    duplicates = claims.duplicated(subset=['claim_id'])
    assert not duplicates.any(), f"Found {duplicates.sum()} duplicate claim IDs"

def test_effective_dates_respected():
    """Claims must use contract/formulary rules effective at claim date."""
    for _, claim in claims.iterrows():
        contract = get_contract(claim['ndc11'], claim['group_id'], claim['fill_date'])
        assert contract is not None, f"No contract for {claim['ndc11']} on {claim['fill_date']}"

def test_expected_rebate_non_negative():
    """Expected rebate should never be negative."""
    assert (invoices['expected_rebate'] >= 0).all(), "Found negative expected rebates"

def test_actual_rebate_nonzero_when_utilization_exists():
    """If utilization exists, actual rebate should be non-zero (usually)."""
    has_util = invoices['utilization_count'] > 0
    has_rebate = invoices['actual_rebate'] > 0
    
    zero_rebate_with_util = has_util & ~has_rebate
    assert zero_rebate_with_util.sum() < 20, f"Found {zero_rebate_with_util.sum()} lines with util but no rebate"
```

### Data quality dashboard

Track these metrics monthly:

* Missing NDC rate
* Missing contract rate
* Missing formulary rate
* Invoice match rate
* Payment match rate
* New unmapped NDCs
* Reversal mismatch rate
* Unit conversion exceptions
* Days supply outliers
* Quantity outliers

Alert when any metric deteriorates or falls outside historical norms.

### When to stop

Do not proceed to modeling if:

* > 5% of claims have orphan NDCs
* > 10% of invoice lines lack matching claims
* > 1% of claims have invalid NDC format
* Paid/reversed claim count doesn't reconcile to invoice within 1%
* Contract effective dates are missing for > 5% of products
* Reversal/adjustment imbalance exceeds 2% of claim count

Fix the data quality issue first. It's cheaper than debugging a bad model.
