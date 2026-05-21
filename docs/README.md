# Rx Rebate Leakage Detection: Complete Guide

## Overview

This documentation covers the design, implementation, and operation of an anomaly detection system for identifying and recovering manufacturer rebate leakage in health insurance pharmacy claims.

**Goal**: Identify recoverable rebate gaps where a plan should have received more manufacturer rebate dollars than it did.

**Scope**: Commercial rebate contracts, claim-level utilization, rebate invoicing and disputes, and operational controls.

**ROI**: Typical organizations recover $2–5M annually with a 5–10x return on the system investment.

---

## Quick navigation

### I. Getting Started (New to rebate recovery?)
Start here to understand the problem and the approach.

- **[Overview](01-getting-started/overview.md)** — Why rebate recovery matters and who this guide is for
- **[Business Context](01-getting-started/business-context.md)** — The four layers of rebate leakage
- **[Quick Start](01-getting-started/quick-start.md)** — The recommended first model (best approach for most organizations)

**Read time**: 15–20 minutes

### II. Data Architecture (How do I model the data?)
Understand the data model and how to generate or enhance synthetic datasets.

- **[Data Model](02-data/data-model.md)** — Core entities and relationships
- **[Required Data](02-data/required-data.md)** — Complete field specifications for claims, contracts, invoices, etc.
- **[Target Outcomes](02-data/target-outcomes.md)** — What the model should detect
- **[Data Quality Controls](02-data/data-quality-controls.md)** — Pre-modeling validation checks
- **[Synthetic Data Generation](02-data/synthetic-data-generation.md)** — Build synthetic datasets for testing with Claude Code
- **[Public Datasets](02-data/public-datasets.md)** — CMS, FDA, and public sources you can leverage
- **[Hybrid Approach](02-data/hybrid-approach.md)** — Combining public + synthetic data
- **[Validation Testing](02-data/validation-testing.md)** — How to validate synthetic data

**Read time**: 45–60 minutes

### III. Modeling (How do I build the anomaly detection model?)
Feature engineering, algorithms, architecture, and a complete example.

- **[Feature Engineering](03-modeling/feature-engineering.md)** — Utilization, financial, and rebate-specific features
- **[Analytic Grains](03-modeling/analytic-grains.md)** — NDC×client×quarter, brand, manufacturer, contract levels
- **[Algorithms](03-modeling/algorithms.md)** — Rules, statistical detection, Isolation Forest, supervised learning
- **[Model Architecture](03-modeling/model-architecture.md)** — Recommended 5-layer approach
- **[Training Strategy](03-modeling/training-strategy.md)** — Data preparation, validation, segmentation
- **[Evaluation Metrics](03-modeling/evaluation-metrics.md)** — Business metrics, precision@K, dollars captured
- **[Explainability](03-modeling/explainability.md)** — Making results understandable to analysts and manufacturers
- **[Example Workflow](03-modeling/example-workflow.md)** — End-to-end Python example

**Read time**: 90–120 minutes

### IV. Implementation (How do I deploy and operate this?)
Deployment, dashboards, governance, and a 5-phase roadmap.

- **[Deployment Pipeline](04-implementation/deployment-pipeline.md)** — Monthly/quarterly workflow and automation
- **[Outputs and Dashboards](04-implementation/outputs-and-dashboards.md)** — Executive dashboard, analyst workbench, data quality dashboard
- **[Governance and Compliance](04-implementation/governance-and-compliance.md)** — Access control, HIPAA, audit trails, legal review
- **[Implementation Roadmap](04-implementation/roadmap.md)** — 5-phase approach: reconciliation → rules → statistics → ML → operations

**Read time**: 60–90 minutes

### V. Common Patterns (What do anomalies look like?)
Recognizable patterns and best practices.

- **[Anomaly Patterns](05-common-patterns/anomaly-patterns.md)** — 10 common leakage patterns with detection strategies
- **[Best Practices](05-common-patterns/best-practices.md)** — What to do and what NOT to do

**Read time**: 30–45 minutes

### VI. Reference (What are the tools?)

- **[Python Packages](06-reference/python-packages.md)** — Libraries, tools, and recommended stack

**Read time**: 15 minutes

---

## How to use this guide

### If you have 1 hour
Read:
1. [Overview](01-getting-started/overview.md)
2. [Business Context](01-getting-started/business-context.md)
3. [Quick Start](01-getting-started/quick-start.md)

You'll understand the problem and the recommended approach.

### If you're building the data pipeline
Read:
1. [Data Model](02-data/data-model.md)
2. [Required Data](02-data/required-data.md)
3. [Data Quality Controls](02-data/data-quality-controls.md)
4. [Synthetic Data Generation](02-data/synthetic-data-generation.md) or [Public Datasets](02-data/public-datasets.md)

### If you're building the ML model
Read:
1. [Feature Engineering](03-modeling/feature-engineering.md)
2. [Analytic Grains](03-modeling/analytic-grains.md)
3. [Algorithms](03-modeling/algorithms.md)
4. [Model Architecture](03-modeling/model-architecture.md)
5. [Example Workflow](03-modeling/example-workflow.md)

