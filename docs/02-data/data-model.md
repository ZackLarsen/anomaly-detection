# Core Data Model

## Overview

A useful rebate recovery system needs more than pharmacy claims. The core data model should connect these entities:

```
claims → drug attributes → member/group eligibility → 
  formulary status → contract terms → rebate invoices → payments/disputes
```

## Entity relationship diagram (conceptual)

```
┌─────────────┐         ┌──────────────┐
│   Members   │─────────│  Pharmacy    │
│             │         │   Claims     │
└─────────────┘         └──────────────┘
      │                        │
      │                        │
      ▼                        ▼
┌─────────────┐         ┌──────────────┐
│  Enrollment │         │   Drug       │
│  & Groups   │         │   Master     │
└─────────────┘         └──────────────┘
      │                        │
      │                        ▼
      │                 ┌──────────────┐
      └────────────────→│  Formulary   │
                        │  History     │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Rebate      │
                        │  Contracts   │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Rebate      │
                        │  Invoices    │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Payments &  │
                        │  Disputes    │
                        └──────────────┘
```

## Core tables and key fields

See [required-data.md](required-data.md) for complete field specifications.

### Pharmacy claims

The foundation. Contains:

* Claim identifiers (claim ID, original claim ID, reversal ID, adjusted claim ID)
* Dates (fill date, adjudication date, paid date, reversal date, invoice quarter)
* Drug identity (NDC11, NDC9, labeler, product, package, GPI, GCN, RxNorm, brand/generic)
* Quantity (quantity dispensed, unit of measure, package size, days supply)
* Financials (ingredient cost, dispensing fee, tax, patient pay, plan paid, gross cost)
* Claim status (paid, reversed, adjusted, rejected, trial claim)
* Channel (retail, mail, specialty, LTC, home infusion)
* Pharmacy (NPI/NABP, chain, pharmacy type)
* Prescriber (NPI, specialty)
* Benefit (plan ID, group ID, carrier, line of business, funding type)
* Utilization flags (DAW, compound flag, maintenance flag, refill number)
* Coordination (COB, secondary payer, Medicare/Medicaid indicator, government-program exclusion)
* Prior authorization/UM (PA flag, step therapy, quantity limit, formulary exception)

### Drug master

Reference data that changes over time. Must include:

* NDC11 normalized format
* NDC effective dates and termination dates
* Brand name, generic name, labeler/manufacturer
* GPI/GCN/RxNorm/Medispan/First Databank mappings
* Drug class/therapeutic category
* Brand/generic/single-source/multi-source status
* Specialty indicator
* Biosimilar/reference product relationships
* Package size and unit of measure
* WAC/AWP history
* FDA approval/launch/discontinuation dates
* Authorized generic indicator
* Line extension indicator

**Critical**: The effective-dating matters. A claim filled in March should be matched to the NDC, manufacturer, formulary, and contract state that existed in March, not the current state.

### Formulary history

Formulary rules by plan, effective-dated:

* Formulary ID
* Plan/group/carrier mapping
* Effective dates
* Drug tier (preferred, non-preferred, excluded, specialty)
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

### Rebate contract terms

This is the hardest and most sensitive dataset. You need contract terms at the most granular level you can access:

* Contract parties (manufacturer, PBM, payer/client, rebate aggregator)
* Effective dates (start/end date, amendment dates)
* Product scope (NDC, brand, GPI, therapeutic class, market basket)
* Eligibility rules (commercial only, Medicare excluded, Medicaid excluded, 340B excluded, COB excluded)
* Formulary requirements (preferred status, tier, exclusivity, PA restrictions)
* Rebate basis (per script, per unit, percent of WAC, percent of AWP, market-share tier)
* Guarantees (PMPM guarantee, per-brand-script guarantee, aggregate minimum)
* True-up rules (annual, quarterly, client-specific, PBM-retained spread)
* Admin fees (manufacturer admin fee, PBM admin fee, data fee)
* Dispute rules (audit window, dispute reason codes, allowed adjustments)
* Data lags (claims runout period, invoice timing, restatement cadence)

**Note**: Some contracts may not be fully transparent to the plan. If the plan only receives PBM guarantee files rather than manufacturer-level rebate detail, the model should focus on **contractual guarantee recovery** rather than "true manufacturer rebate recovery."

### Rebate invoices

Both expected and actual rebate flows:

* Invoice ID, invoice quarter
* Manufacturer, PBM/client/group
* NDC/brand/product
* Utilization count, units, days supply
* Gross spend, rebate rate
* Expected rebate, invoiced rebate, paid rebate
* Disputed rebate, adjusted rebate, write-off
* Payment date, dispute reason
* Prior-period adjustments, true-up amount
* Guarantee amount, admin-fee deductions

### Eligibility and enrollment

Needed for denominator-based guarantees:

* Member months
* Plan/group eligibility spans
* Line of business
* Employer/client
* Funding arrangement (self-funded vs. fully insured)
* PBM contract ID
* Benefit package
* State/region
* Medicare/Medicaid/commercial status

### Medical claims (optional but important)

For some drugs, especially specialty injectables and infusions, rebates may be affected by medical-benefit utilization:

* HCPCS/J-code, NDC if available
* Units billed, units paid
* Revenue code, place of service, provider type
* Drug administration date
* Allowed amount, paid amount
* Crosswalk from HCPCS units to NDC units

This is a known problem area. Industry and government audit materials frequently identify NDC capture and HCPCS-to-NDC unit conversion as important for rebate invoicing accuracy.

## Design principles

1. **Temporal awareness**: Every claim and contract rule is effective-dated. Always respect the effective date.
2. **Grain clarity**: Know what grain each table is at (claim-level vs. aggregate vs. reference).
3. **Referential integrity**: Every claim NDC should map to drug master. Every rebate invoice should reconcile to claims.
4. **Auditability**: Store enough detail to explain any calculated value (expected rebate, rebate gap, etc.) back to source claims and contracts.
5. **Change tracking**: Track versions of contracts, formulary rules, and NDC mappings for audit trails.

See [required-data.md](required-data.md) for complete specifications and [data-quality-controls.md](data-quality-controls.md) for validation rules.
