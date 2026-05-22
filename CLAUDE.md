# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a complete guide and implementation framework for building an anomaly detection system to identify and recover manufacturer rebate leakage in health insurance pharmacy claims. The project combines:
- **Extensive documentation** (in `docs/`) covering business context, data modeling, machine learning architecture, and deployment
- **Python implementation examples** using a modern ML stack (scikit-learn, polars, pyod, altair)
- **Synthetic data generation** and validation patterns

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

## Git Workflow

**Before pushing, always fetch and pull:**
```bash
git fetch origin
git pull origin [branch-name]
```

**Branch naming:**
- **Main branch**: `main` (production-ready)
- **Feature branches**: `feature/[description]` (e.g., `feature/rbf-kernel`)
- **Research branches**: `research/[topic]` (e.g., `research/xgboost-tuning`)
- **Current branch**: `synthetic-data-generation` (complete synthetic data generator)

**Recent work:**
- `858757f` — README files (project overview + data generation guide)
- `57f76b1` — Phase 6 (Jupyter notebooks and CLI)
- `318f580` — Phase 4 (validation module and 174 tests)
- Earlier phases: Schema, generators, anomaly injectors

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

### Automated Test Suite (174 tests, 0.8 seconds)

```bash
pytest tests/                              # Run all tests
pytest tests/test_schema.py -v             # Run specific test file
pytest tests/ --cov=src/synthetic_data_gen # With coverage report
```

**Test files:**
- `test_schema.py` — Pydantic model validation (28 tests)
- `test_claims_generation.py` — Claims generation and distributions (18 tests)
- `test_drug_master.py` — Drug master consistency (13 tests)
- `test_reconciliation.py` — Invoice reconciliation with claims (15 tests)
- `test_anomaly_injection.py` — All 7 anomaly injection functions (37 tests)
- `test_validation.py` — Validation functions (30 tests)
- `test_runner.py` — CLI and orchestration (33 tests)

### Validation Checks

The `validate.py` module provides 13 data quality checks:
- Referential integrity (NDCs, null keys, duplicates)
- Financial constraints (non-negative rebates, paid ≤ actual)
- Date constraints (no future claims)
- Reconciliation (invoice aggregates match claims)
- Anomaly detectability (anomalies have correct characteristics)

Run validation programmatically:
```python
from synthetic_data_gen.validate import run_all_validations
results = run_all_validations(claims, drugs, formulary, contracts, invoices, labels)
```

All validation checks pass on the provided synthetic dataset.

## Common Tasks

### Running the System

**Generate synthetic dataset:**
```bash
python main.py                              # Full dataset with anomalies
python -m synthetic_data_gen generate --seed 999  # Custom seed
python -m synthetic_data_gen generate --no-anomalies  # Baseline only
python -m synthetic_data_gen generate --help       # Show all options
```

**Explore data in Jupyter:**
```bash
jupyter notebook
# Open: notebooks/01_generate_demo_data.ipynb (data exploration)
# Open: notebooks/02_train_anomaly_models.ipynb (model training)
```

**Run tests:**
```bash
pytest tests/ -v                            # All tests
pytest tests/test_anomaly_injection.py -v   # Single test file
```

### Understanding the Code

**Building a synthetic dataset:**
- Use `generate_and_save()` from `src/synthetic_data_gen/runner.py`
- Or manually: `ClaimsGenerator`, `DrugGenerator`, `FormularyGenerator`, `ContractGenerator`, `InvoiceGenerator`
- See `notebooks/02_train_anomaly_models.ipynb` for feature engineering example

**Injecting anomalies:**
- Use `inject_scenario()` from `src/synthetic_data_gen/inject_anomalies.py`
- 7 functions available: missing_rebate, unmapped_ndc, yield_collapse, channel_omission, unit_error, dispute_spike, guarantee_true_up
- Each returns updated invoices, labels, and contracts

**Understanding leakage patterns:**
- See `docs/05-common-patterns/anomaly-patterns.md` (10 common patterns with detection strategies)
- See `notebooks/01_generate_demo_data.ipynb` for visual exploration

**Choosing algorithms:**
- See `docs/03-modeling/algorithms.md` (rules, statistical, Isolation Forest, supervised)
- See `notebooks/02_train_anomaly_models.ipynb` for Isolation Forest example

**Explaining results to analysts:**
- See `docs/03-modeling/explainability.md`
- Notebooks produce audit queues ranked by priority_score (50% ML + 50% rules)

**Deploying monthly:**
- See `docs/04-implementation/deployment-pipeline.md`
- Use `runner.generate_and_save()` to orchestrate full pipeline

## Key Metrics to Track

**System Performance:**
- **Generation time**: ~4 seconds (500K claims)
- **Test suite**: 174 tests in 0.8 seconds
- **Dataset size**: 500K claims, 118K invoices, 7 labeled anomalies

**Model Evaluation (on synthetic data):**
- **Precision@25**: 56%
- **Precision@50**: 56%
- **Recall@100**: 54%
- **Dollars Captured@50**: $647K (68% of labeled impact)

**Target Metrics (when deploying to production):**
- Precision@100 (target > 70%)
- Dollars@100 (target > $500K)
- Analyst agreement (target > 80%)
- False-positive cost (target < 10% of analyst time)
