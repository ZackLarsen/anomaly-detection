# Required Data Fields

This document specifies the complete set of fields needed for rebate recovery analysis. See [data-model.md](data-model.md) for conceptual overview.

## 1. Pharmacy claim data

At minimum:

| Field category         | Examples                                                                                             |
| ---------------------- | ---------------------------------------------------------------------------------------------------- |
| Claim identifiers      | claim ID, original claim ID, reversal ID, adjusted claim ID                                          |
| Dates                  | fill date, adjudication date, paid date, reversal date, invoice quarter                              |
| Drug identity          | NDC11, NDC9, labeler, product, package, GPI, GCN, RxNorm, brand/generic indicator                    |
| Quantity               | quantity dispensed, unit of measure, package size, days supply, metric decimal quantity              |
| Financials             | ingredient cost, dispensing fee, tax, patient pay, plan paid, gross cost, AWP/WAC/NADAC if available |
| Claim status           | paid, reversed, adjusted, rejected, trial claim                                                      |
| Channel                | retail, mail, specialty, LTC, home infusion                                                          |
| Pharmacy               | NPI/NABP, chain, pharmacy type                                                                       |
| Prescriber             | NPI, specialty                                                                                       |
| Benefit attributes     | plan ID, group ID, carrier/account, line of business, funding type                                   |
| Utilization flags      | DAW, compound flag, maintenance flag, refill number, new/refill                                      |
| Coordination           | COB, secondary payer, Medicare/Medicaid indicator, government-program exclusion                      |
| Prior authorization/UM | PA flag, step therapy, quantity limit, formulary exception                                           |

## 2. Drug reference data

You need drug master data that changes over time. Important fields:

* NDC11 normalized format
* NDC effective dates and termination dates
* Brand name
* Generic name
* Labeler/manufacturer
* Rebate manufacturer/contracting entity
* GPI/GCN/RxNorm/Medispan/First Databank mappings
* Drug class/therapeutic category
* Brand/generic/single-source/multi-source status
* Specialty indicator
* Biosimilar/reference product relationships
* Package size and unit of measure
* WAC/AWP history
* FDA approval/launch/discontinuation dates, if available
* Authorized generic indicator
* Line extension indicator

The effective-dating matters. A claim filled in March should be matched to the NDC, manufacturer, formulary, and contract state that existed in March, not the current state.

## 3. Formulary and benefit design data

Needed fields:

* Formulary ID
* Plan/group/carrier mapping
* Effective dates
* Drug tier
* Preferred/non-preferred status
* Exclusion status
* Specialty tier
* PA/ST/QL requirements
* Brand-preferred-over-generic flags
* Biosimilar preference
* Medical-benefit carve-out indicators
* Pharmacy network/channel eligibility
* Custom formulary overrides for large clients

This is critical because many rebate contracts depend on formulary position.

## 4. Rebate contract data

This is the hardest and most sensitive dataset.

You need contract terms at the most granular level you can access:

| Contract field         | Examples                                                                           |
| ---------------------- | ---------------------------------------------------------------------------------- |
| Contract parties       | manufacturer, PBM, payer/client, rebate aggregator                                 |
| Effective dates        | start/end date, amendment dates                                                    |
| Product scope          | NDC, brand, GPI, therapeutic class, market basket                                  |
| Eligibility rules      | commercial only, Medicare excluded, Medicaid excluded, 340B excluded, COB excluded |
| Formulary requirements | preferred status, tier, exclusivity, PA restrictions                               |
| Rebate basis           | per script, per unit, percent of WAC, percent of AWP, market-share tier            |
| Guarantees             | PMPM guarantee, per-brand-script guarantee, aggregate minimum                      |
| True-up rules          | annual, quarterly, client-specific, PBM-retained spread                           |
| Admin fees             | manufacturer admin fee, PBM admin fee, data fee                                    |
| Dispute rules          | audit window, dispute reason codes, allowed adjustments                            |
| Data lags              | claims runout period, invoice timing, restatement cadence                          |

Some contracts may not be fully transparent to the plan. If the plan only receives PBM guarantee files rather than manufacturer-level rebate detail, the model should focus on **contractual guarantee recovery** rather than "true manufacturer rebate recovery."

## 5. Rebate invoice and payment data

You need both expected and actual rebate flows.

Fields:

* Invoice ID
* Invoice quarter
* Manufacturer
* PBM/client/group
* NDC/brand/product
* Utilization count
* Units
* Days supply
* Gross spend
* Rebate rate
* Expected rebate
* Invoiced rebate
* Paid rebate
* Disputed rebate
* Adjusted rebate
* Write-off
* Payment date
* Dispute reason
* Prior-period adjustments
* True-up amount
* Guarantee amount
* Admin-fee deductions

## 6. Eligibility and enrollment

Needed for denominator-based guarantees:

* Member months
* Plan/group eligibility spans
* Line of business
* Employer/client
* Funding arrangement
* PBM contract ID
* Benefit package
* State/region
* Medicare/Medicaid/commercial status

## 7. Medical claims (especially physician-administered drugs)

For some drugs, especially specialty injectables and infusions, rebates may be affected by medical-benefit utilization.

Needed fields:

* HCPCS/J-code
* NDC if available
* Units billed
* Units paid
* Revenue code
* Place of service
* Provider type
* Drug administration date
* Allowed amount
* Paid amount
* Crosswalk from HCPCS units to NDC units

This is a known problem area. Industry and government audit materials frequently identify NDC capture and HCPCS-to-NDC unit conversion as important for rebate invoicing accuracy.

## 8. External benchmark data

Useful but not always required:

* WAC/AWP pricing history
* Market-share data
* Competing product launches
* FDA drug shortage/discontinuation data
* Public Medicaid rebate or utilization files where relevant
* Internal historical rebate yield
* PBM performance guarantees
* Therapeutic-class benchmarks
* Manufacturer dispute benchmarks

Be careful: public rebate benchmarks are often stale, incomplete, or not comparable to your contracts.
