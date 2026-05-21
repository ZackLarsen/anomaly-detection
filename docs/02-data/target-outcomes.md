# Target Outcomes

You need to decide what the model is detecting. This document defines the specific variables and outcomes your anomaly detection model should focus on.

## Financial anomaly targets

Focus on dollar gaps between expected and actual rebates:

* `expected_rebate_amount - actual_rebate_amount`
* `expected_rebate_per_script - actual_rebate_per_script`
* `actual_rebate / gross_drug_cost`
* `actual_rebate / WAC`
* `rebate_yield_vs_contract_minimum`
* `unpaid_rebate_amount`
* `disputed_rebate_amount`
* `writeoff_rate`
* `guarantee_shortfall_amount`

## Operational anomaly targets

These flags identify data quality and process issues:

* Missing contract mapping
* Missing formulary mapping
* Missing rebate invoice line
* Missing or invalid NDC
* Unexpected exclusion
* Unexpected reversal/adjustment pattern
* Claim included in utilization but excluded from invoice
* Product included last quarter but absent this quarter
* Manufacturer payment materially below invoice

## Prioritization target

The most useful score is not merely anomaly probability. It is:

> **Expected recoverable dollars = probability of true leakage × estimated dollar gap × probability of successful recovery**

That last term matters. A weird pattern that is contractually valid is not worth chasing.

### Example prioritization formula

```text
priority_score = 
  (anomaly_probability × 0.5)
  + (rebate_gap_dollars × 0.3)
  + (recoverability_probability × 0.2)
```

Add business rules:

* Minimum dollar threshold (e.g., only flag gaps > $5,000)
* Contract audit window (e.g., only recoverable within 2 years)
* Manufacturer dispute deadline
* Client materiality threshold
* Data completeness score
* Legal/compliance sensitivity

## Modeling considerations

### What to optimize for

* **Precision at K** — Of the top 100 cases, how many are true leakage?
* **Dollars captured at K** — Of the top 100 cases, how many dollars were recovered?
* **Net recovery after cost** — Recovered dollars minus analyst review cost
* **False-positive review burden** — Don't waste analyst time

### What NOT to optimize for

* Total anomaly count — More anomalies doesn't mean more recovery
* Anomaly probability alone — A low-probability anomaly worth $500K is better than a high-probability anomaly worth $500
* Statistical weirdness — Contractually valid exceptions shouldn't be flagged

## Grain-specific targets

Different analytical grains may have different targets:

### Claim level
* Eligibility errors
* Missing NDC/contract/formulary mapping
* Incorrect exclusions

### NDC × client × quarter
* Product-level rebate leakage
* Sudden yield drops
* Unit problems

### Manufacturer × client × quarter
* Invoice/payment shortfalls
* Guarantee issues
* Dispute anomalies

### Contract × quarter
* PBM guarantee audits
* Annual true-ups
* Aggregate leakage

See [../03-modeling/analytic-grains.md](../03-modeling/analytic-grains.md) for more detail on which grain to use for each anomaly type.
