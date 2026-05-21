# Common Anomaly Patterns in Rx Rebate Recovery

## Pattern 1: New NDC not mapped

**Symptom:** Brand has claims for a new package/NDC, but invoice excludes it.

**Detection:**

* NDC launch age < 12 months
* Brand family contracted
* Missing contract mapping
* Expected rebate > 0
* Actual rebate = 0

**Likely action:**

* Update NDC-to-contract map
* Rebill prior quarters within audit window

**Example:** Brand X launches new strength NDC 98765432101. Claims show 200 scripts, expected $8K rebate. But NDC not on invoice. Map to existing contract, dispute for backfill.

## Pattern 2: Rebate yield collapse

**Symptom:** Rebate per 30-day script drops sharply without utilization or formulary change.

**Detection:**

* Stable claim count
* Stable WAC/gross cost
* Stable formulary tier
* Actual rebate down 60%+
* Contract still active

**Likely action:**

* Review invoice rate, formulary status, and PBM/manufacturer dispute

**Example:** Brand Y normally $15/script. Q2 2025 drops to $4/script. 500 scripts so far. Same formulary status, same utilization. Check if PBM withheld rebate due to dispute.

## Pattern 3: Specialty channel omission

**Symptom:** Retail claims receive rebate; specialty claims do not.

**Detection:**

* Same NDC
* Same plan/client
* Different channel
* Specialty actual/expected ratio near zero
* Retail ratio normal

**Likely action:**

* Check contract channel eligibility
* Check PBM specialty carve-out
* Check invoice feed inclusion

**Example:** Brand Z rebates normally for retail. Specialty channel shows $12K expected, $0 actual. Contract says specialty should be included. PBM might have specialty on a separate invoice feed.

## Pattern 4: Incorrect exclusion

**Symptom:** Claims excluded due to COB, government program, 340B, or non-commercial flag, but eligibility suggests they should be included.

**Detection:**

* Exclusion reason present
* Member LOB commercial
* Plan paid positive
* No secondary payer
* Expected rebate positive

**Likely action:**

* Audit exclusion logic

**Example:** 50 claims marked as "Medicare" but member age is 32. Claims have plan_paid > 0. Likely data error; should be included in rebate.

## Pattern 5: Unit conversion error

**Symptom:** Rebate amount is consistently off by a factor such as 10, 100, package size, or HCPCS-to-NDC conversion.

**Detection:**

* Actual/expected ratio near 0.1, 0.01, 10, 100, etc.
* High-cost injectable
* Medical benefit or specialty product
* Quantity/unit mismatch

**Likely action:**

* Review unit-of-measure conversion and NDC package size

**Example:** Injectable drug with 10-unit vials. Rebate expected per unit = $5. Invoice shows rebate per vial instead of per unit. Actual rebate is 1/10 of expected.

## Pattern 6: Guarantee true-up missing

**Symptom:** Aggregate rebates below PBM/client guarantee, but no true-up payment.

**Detection:**

* Contract guarantee amount > actual passed-through rebate
* End-of-year or quarter true-up absent
* PMPM guarantee shortfall

**Likely action:**

* Contract audit against PBM guarantee language

**Example:** Client guaranteed $500K per year. Year-end calculation: $450K earned. Should get $50K true-up payment in Q1 next year. Payment not received.

## Pattern 7: Manufacturer dispute spike

**Symptom:** Invoiced rebates look correct, but paid rebates are low because disputes/write-offs rise.

**Detection:**

* Disputed amount / invoiced amount high
* Concentrated in manufacturer/product
* Prior quarters normal
* Reason code changes

**Likely action:**

* Review manufacturer dispute reason and supporting utilization data

**Example:** Brand A normally has 1% disputes. Q2 2025 has 15% disputes all marked "utilization mismatch." Previous quarters reconciled fine. Investigation shows PBM changed unit conversion logic.

## Pattern 8: Reversal without original

**Symptom:** Reversed claims exist without matching original claims.

**Detection:**

* Reversal claim ID present
* Original claim ID missing or not found
* Pattern suggests systematic reconciliation issue

**Likely action:**

* Data quality audit; investigate PBM feed

## Pattern 9: Late claim after invoice cutoff

**Symptom:** Claim paid after quarter-end invoice cutoff, not included in invoice.

**Detection:**

* Claim fill date in Q1
* Claim paid in Q2
* Invoice generated at Q1-end
* Claim missing from Q1 invoice

**Likely action:**

* Request Q1 restatement or Q2 inclusion (per contract terms)

## Pattern 10: Product tier mismatch

**Symptom:** Product is preferred on formulary but rebate doesn't reflect preferred status.

**Detection:**

* Formulary says preferred
* Rebate realization below preferred-tier expectations
* Rate applied = non-preferred rate
* Invoice shows non-preferred dollars

**Likely action:**

* Check if PBM applied wrong tier; dispute for adjustment

## Detection strategy by pattern

| Pattern | Rules | Statistical | ML | Time-Series |
|---------|-------|------------|----|----|
| 1. New NDC unmapped | ✓ | ✓ | - | - |
| 2. Yield collapse | ✓ | ✓ | ✓ | ✓ |
| 3. Channel omission | ✓ | ✓ | ✓ | - |
| 4. Incorrect exclusion | ✓ | - | - | - |
| 5. Unit conversion | ✓ | ✓ | ✓ | - |
| 6. Missing true-up | ✓ | - | - | - |
| 7. Dispute spike | ✓ | ✓ | ✓ | ✓ |
| 8. Reversal orphan | ✓ | - | - | - |
| 9. Late claim | ✓ | - | - | - |
| 10. Tier mismatch | ✓ | ✓ | ✓ | - |

**Key insight**: Every pattern is detectable with rules alone. Statistical and ML enhance coverage but are not required.

## Recoverability assessment

Not every anomaly pattern is recoverable:

| Pattern | Typical Recoverability | Why it matters |
|---------|----------------------|---|
| 1. New NDC unmapped | High (85%) | Straightforward mapping fix |
| 2. Yield collapse | Medium (60%) | May reflect legitimate contract change |
| 3. Channel omission | High (80%) | Contract usually clear on channels |
| 4. Incorrect exclusion | High (90%) | Data error easy to fix |
| 5. Unit conversion | High (85%) | Clear calculation error |
| 6. Missing true-up | Medium (70%) | Depends on contract language |
| 7. Dispute spike | Low–Medium (30–50%) | Disputes hard to overturn |
| 8. Reversal orphan | High (80%) | Data reconciliation |
| 9. Late claim | Medium (40%) | Depends on contract cutoff terms |
| 10. Tier mismatch | High (85%) | Objective formulary vs invoice comparison |

Prioritize high-recoverability patterns; deprioritize low ones.
