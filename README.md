# Anomaly Detection for Rx Rebate Recovery

A complete framework for building anomaly detection systems to identify and recover manufacturer rebate leakage in health insurance pharmacy claims.

**Goal:** Identify recoverable rebate gaps where a plan should have received more manufacturer rebate dollars than it did.

**ROI:** Typical organizations recover $2–5M annually with a 5–10x return on system investment.

---

## Quick Start

### 1. Explore the Data

Start with the Jupyter notebooks to understand the synthetic dataset and anomaly detection models:

```bash
# Start Jupyter
jupyter notebook

# Then open:
# - notebooks/01_generate_demo_data.ipynb       (data exploration, visualizations)
# - notebooks/02_train_anomaly_models.ipynb     (model training, evaluation)
```

### 2. Generate Synthetic Data (Optional)

The synthetic data is already generated and ready to use. To regenerate with a different seed or configuration:

```bash
python main.py                                    # Generate full dataset
python -m synthetic_data_gen generate --seed 999 # Custom seed
python -m synthetic_data_gen generate --help      # Show all options
```

See [**data/synthetic/README.md**](data/synthetic/README.md) for detailed data generation instructions.

### 3. Run Tests

```bash
pytest tests/ -v        # Run all 174 tests (0.8 seconds)
pytest tests/ --cov     # Run with coverage report
```

---

## Project Overview

This repository contains:

1. **Documentation** (`docs/`) — Comprehensive guides covering:
   - Business context and four layers of rebate leakage
   - Data modeling and required fields
   - Feature engineering and anomaly detection algorithms
   - Implementation roadmap and deployment strategies
   - Common leakage patterns and best practices

2. **Synthetic Data Generation** (`src/synthetic_data_gen/`) — Python package with:
   - 5 configurable data generators (claims, drugs, formulary, contracts, invoices)
   - 7 realistic anomaly injection scenarios
   - Validation framework ensuring data quality
   - Full test suite (174 tests)
   - CLI for easy dataset generation

3. **Example Notebooks** (`notebooks/`) — Jupyter notebooks demonstrating:
   - Data exploration with interactive visualizations
   - Feature engineering pipeline
   - Anomaly detection model training (Isolation Forest)
   - Evaluation metrics (Precision@K, Dollars@K)
   - Audit queue generation

4. **Configuration** (`configs/`) — YAML files for:
   - Base generation parameters (500K claims, 300 NDCs, 50 groups)
   - 7 anomaly scenarios with injection parameters

---

## What's Included

### Synthetic Dataset

**500K pharmacy claims with ground-truth anomalies:**
- 300 unique drug NDCs
- 50 client/group IDs
- 20 manufacturers
- 118K invoice records (aggregated to NDC × client × quarter)
- 7 injected anomalies with labeled ground truth

**Data files** (in `data/synthetic/`):
- `claims.parquet` — 500K individual pharmacy claims
- `drugs.parquet` — Drug master with brand, manufacturer, specialty flags
- `formulary.parquet` — Formulary tiers and restrictions (70% client-NDC coverage)
- `contracts.parquet` — Rebate contracts with 4 basis types
- `invoices.parquet` — Quarterly rebate invoices with expected/actual amounts
- `anomaly_labels.parquet` — Ground-truth labels for 7 injected anomalies

### Anomaly Types

The system can detect and inject:
1. **Missing Rebate** — Contracted product has zero rebate despite positive utilization
2. **Unmapped NDC** — New product not included in rebate invoice
3. **Rebate Yield Collapse** — Sudden drop in rebate rate without utilization change
4. **Channel Omission** — Rebates missing for specialty/mail channel only
5. **Unit Conversion Error** — Units miscounted/converted in invoice
6. **Dispute Spike** — Manufacturer disputes reduce paid rebates
7. **Guarantee True-up Missing** — PMPM guarantee shortfall unpaid

---

## Development

### Environment Setup

