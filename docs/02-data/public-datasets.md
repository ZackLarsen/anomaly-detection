# Public Datasets for Synthetic Data

Yes, public datasets can replace **some** of the synthetic data generation, especially drug master data, utilization distributions, prices, formulary structure, and medical-benefit crosswalks. But they **cannot replace the core commercial rebate pieces**: private rebate contracts, PBM/client guarantees, claim-level commercial utilization, actual paid rebates, manufacturer disputes, and recoverability outcomes.

The practical answer is:

> Use public data to make the synthetic world realistic.
> Still synthesize contracts, invoices, rebate payments, leakage events, and labels.

## Best public datasets to use

| Dataset                                             |                                                      Use it for |              Can it replace synthetic data? |
| --------------------------------------------------- | --------------------------------------------------------------: | ------------------------------------------: |
| CMS Medicaid State Drug Utilization Data            | Real NDC-level quarterly utilization and reimbursement by state |                           **Partially yes** |
| CMS Medicare Part D Prescriber / Spending data      |             Real drug-level Part D volumes and gross drug costs |                           **Partially yes** |
| CMS Part D Formulary / Pharmacy Network files       |                Real formulary tiers, PA/ST/QL, plan formularies |            **Yes, for formulary structure** |
| FDA NDC Directory                                   |                       Real NDC/product/package/labeler metadata |           **Yes, for drug master backbone** |
| FDA Orange Book                                     |       Brand/generic, TE codes, approval data, applicant, RLD/RS |               **Yes, for product metadata** |
| RxNorm                                              |                 Normalized drug names and drug concept mappings |             **Yes, for vocabulary mapping** |
| CMS NADAC                                           |                      Retail pharmacy acquisition-cost benchmark |          **Yes, for price/cost enrichment** |
| CMS ASP files and NDC-HCPCS crosswalks              |              Medical-benefit drug pricing and HCPCS/NDC mapping | **Yes, for Part B/medical drug simulation** |
| Medicaid Drug Rebate Program product data           |                        Medicaid rebate-program product universe |                           **Partially yes** |
| Medicare Part D manufacturer rebate summary reports |                                        Aggregate rebate context |                                 **Limited** |

---

# 1. CMS Medicaid State Drug Utilization Data

This is one of the most useful public datasets for your use case.

CMS says State Drug Utilization Data has been reported by states since the start of the Medicaid Drug Rebate Program for covered outpatient drugs paid by Medicaid agencies. ([Medicaid][1])

It typically includes:

* state
* year/quarter
* NDC
* product name
* units reimbursed
* number of prescriptions
* Medicaid amount reimbursed
* non-Medicaid amount reimbursed
* total amount reimbursed

## How it helps

You can use it to generate realistic:

* NDC-level utilization
* quarterly seasonality
* state-level variation
* drug volume distributions
* high-cost versus high-volume drug patterns
* reimbursement-per-unit patterns
* Medicaid-style rebate invoicing simulations

## What it can replace

It can replace a lot of the synthetic **utilization generator**.

Instead of randomly generating NDC volumes, you can seed your synthetic claims or aggregate tables from actual Medicaid NDC-quarter utilization.

For example, instead of this:

```python
claim_count = random_poisson(...)
units = random_gamma(...)
```

use:

```text
claim_count ≈ number_of_prescriptions from SDUD
units ≈ units_reimbursed from SDUD
gross_cost ≈ total_amount_reimbursed from SDUD
```

Then inject synthetic rebate contracts and leakage anomalies on top.

## Limitations

It is Medicaid, not commercial. It is also aggregate, not claim-level. It will not give you:

* commercial PBM contract terms
* commercial formulary status
* actual manufacturer rebate payments
* paid rebate disputes
* member-level or claim-level data
* PBM guarantee structures

Still, for **aggregate NDC × quarter anomaly modeling**, it is very useful.

---

# 2. CMS Medicare Part D Spending and Prescriber datasets

CMS Medicare Part D data is useful for realistic drug spending and utilization. The Medicare Part D Prescribers by Provider and Drug dataset contains prescription fills and total drug cost organized by prescriber NPI, drug brand name, and generic name. ([CMS Data][2])

