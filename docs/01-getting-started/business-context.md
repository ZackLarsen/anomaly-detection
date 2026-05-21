# Business Context: Rebate Recovery in Health Insurance

## The business objective

For a health insurance company, the goal is not "detect weird claims" in the abstract. The goal is to find **recoverable rebate leakage**: prescriptions, utilization, products, contracts, or invoices where the plan likely should have received more manufacturer rebate dollars than it did.

In commercial health insurance, rebates are typically retrospective payments from drug manufacturers, often tied to:

* Formulary placement
* Product utilization
* Market-basket performance
* Exclusivity/preferred status
* Contract terms

PBM rebate arrangements can include pass-through rebates, guaranteed minimum rebates, per-script guarantees, percentage-of-rebate sharing, PMPM guarantees, formulary compliance requirements, or administrative-fee structures.

## Where anomalies occur

Rebate leakage often shows up as **exceptions** at four analytical layers:

### A. Claim-level leakage

At the prescription claim level, ask:

> Given this drug, plan, formulary, channel, date, contract, and eligibility state, should this claim have generated rebate value?

Examples:

* Brand claim missing from rebate-eligible population.
* NDC excluded even though GPI/brand family is contracted.
* Incorrect units or package quantity lowering expected rebate.
* Specialty claims omitted from rebate files.
* Paid claims reversed after invoice cutoff but not corrected later.

### B. Product-level leakage

At NDC, GPI, brand, or therapeutic-class level:

> Is the actual rebate yield materially lower than comparable or historical experience?

Examples:

* Rebate per script falls from $400 to $40 for a brand with no contract change.
* A new NDC launch is not mapped to the existing brand contract.
* Biosimilar/reference-product mapping causes the wrong rebate rule to apply.
* A drug moves formulary tier, but the rebate rate used does not change.

### C. Contract/invoice-level leakage

At the manufacturer, PBM, contract, or quarterly invoice level:

> Does the invoiced or paid rebate match the guarantee or contractual economics?

Examples:

* PBM guarantee shortfall.
* Minimum rebate guarantee not trued up.
* Admin fees deducted incorrectly.
* Rebates booked to wrong client, group, carrier, or plan sponsor.
* Manufacturer dispute write-offs are abnormally high.

### D. Process/control anomalies

At the operational level:

> Are there systematic data quality or workflow problems causing leakage?

Examples:

* Missing NDCs.
* Invalid 11-digit NDC normalization.
* HCPCS/J-code claims lacking NDC detail.
* Gaps between claims adjudication, formulary files, and rebate invoicing.
* Mismatched calendar quarter versus service date quarter.
* Late-arriving claims not re-invoiced.

## Why this matters

Medicaid rebate audits have repeatedly emphasized the importance of accurate utilization data, NDCs, unit conversion, and claim-level drug identifiers. For example, HHS OIG reported that states could obtain substantial additional rebates for physician-administered drugs when NDC-level utilization is captured and invoiced correctly.

Even if your company is focused on commercial rebates rather than Medicaid, the same analytical principle applies:

> **Rebate recovery depends on accurate drug identity, utilization, units, eligibility, and contract mapping.**

## The analytical strategy

1. **Estimate** expected rebate dollars using contract rules, claim utilization, and formulary status.
2. **Compare** to actual rebate dollars received.
3. **Rank** suspicious gaps by:
   - Probability of true leakage
   - Estimated dollar gap
   - Probability of successful recovery
4. **Route** the highest-value cases for audit or contract review.

The most useful score is not merely anomaly probability. It is:

> **Expected recoverable dollars = probability of true leakage × estimated dollar gap × probability of successful recovery**

That last term matters. A weird pattern that is contractually valid is not worth chasing.