Then reference:
- [Training Strategy](03-modeling/training-strategy.md) (as you train)
- [Evaluation Metrics](03-modeling/evaluation-metrics.md) (as you evaluate)
- [Explainability](03-modeling/explainability.md) (as you explain to analysts)

### If you're deploying to production
Read:
1. [Deployment Pipeline](04-implementation/deployment-pipeline.md)
2. [Implementation Roadmap](04-implementation/roadmap.md)
3. [Governance and Compliance](04-implementation/governance-and-compliance.md)
4. [Outputs and Dashboards](04-implementation/outputs-and-dashboards.md)

Then keep [Anomaly Patterns](05-common-patterns/anomaly-patterns.md) and [Best Practices](05-common-patterns/best-practices.md) handy as reference.

---

## Key concepts

### Four layers of rebate leakage

1. **Claim-level**: Individual claims missing from rebate-eligible population
2. **Product-level**: NDC or brand-level rebate gaps (e.g., sudden yield drops)
3. **Contract-level**: PBM guarantee shortfalls or invoice/payment mismatches
4. **Process-level**: Data quality issues (missing NDCs, unit mismatches, etc.)

### Five-layer model architecture

1. **Reconciliation**: Calculate expected vs. actual rebate
2. **Rules**: Deterministic leakage patterns (missing rebate, low realization, etc.)
3. **Statistical**: Trend and peer-comparison anomalies
4. **ML**: Multi-dimensional outlier detection (Isolation Forest)
5. **Prioritization**: Rank by expected recoverable dollars

### Recommended analytic grain

**NDC × client × quarter**

- Granular enough to catch product-client-specific leakage
- Coarse enough to avoid noise
- Business-aligned with how contracts and invoices are organized

### Quickest path to ROI

1. **Weeks 1–4**: Reconciliation + deterministic rules → **30–50% of recoverable leakage**
2. **Weeks 5–8**: Add statistical anomaly detection → **+15–25% more**
3. **Weeks 9–12**: Add Isolation Forest → **+10–20% more**
4. **Weeks 13–16 and beyond**: Supervised model as labels accumulate → **Dramatic efficiency improvement**

---

## Key metrics to track

**Business metrics:**
- Dollars identified (estimated leakage)
- Dollars recovered (actual money back)
- Recovery rate (recovered / identified)
- Net ROI (recovered - cost)

**Model metrics:**
- Precision@100 (of top 100, % are true leakage; target > 70%)
- Dollars@100 (recovery potential in top 100; target > $500K)
- Analyst agreement (> 80%)
- False-positive cost (< 10% of analyst time)

**Operational metrics:**
- Time to recovery (target < 120 days)
- Dispute success rate (target > 50%)
- Audit window preservation (target > 80%)

---

## Next steps

1. **Start with [Getting Started](01-getting-started/overview.md)** to understand the problem
2. **Read [Quick Start](01-getting-started/quick-start.md)** to decide your approach
3. **Choose your path**:
   - Building data infrastructure? → [Data Architecture](02-data/data-model.md)
   - Building the model? → [Modeling](03-modeling/feature-engineering.md)
   - Deploying? → [Implementation](04-implementation/deployment-pipeline.md)
4. **Refer to [Common Patterns](05-common-patterns/anomaly-patterns.md) and [Best Practices](05-common-patterns/best-practices.md)** as you work

---

## Questions?

Refer to the [Common Patterns](05-common-patterns/anomaly-patterns.md) section for pattern recognition, or [Best Practices](05-common-patterns/best-practices.md) for pitfalls to avoid.

For tools and libraries, see [Python Packages](06-reference/python-packages.md).

---

## Document structure

```
docs/
├── 01-getting-started/
│   ├── overview.md
│   ├── business-context.md
│   └── quick-start.md
│
├── 02-data/
│   ├── data-model.md
│   ├── required-data.md
│   ├── target-outcomes.md
│   ├── data-quality-controls.md
│   ├── synthetic-data-generation.md
│   ├── public-datasets.md
│   ├── hybrid-approach.md
│   └── validation-testing.md
│
├── 03-modeling/
│   ├── feature-engineering.md
│   ├── analytic-grains.md
│   ├── algorithms.md
│   ├── model-architecture.md
│   ├── training-strategy.md
│   ├── evaluation-metrics.md
│   ├── explainability.md
│   └── example-workflow.md
│
├── 04-implementation/
│   ├── deployment-pipeline.md
│   ├── outputs-and-dashboards.md
│   ├── governance-and-compliance.md
│   └── roadmap.md
│
├── 05-common-patterns/
│   ├── anomaly-patterns.md
│   └── best-practices.md
│
├── 06-reference/
│   └── python-packages.md
│
└── README.md (this file)
```

---

**Last updated**: May 2026

**Version**: 1.0

**License**: Internal use only