CMS's quarterly Part D spending data reports gross drug cost metrics. However, the important catch is that Part D public spending metrics do **not** reflect manufacturer rebates or other price concessions. CMS is prohibited from publicly disclosing such information. ([DATALUMOS][3])

## How it helps

Use it for:

* real drug-level utilization volumes
* real gross drug cost distributions
* brand/generic spending patterns
* prescriber-level concentration
* geographic variation
* high-cost specialty-drug behavior
* trend and seasonality calibration

## What it can replace

It can replace synthetic generation of:

* drug popularity
* drug cost distributions
* gross-cost trends
* prescriber concentration
* utilization volatility

## What it cannot replace

It cannot replace:

* rebate amounts
* rebate invoices
* rebate contracts
* actual net cost after rebates
* PBM/manufacturer disputes
* commercial client-level behavior

So, for rebate recovery, Medicare Part D public data is a good **utilization and cost realism source**, not a rebate source.

---

# 3. CMS Part D Formulary and Pharmacy Network files

This is highly relevant.

CMS's monthly Part D formulary and pharmacy network public use files contain formulary and pharmacy network data for Medicare Prescription Drug Plans and Medicare Advantage Prescription Drug plans. ([CMS Data][4]) Quarterly files include plan information and basic drug formulary details such as NDCs, cost-share tier, step therapy, quantity limits, and prior authorization indicators. ([Data.gov][5])

## How it helps

Use it to build realistic formulary features:

* tier
* formulary inclusion
* prior authorization
* step therapy
* quantity limits
* plan/formulary identifiers
* plan-level variation
* monthly or quarterly formulary changes

## What it can replace

This can largely replace synthetic formulary generation.

Instead of inventing tiers and PA/ST/QL flags, use real Part D formulary structures, then map them into your synthetic commercial environment.

## Caveat

Part D formularies are not the same as commercial formularies. But structurally, they are close enough to make your test data much more realistic.

---

# 4. FDA NDC Directory

The FDA NDC Directory is one of the best sources for building a drug master backbone.

Use it for:

* real NDCs
* labeler codes
* product codes
* package codes
* proprietary names
* nonproprietary names
* dosage forms
* routes
* marketing categories
* package descriptions
* start/end marketing dates
* labeler/manufacturer names

## What it can replace

It can replace most synthetic drug-master generation.

You should not invent NDCs unless you need fictional examples for demos. For modeling and pipeline testing, real NDC structure is better.

## Caveat

NDC data changes, can have package-level complexity, and is not enough by itself to define rebate-contract product families. You still need to create or infer brand-family groupings.

---

# 5. FDA Orange Book

FDA's Orange Book downloadable data files include product, patent, and exclusivity files. The Products file includes active ingredient, dosage form/route, trade name, applicant, strength, NDA/ANDA type, application number, therapeutic equivalence code, approval date, RLD, reference standard, and product type. ([U.S. Food and Drug Administration][6])

## How it helps

Use it for:

* brand/generic classification
* NDA versus ANDA
* reference listed drug
* reference standard
* therapeutic equivalence codes
* approval dates
* applicant/manufacturer enrichment
* generic competition context

## What it can replace

It can replace synthetic generation of:

* approval dates
* NDA/ANDA status
* generic-equivalence relationships
* reference-product relationships
* product maturity / launch-age features

## Caveat

Orange Book does not give you NDC-level utilization or commercial rebate terms.

---

# 6. RxNorm

RxNorm provides normalized drug names and drug identifiers. NLM says RxNorm files are pipe-delimited Rich Release Format files, and the current prescribable content release is available without a license. ([National Library of Medicine][7])

## How it helps

Use it for:

* normalized drug names
* ingredient mapping
* branded drug concepts
* clinical drug concepts
* strength/form mappings
* deduplication across names
* mapping NDC-like product references into normalized drug concepts, depending on the release/source fields available

## What it can replace

It can replace synthetic vocabulary mapping.

This is useful when you want features like:

```text
ingredient
brand_name
clinical_drug_component
dose_form
strength
```

## Caveat

RxNorm is a clinical vocabulary, not a rebate-contract hierarchy. It will not tell you how a PBM or manufacturer contract groups products.

---

# 7. CMS NADAC

NADAC is extremely useful for price realism. CMS says NADAC data and comparison data are updated weekly, with monthly postings that include the previous month's survey findings and weekly price changes. ([Medicaid][8])

