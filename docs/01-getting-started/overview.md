# Rx Rebate Leakage Detection: Overview

## What is rebate recovery?

In commercial health insurance, manufacturer rebates are typically retrospective payments tied to formulary placement, product utilization, market-basket performance, and contract terms. These rebates represent a significant revenue stream for health plans, but leakage—where a plan doesn't receive rebates it's entitled to—is a widespread problem.

Rebate leakage often shows up as **exceptions**:

* A high-rebate brand drug has claims but no corresponding rebate.
* A product's rebate amount suddenly drops despite stable utilization.
* NDCs are misclassified, excluded, or rolled up incorrectly.
* Units, days supply, or package size causes underbilling.
* Formulary tier/preferred status is wrong for a claim period.
* Specialty, mail, retail, 340B, government-program, or COB-excluded claims are incorrectly included or excluded.
* PBM invoice guarantees do not reconcile to claim-level expected rebates.
* Manufacturer dispute patterns create persistent under-collection.

## Why anomaly detection?

The analytical strategy is straightforward: **estimate expected rebate dollars, compare to actual rebate dollars, rank suspicious gaps by recoverability, and route the highest-value cases for audit or contract review.**

Anomaly detection helps because:

1. **Leakage is structural** — It occurs in patterns across claim, product, contract, and process layers, not randomly.
2. **Business relevance** — Not all anomalies are recoverable. The model must rank by expected dollar recovery, not just statistical weirdness.
3. **Auditability** — Rebate analysts and manufacturers need explanations, not black-box scores.
4. **Scale** — Manual review of millions of claims and thousands of NDC-client-quarter combinations requires automation.

## Who this guide is for

- **Finance leaders**: Understanding how to identify and recover manufacturer rebates
- **Data engineers**: Building the data infrastructure and synthetic datasets
- **ML/analytics engineers**: Training and deploying anomaly detection models
- **Rebate analysts**: Using the models to prioritize audit work
- **Compliance teams**: Ensuring the process meets regulatory and governance standards

## Document structure

This documentation is organized into six sections:

1. **Getting Started** — Business context and quick-start reference
2. **Data Architecture** — Data models, sources, quality controls, and synthetic generation
3. **Modeling** — Feature engineering, algorithms, and training strategies
4. **Implementation** — Deployment, dashboards, and governance
5. **Common Patterns** — Typical anomalies and best practices
6. **Reference** — Python packages and key definitions

Start with [business-context.md](business-context.md) to understand the problem domain, then move to [quick-start.md](quick-start.md) for a high-level summary of the recommended first model.