```bash
# Requires Python 3.12+
python --version

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### Project Structure

```
src/synthetic_data_gen/           # Main package
├── schema.py                      # Pydantic models
├── config.py                      # Config loading
├── generate_*.py                  # 5 data generators
├── inject_anomalies.py            # 7 anomaly injectors
├── validate.py                    # Validation framework
├── runner.py                      # Orchestration
└── __main__.py                    # CLI

tests/                             # 174 tests
├── test_schema.py
├── test_claims_generation.py
├── test_drug_master.py
├── test_reconciliation.py
├── test_anomaly_injection.py
├── test_validation.py
└── test_runner.py

notebooks/                         # Example notebooks
├── 01_generate_demo_data.ipynb
└── 02_train_anomaly_models.ipynb

docs/                              # Comprehensive guides (27 markdown files)
└── 01-getting-started/
    ├── overview.md
    ├── business-context.md
    └── quick-start.md
```

See [**CLAUDE.md**](CLAUDE.md) for developer guidance and common tasks.

### Running the System

**Generate synthetic data:**
```bash
python main.py                     # Full dataset with anomalies
python -m synthetic_data_gen generate --no-anomalies  # Baseline only
```

**Explore data:**
```bash
jupyter notebook                   # Open notebooks/ folder
```

**Run tests:**
```bash
pytest tests/                      # Run all tests
pytest tests/test_claims_generation.py -v  # Single test file
```

---

## Key Metrics

**Model Performance (on synthetic data):**
- Precision@25: 56%
- Precision@50: 56%
- Recall@100: 54%
- Dollars Captured@50: $647K (68% of labeled impact)

**System Speed:**
- Dataset generation: ~4 seconds (500K claims)
- Test suite: ~0.8 seconds (174 tests)
- Notebook execution: ~3 minutes (exploration + model training)

---

## Recommended Approach

### Four Layers of Leakage Detection

1. **Reconciliation** (Week 1–2) — Calculate expected vs. actual rebate → 30–50% recovery
2. **Rules** (Week 2–4) — Deterministic leakage patterns → +15–25% recovery
3. **Statistical** (Week 5–8) — Trend and peer anomalies → +10–15% recovery
4. **ML** (Week 9+) — Multi-dimensional outlier detection → Efficiency gains

### Five-Layer Model Architecture

```
Pharmacy Claims
    ↓
Drug Master (NDC → brand, manufacturer, specialty)
    ↓
Formulary & Contracts (tier, preferred status, rebate terms)
    ↓
Expected Rebate Calculation (per contract basis type)
    ↓
Invoice & Payment Data
    ↓
Anomaly Detection (rules + statistical + ML)
    ↓
Audit Queue (ranked by recoverable dollars)
```

---

## Documentation

- **[docs/01-getting-started/](docs/01-getting-started/)** — Business context and overview
- **[docs/02-data/](docs/02-data/)** — Data modeling, required fields, synthetic generation
- **[docs/03-modeling/](docs/03-modeling/)** — Feature engineering, algorithms, evaluation
- **[docs/04-implementation/](docs/04-implementation/)** — Deployment, dashboards, governance
- **[docs/05-common-patterns/](docs/05-common-patterns/)** — 10 leakage patterns and best practices
- **[CLAUDE.md](CLAUDE.md)** — Developer guide with common tasks and commands

---

## Next Steps

1. **Start with notebooks** — `jupyter notebook` → `notebooks/01_generate_demo_data.ipynb`
2. **Understand the domain** — Read `docs/01-getting-started/overview.md`
3. **Explore model training** — Run `notebooks/02_train_anomaly_models.ipynb`
4. **Generate custom data** — `python main.py --seed [YOUR_SEED]`
5. **Build your model** — Modify notebooks or use the generators directly in your code

---

## License

Internal use only.

**Questions?** See [docs/README.md](docs/README.md) for comprehensive documentation.