## How it helps

Use it for:

* acquisition-cost benchmarks
* drug price trends
* generic price volatility
* cost-per-unit realism
* gross-cost simulation
* outlier detection features

## What it can replace

It can replace synthetic acquisition-cost generation.

For example, instead of randomly assigning unit cost, you can use:

```text
synthetic ingredient cost ≈ NADAC × units
```

Then add plan/payment noise.

## Caveat

NADAC is not WAC, AWP, commercial allowed amount, or rebate basis. It is a pharmacy acquisition-cost benchmark, so it is useful for realism but not a direct rebate calculation input unless your synthetic contract design uses it.

---

# 8. CMS ASP pricing files and NDC-HCPCS crosswalks

For medical-benefit drugs, this is one of the best public data sources.

CMS ASP pricing files include quarterly payment limit files, NDC-HCPCS crosswalks, and historical data. ([CMS][9]) CMS states that Medicare pays most separately payable Part B drugs using ASP methodology, generally ASP plus 6%, and publishes payment amounts quarterly. ([CMS][10])

## How it helps

Use it for:

* Part B drug pricing
* HCPCS-to-NDC mapping
* injectable/infusion drug simulation
* unit conversion testing
* medical-benefit rebate leakage scenarios
* J-code/NDC crosswalk features

## What it can replace

It can replace a lot of synthetic generation for medical-benefit drug logic.

Especially useful for these anomaly scenarios:

* HCPCS-to-NDC unit mismatch
* J-code claims missing NDC detail
* medical-benefit drug excluded from rebate invoicing
* Part B drug price benchmark outliers

## Caveat

Commercial medical-benefit rebate arrangements still are not public.

---

# 9. Medicare Part D manufacturer rebate summary reports

CMS has a Medicare Part D Manufacturer Summary Rebate Report area under Medicare & Medicaid Spending by Drug. ([CMS Data][11]) This can provide some aggregate rebate context, but it is not a substitute for product-level commercial rebate contracts.

## How it helps

Use it for:

* aggregate calibration
* sanity checks on broad rebate levels
* policy-level context
* benchmarking high-level rebate magnitudes

## What it cannot do

It generally will not give you the claim/product/client/contract-level rebate detail needed for anomaly detection.

So it may help with **calibration**, but not with **model labels**.

---

# What public data can let you skip

You can skip synthetic generation for these components:

## 1. Drug master backbone

Use:

* FDA NDC Directory
* FDA Orange Book
* RxNorm

Synthetic generation still needed for:

* rebate brand-family grouping
* PBM-specific product grouping
* contract product baskets
* client-specific coverage grouping

## 2. Utilization distributions

Use:

* Medicaid SDUD
* Medicare Part D Spending
* Medicare Part D Prescriber data

Synthetic generation still needed for:

* claim-level member IDs
* group/client IDs
* reversals/adjustments
* commercial plan structure
* paid/rejected claim lifecycle
* late-arriving claims

## 3. Formulary structure

Use:

* CMS Part D formulary files

Synthetic generation still needed for:

* commercial formulary equivalents
* employer-specific overrides
* PBM-specific preferred/non-preferred rebate logic
* custom rebate tiers

## 4. Price/cost benchmarks

Use:

* NADAC
* ASP pricing files
* possibly external WAC/AWP data if licensed

Synthetic generation still needed for:

* commercial allowed amount
* PBM spread
* plan-paid / patient-pay split
* gross-to-net economics
* rebate basis and rate

## 5. Medical drug crosswalks

Use:

* CMS ASP NDC-HCPCS crosswalks

Synthetic generation still needed for:

* commercial medical-benefit claims
* NDC capture quality
* medical rebate eligibility
* unit conversion errors
* invoice/payment disputes

---

# What public data cannot replace

This is the hard line.

Public datasets will not let you skip synthetic generation for:

1. **Commercial rebate contracts**

   * per-script rebate guarantees
   * percentage-of-WAC rebates
   * market-share tiers
   * exclusivity terms
   * formulary-position requirements
   * admin fees
   * PBM spread/pass-through logic

2. **Actual rebate invoices**

   * manufacturer invoice lines
   * PBM invoice files
   * client-level rebate allocations
   * true-up files

