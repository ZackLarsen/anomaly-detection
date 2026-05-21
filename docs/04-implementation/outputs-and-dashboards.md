# Outputs and Dashboards

Create three deliverables.

## 1. Executive dashboard

For C-suite and finance leadership.

**Key metrics:**

* Total estimated leakage (this month, YTD, trend)
* Validated leakage (amount confirmed by analysts)
* Recovered dollars (actual money recovered)
* Recovery rate (recovered / identified)
* Top manufacturers by leakage
* Top clients/groups by leakage
* Top drugs by leakage
* Top root causes
* Aging by quarter (how much is >6 months old)
* Audit-window risk (how much expires soon)

**Visualization:**

```
╔════════════════════════════════════════════════════════════════════════════╗
║                    RX REBATE RECOVERY DASHBOARD                            ║
║                           Executive Summary                                 ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  FINANCIAL IMPACT                                                            ║
║  ┌────────────────────────────────────────────────────────────────────┐    ║
║  │ Estimated Leakage: $47.3M      │  Recovered This Year:  $12.8M      │    ║
║  │ Validated Leakage:  $18.9M     │  Net Recovery (after cost): $10.2M │    ║
║  │ Pending Disputes:   $9.4M      │  YTD Recovery Rate: 68%             │    ║
║  └────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  TRENDS (Last 12 months)                                                     ║
║  ┌────────────────────────────────────────────────────────────────────┐    ║
║  │ Est. Leakage (M)                                                     │    ║
║  │ 50│                                              ┏━━┓                │    ║
║  │ 40│            ┏━━━┓  ┏━━━┓  ┏━━┓   ┏━━┓         ┃  ┃              │    ║
║  │ 30│   ┏━━━┓    ┃   ┃  ┃   ┃  ┃ ┃   ┃ ┃        ┏━┛  ┗━┓            │    ║
║  │ 20│   ┃   ┃━━━━┛   ┗━━┛   ┗━━━┛ ┗━━━ ┃ ┗━━━━━━┛      ┗━          │    ║
║  │ 10│   ┃                              ┃                            │    ║
║  │  0└───┴─────────────────────────────┴───────────────────────────┘    ║
║  │    Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec                     │    ║
║  └────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  TOP MANUFACTURERS                    TOP ROOT CAUSES                       ║
║  ┌──────────────────────────┐       ┌──────────────────────────┐          ║
║  │ Mfr A         $12.3M     │       │ Missing NDC Mapping $8.2M │          ║
║  │ Mfr B          $9.1M     │       │ Low Realization $7.1M     │          ║
║  │ Mfr C          $7.8M     │       │ Unit Conversion $6.3M     │          ║
║  │ Mfr D          $6.4M     │       │ Guarantee Shortfall $5.8M │          ║
║  │ Mfr E          $5.2M     │       │ Specialty Omission $4.1M  │          ║
║  └──────────────────────────┘       └──────────────────────────┘          ║
║                                                                              ║
║  AUDIT WINDOW RISK                                                           ║
║  ┌────────────────────────────────────────────────────────────────────┐    ║
║  │ Expires in < 1 month:    $3.2M  (ACTION: urgent)                    │    ║
║  │ Expires in 1–3 months:   $8.1M  (ACTION: high priority)              │    ║
║  │ Expires in 3–6 months:  $15.7M  (ACTION: scheduled)                  │    ║
║  │ Safe (> 6 months):      $20.3M  (ACTION: normal queue)               │    ║
║  └────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚════════════════════════════════════════════════════════════════════════════╝
```

## 2. Analyst workbench

For rebate analysts reviewing cases.

**Each case should include:**

* Drug (brand, NDC, therapeutic class)
* Client/group
* Quarter
* Expected rebate (calculated from contract)
* Actual rebate (from invoice)
* Gap (expected - actual)
* Reason codes (missing rebate, low realization, etc.)
* Supporting claim count
* Contract rule applied
* Sample invoice line (if any)
* Payment/dispute status
* Recommended action
* Priority score
* Confidence score

**Example workbench row:**

```
Case ID | NDC      | Brand X | Mfr A | Group | Q | Expected | Actual | Gap    | Reasons           | Actions | Priority
--------|----------|---------|-------|-------|---|----------|--------|--------|-------------------|---------|----------
47362   | 12345678 | Brand X | Mfr A | G001  | 2 | $420K    | $95K   | $325K  | Missing rebate    | Dispute | 98%
        |          |         |       |       |   |          |        |        | Low realization   |         |
        |          |         |       |       |   |          |        |        | (23% vs 92%)      |         |
```

