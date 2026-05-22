# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a complete guide and implementation framework for building an anomaly detection system to identify and recover manufacturer rebate leakage in health insurance pharmacy claims. The project combines:
- **Extensive documentation** (in `docs/`) covering business context, data modeling, machine learning architecture, and deployment
- **Python implementation examples** using a modern ML stack (scikit-learn, polars, pyod, altair)
- **Synthetic data generation** and validation patterns
- **ROI-focused approach**: Typical organizations recover $2–5M annually with a 5–10x return on system investment

The primary goal is to identify recoverable rebate gaps at multiple levels: claim-level, product-level, contract-level, and process-level.

## Development Environment

### Setup
- **Python version**: 3.12 (specified in `.python-version`)
- **Package manager**: `uv` (modern, fast Python package manager)
- **Virtual environment**: `.venv/` (already initialized)

### Getting Started
```bash
# Activate virtual environment (if not already active)
source .venv/bin/activate

# Install/update dependencies
uv sync

# Run the main entry point
python main.py
```

### Dependencies
Key packages (defined in `pyproject.toml`):
- **polars**: Fast DataFrame library for data manipulation
- **scikit-learn**: ML algorithms (Isolation Forest, etc.)
- **pyod**: Anomaly detection library with various algorithms
- **numpy**: Numerical computing
- **altair**: Declarative visualization

## Documentation Structure

The `docs/` directory is organized into 6 sections, each guiding a different role/task:

```
docs/
├── 01-getting-started/        # New to rebate recovery? Start here (15–20 min)
│   ├── overview.md            # Why rebate recovery matters
│   ├── business-context.md    # Four layers of leakage
│   └── quick-start.md         # Recommended first model
│
├── 02-data/                   # Data architecture and preparation (45–60 min)
│   ├── data-model.md
│   ├── required-data.md       # Field specifications
│   ├── target-outcomes.md     # What the model should detect
│   ├── data-quality-controls.md
│   ├── synthetic-data-generation.md
│   ├── public-datasets.md
│   ├── hybrid-approach.md
│   └── validation-testing.md
│
├── 03-modeling/               # ML architecture and training (90–120 min)
│   ├── feature-engineering.md
│   ├── analytic-grains.md     # Recommended: NDC × client × quarter
│   ├── algorithms.md          # Rules, statistical, Isolation Forest, supervised
│   ├── model-architecture.md  # 5-layer recommended approach
│   ├── training-strategy.md
│   ├── evaluation-metrics.md  # Precision@K, dollars captured
│   ├── explainability.md      # Making results auditable
│   └── example-workflow.md    # End-to-end Python example
│
├── 04-implementation/         # Deployment and operations (60–90 min)
│   ├── deployment-pipeline.md
│   ├── outputs-and-dashboards.md
│   ├── governance-and-compliance.md
│   └── roadmap.md             # 5-phase implementation approach
│
├── 05-common-patterns/        # Reference patterns (30–45 min)
│   ├── anomaly-patterns.md    # 10 common leakage patterns
│   └── best-practices.md
│
└── 06-reference/
    └── python-packages.md     # Tools and recommended stack
```

**Reading paths by role:**
- **Finance/Executive**: Read `01-getting-started/` (1 hour total)
- **Data Engineer**: Read `02-data/` for data pipeline construction
- **ML Engineer**: Read `03-modeling/` for model development; reference `05-common-patterns/` during implementation
- **Deploying to prod**: Read `04-implementation/` in order
- **Analyst**: Reference `05-common-patterns/anomaly-patterns.md` and `best-practices.md`

## Key Architecture Concepts

### Five-Layer Model Architecture
The recommended production system combines:
1. **Reconciliation**: Calculate expected vs. actual rebate
2. **Rules**: Deterministic leakage patterns (hardcoded business rules)
3. **Statistical**: Trend and peer-comparison anomalies
4. **ML**: Multi-dimensional outlier detection (Isolation Forest)
5. **Prioritization**: Rank by expected recoverable dollars

### Recommended Analytic Grain
**NDC (National Drug Code) × Client × Quarter**
- Granular enough to catch product-client-specific leakage
- Coarse enough to avoid noise
- Aligned with how contracts and invoices are organized

### Quickest Path to ROI
1. **Weeks 1–4**: Reconciliation + rules → 30–50% of recoverable leakage
2. **Weeks 5–8**: Add statistical anomaly detection → +15–25%
3. **Weeks 9–12**: Add Isolation Forest → +10–20%
4. **Weeks 13–16+**: Supervised learning with accumulated labels → Efficiency gains

## Git Workflow

- **Main branch**: `main` (production-ready)
- **Feature branches**: Named descriptively (e.g., `feature/synthetic-data-gen`, `research/isolation-forest`)
- **Recent work**: Check commits for understanding of prior decisions and experiments
  - Branches are often named `research/` to indicate exploration and documentation work

## Working with Code

### When Adding Features
- Keep code examples in `docs/03-modeling/example-workflow.md` as the reference implementation
- Use polars for data manipulation (preferred over pandas in this project)
- Follow the five-layer architecture when building new models
- Rank anomalies by **expected recoverable dollars**, not just anomaly score

### When Building Data Pipelines
- Reference `docs/02-data/required-data.md` for field specifications
- Use `docs/02-data/data-quality-controls.md` for validation checks
- Synthetic data generation in `docs/02-data/synthetic-data-generation.md` for test environments

### When Evaluating Models
- Primary metric: **Precision@K** (of top K anomalies, what % are true leakage)
- Secondary: **Dollars@K** (recovery potential in top K results)
- Domain metric: **Analyst agreement** (manual review concordance)
- See `docs/03-modeling/evaluation-metrics.md` for complete metric definitions

## Testing and Validation

- **Data validation**: Use patterns from `docs/02-data/validation-testing.md`
- **Model validation**: Follow guidance in `docs/03-modeling/training-strategy.md`
- **Example end-to-end flow**: See `docs/03-modeling/example-workflow.md`

Currently there are no automated tests, but future implementations should:
- Test data quality checks before modeling
- Validate reconciliation math against expected rebates
- Benchmark model precision@K on holdout test sets
- Validate synthetic data distributions match real data characteristics

## Common Tasks

**Building a synthetic dataset for testing:**
See `docs/02-data/synthetic-data-generation.md`

**Understanding a leakage pattern:**
See `docs/05-common-patterns/anomaly-patterns.md` (covers 10 common patterns)

**Choosing between algorithms:**
See `docs/03-modeling/algorithms.md` (rules, statistical, Isolation Forest, supervised)

**Explaining results to analysts:**
See `docs/03-modeling/explainability.md`

**Deploying monthly:**
See `docs/04-implementation/deployment-pipeline.md`

## Key Metrics to Track

**Business:**
- Dollars identified (estimated leakage)
- Dollars recovered (actual money back)
- Recovery rate (recovered / identified)
- Net ROI

**Model:**
- Precision@100 (target > 70%)
- Dollars@100 (target > $500K)
- Analyst agreement (target > 80%)
- False-positive cost (target < 10% of analyst time)

**Operational:**
- Time to recovery (target < 120 days)
- Dispute success rate (target > 50%)
- Audit window preservation (target > 80%)