3. **Actual paid rebate amounts**

   * payment timing
   * disputed amounts
   * write-offs
   * recoveries

4. **Confirmed leakage labels**

   * true missing rebates
   * recoverability
   * analyst review decisions
   * audit outcomes
   * dollars recovered

5. **Commercial claim-level data**

   * member-level utilization
   * employer/client mapping
   * reversal/adjustment lifecycle
   * pharmacy channel carve-outs
   * COB and exclusion logic

So the answer is: **public data can reduce synthetic data generation by maybe 40–70% for realism, but not for the actual rebate-recovery truth layer.**

---

# Recommended hybrid approach

The best design is:

```text
Public drug data
+ public utilization data
+ public formulary data
+ public price benchmarks
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

## Concrete example

Use public data for the base:

```text
NDC universe: FDA NDC Directory
drug attributes: Orange Book + RxNorm
utilization: Medicaid SDUD or Medicare Part D Spending
formulary features: CMS Part D formulary files
price benchmark: NADAC / ASP
```

Then synthesize:

```text
commercial groups
PBM contracts
rebate rates
guarantees
invoice files
payment files
disputes
recoverability labels
```

That gives you realistic data without pretending public datasets contain private rebate economics.

---

# Best public-data-backed simulation table

A strong starting table would be:

```text
NDC × drug_name × manufacturer/labeler × brand/generic × quarter × state/plan_proxy
```

With columns sourced as follows:

| Column                 | Source                            |
| ---------------------- | --------------------------------- |
| NDC                    | FDA NDC Directory / Medicaid SDUD |
| Drug name              | FDA NDC Directory / RxNorm        |
| Ingredient             | RxNorm / Orange Book              |
| Brand/generic          | Orange Book / FDA metadata        |
| Approval date          | Orange Book                       |
| Claim count proxy      | Medicaid SDUD or Part D           |
| Units proxy            | Medicaid SDUD                     |
| Gross cost proxy       | Medicaid SDUD or Part D           |
| Acquisition cost proxy | NADAC                             |
| Formulary tier proxy   | CMS Part D formulary              |
| PA/ST/QL proxy         | CMS Part D formulary              |
| HCPCS mapping          | ASP NDC-HCPCS crosswalk           |
| Expected rebate        | Synthetic                         |
| Actual rebate          | Synthetic                         |
| Anomaly label          | Synthetic                         |
| Recoverable amount     | Synthetic                         |

This lets you skip a lot of fake data generation while preserving the most important property: known anomaly labels.

---

# Bottom line

Public datasets can give you a realistic **drug/utilization/formulary/pricing skeleton**. They cannot give you the private **rebate contract/payment/recovery layer**.

The best move is not to choose between public and synthetic data. Use public data as the base distribution, then synthesize only what is actually unavailable: rebate contracts, invoices, payment behavior, anomalies, and labels.

[1]: https://www.medicaid.gov/medicaid/prescription-drugs/state-drug-utilization-data "State Drug Utilization Data | Medicaid"
[2]: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug?utm_source=chatgpt.com "Medicare Part D Prescribers by Provider & Drug Data"
[3]: https://www.datalumos.org/datalumos/project/227922/version/V1/view?utm_source=chatgpt.com "Medicare Part D Spending by Drug"
[4]: https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information?utm_source=chatgpt.com "Monthly Medicare Drug Plan & Pharmacy Network Data"
[5]: https://catalog.data.gov/dataset/quarterly-prescription-drug-plan-formulary-pharmacy-network-and-pricing-information?utm_source=chatgpt.com "Quarterly Prescription Drug Plan Formulary, Pharmacy ..."
[6]: https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files "Orange Book Data Files | FDA"
[7]: https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html "RxNorm Files"
[8]: https://www.medicaid.gov/medicaid/nadac "National Average Drug Acquisition Cost | Medicaid"
[9]: https://www.cms.gov/medicare/payment/part-b-drugs/asp-pricing-files?utm_source=chatgpt.com "ASP Pricing Files"
[10]: https://www.cms.gov/medicare/payment/fee-for-service-providers/part-b-drugs/average-drug-sales-price?utm_source=chatgpt.com "Medicare Part B Drug Average Sales Price"
[11]: https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug?utm_source=chatgpt.com "Medicare & Medicaid Spending by Drug"