**Create in:** Excel, web app, or database-backed tool

**Features:**

* Sort/filter by priority, manufacturer, client, reason code
* One-click dispute template generation
* Case comment/history tracking
* Bulk outcome submission
* Graphical breakdown of gap (by claim, by channel, etc.)

## 3. Data quality dashboard

Track data health metrics monthly.

**Metrics:**

* Missing NDC rate (% of claims without valid NDC)
* Missing contract rate (% of claims without matching contract)
* Missing formulary rate (% of claims without formulary status)
* Invoice match rate (% of claims found in invoice)
* Payment match rate (% of invoices with payment record)
* New unmapped NDCs (count of new products not yet in contract system)
* Reversal mismatch rate (% of reversals without matching original claim)
* Unit conversion exceptions (count of possible unit mismatches)
* Days supply outliers (count of implausible days-supply values)
* Quantity outliers (count of implausible quantity values)

**Alert thresholds:**

```
METRIC                           | YELLOW THRESHOLD | RED THRESHOLD
---------------------------------|------------------|---------------
Missing NDC rate                 |    > 3%          |    > 5%
Missing contract rate            |    > 5%          |   > 10%
Missing formulary rate           |    > 2%          |    > 5%
Invoice match rate               |   < 95%          |   < 90%
Payment match rate               |   < 95%          |   < 90%
New unmapped NDCs (per month)    |   > 50           |   > 100
Reversal mismatch rate           |    > 1%          |    > 2%
Unit conversion exceptions       |   > 20           |   > 50
```

When a metric hits yellow, investigate. When it hits red, stop production reporting and fix.

**Dashboard visualization:**

```
╔════════════════════════════════════════════════════════════════════╗
║                  DATA QUALITY DASHBOARD                            ║
║                      April 2025 (Latest)                           ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║  COMPLETENESS METRICS                                              ║
║  ┌─────────────────────────────────────────────────────┐          ║
║  │ Missing NDC rate         1.2% ✓  (Threshold: 3%)     │          ║
║  │ Missing contract rate    2.8% ✓  (Threshold: 5%)     │          ║
║  │ Missing formulary rate   0.8% ✓  (Threshold: 2%)     │          ║
║  │ Invoice match rate      97.3% ✓  (Threshold: 95%)    │          ║
║  │ Payment match rate      96.8% ✓  (Threshold: 95%)    │          ║
║  └─────────────────────────────────────────────────────┘          ║
║                                                                     ║
║  DATA QUALITY ISSUES                                               ║
║  ┌─────────────────────────────────────────────────────┐          ║
║  │ New unmapped NDCs           28 ✓  (Threshold: 50)   │          ║
║  │ Reversal mismatch rate    0.3% ✓  (Threshold: 1%)   │          ║
║  │ Unit conversion exceptions 12 ✓  (Threshold: 20)   │          ║
║  │ Days supply outliers       43 ✓  (Threshold: 100)   │          ║
║  │ Quantity outliers          67 ✓  (Threshold: 200)   │          ║
║  └─────────────────────────────────────────────────────┘          ║
║                                                                     ║
║  TREND (Last 6 months)                                             ║
║  ┌─────────────────────────────────────────────────────┐          ║
║  │ Missing NDC Rate (%)                                  │          ║
║  │ 5 │     ╱───────────╲                                │          ║
║  │ 4 │    ╱             ╲                               │          ║
║  │ 3 │───╱               ╲───                           │          ║
║  │ 2 │  ╱                 ╲  ╲───                        │          ║
║  │ 1 │ ╱                   ╲    ╲─ 1.2%                  │          ║
║  │ 0 └──────────────────────────────────────────────────│          ║
║  │    Nov  Dec  Jan  Feb  Mar  Apr                       │          ║
║  └─────────────────────────────────────────────────────┘          ║
║                                                                     ║
║  ACTIONS NEEDED                                                     ║
║  ┌─────────────────────────────────────────────────────┐          ║
║  │ ✓ All metrics within acceptable range                │          ║
║  │ ✓ No critical issues detected                        │          ║
║  │ ℹ Monthly trend: New unmapped NDCs stable             │          ║
║  └─────────────────────────────────────────────────────┘          ║
║                                                                     ║
╚════════════════════════════════════════════════════════════════════╝
```

## Implementation

* **Executive dashboard**: Tableau, PowerBI, or Looker connected to data warehouse
* **Analyst workbench**: Custom web app (FastAPI/React) or Salesforce/similar CRM
* **Data quality dashboard**: Auto-updated spreadsheet or real-time database system

Update dashboards daily or weekly, not just monthly.
