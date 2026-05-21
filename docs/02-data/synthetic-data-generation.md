Claude Code can be used less as a "synthetic data generator" directly and more as an **agentic engineering assistant** that builds, tests, documents, and iterates on a synthetic-data generation framework for the rebate-recovery models. Anthropic describes Claude Code as an agentic coding tool that can read a codebase, edit files, run commands, integrate with developer tools, and work across the terminal, IDE, desktop app, and browser. ([Claude Code][1]) It can also run tests and iterate on failures, which is useful when generating healthcare-style synthetic data because the hard part is not writing random rows; it is preserving realistic constraints. ([Anthropic][2])

## What Claude Code should generate

For the rebate anomaly-detection approaches I described, you want synthetic data at several related tables, not one flat CSV.

A good synthetic dataset would include:

1. **Pharmacy claims**

   * claim ID
   * member ID surrogate
   * group/client ID
   * fill date
   * NDC11
   * quantity
   * days supply
   * channel
   * plan paid
   * gross drug cost
   * claim status
   * reversal/adjustment flags

2. **Drug master**

   * NDC11
   * brand family
   * manufacturer
   * GPI/class
   * specialty flag
   * package size
   * effective dates
   * launch date

3. **Formulary history**

   * client/group
   * NDC or brand family
   * tier
   * preferred flag
   * PA/ST/QL flags
   * effective dates

4. **Rebate contract terms**

   * manufacturer
   * brand family
   * group/client
   * effective dates
   * rebate basis
   * rebate rate
   * minimum guarantee
   * channel exclusions
   * line-of-business exclusions

5. **Rebate invoices**

   * invoice quarter
   * manufacturer
   * NDC/brand
   * client/group
   * invoiced utilization
   * expected rebate
   * actual rebate
   * disputed rebate
   * paid rebate

6. **Injected anomaly labels**

   * anomaly type
   * affected NDC/group/quarter
   * expected dollar impact
   * true/false recoverability flag
   * root cause

The last table is crucial. Synthetic data is only useful for model development if you know the truth.

---

## How Claude Code fits into the workflow

Claude Code can help create a small synthetic-data project like this:

```text
rx-rebate-synthetic/
  pyproject.toml
  README.md
  configs/
    base.yaml
    anomaly_scenarios.yaml
  src/
    rx_synth/
      generate_claims.py
      generate_drugs.py
      generate_formulary.py
      generate_contracts.py
      generate_invoices.py
      inject_anomalies.py
      validate.py
      schema.py
  notebooks/
    01_generate_demo_data.ipynb
    02_train_anomaly_models.ipynb
  tests/
    test_reconciliation.py
    test_anomaly_injection.py
    test_schema_constraints.py
  data/
    synthetic/
```

Claude Code is useful because you can ask it to create or modify all of those files, run the tests, inspect failures, and patch the code. Its GitHub Action can also respond to PRs/issues and implement code changes, which means you could automate review or regeneration tasks in CI. ([GitHub][3])

---

# 1. Use Claude Code to create a synthetic Rx rebate data generator

You might start with a prompt like:

```text
Create a Python package that generates synthetic pharmacy claims, drug master data,
formulary history, rebate contracts, rebate invoices, and anomaly labels for testing
Rx rebate leakage detection models.

Use pandas, numpy, pydantic, and faker. Do not use real PHI. Generate only synthetic
member IDs, group IDs, NDCs, manufacturers, and claims.

The generated data must preserve realistic relationships:
- Claims reference valid NDCs.
- NDCs map to brand families and manufacturers.
- Formulary records are effective-dated.
- Contract terms are effective-dated.
- Rebate invoice lines aggregate from claim-level utilization.
- Actual rebate should normally equal expected rebate within noise.
- Injected anomalies should be labeled.
```

Claude Code can then generate the code, run unit tests, and fix issues. The important part is to make it generate **relationally consistent data**, not just random fields.

---

# 2. Generate baseline "normal" data

The first synthetic dataset should represent the normal world.

For example:

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

n_claims = 500_000
n_ndcs = 300
n_groups = 50

claims = pd.DataFrame({
    "claim_id": [f"C{i:09d}" for i in range(n_claims)],
    "member_id": rng.integers(1, 100_000, n_claims).astype(str),
    "group_id": rng.choice([f"G{i:03d}" for i in range(n_groups)], n_claims),
    "ndc11": rng.choice([f"{i:011d}" for i in range(10000000000, 10000000000 + n_ndcs)], n_claims),
    "fill_date": rng.choice(pd.date_range("2024-01-01", "2025-12-31"), n_claims),
    "days_supply": rng.choice([30, 60, 84, 90], n_claims, p=[0.65, 0.05, 0.10, 0.20]),
    "quantity": rng.gamma(shape=2.0, scale=15.0, size=n_claims).round(2),
    "channel": rng.choice(["retail", "mail", "specialty"], n_claims, p=[0.70, 0.20, 0.10]),
})
```

But Claude Code should be instructed to go further than this. It should create drug-specific and channel-specific distributions:

* Specialty drugs should have higher cost.
* 90-day fills should be more common in mail.
* Specialty drugs should have lower claim volume but higher rebate dollars.
* Brand drugs should usually have rebate contracts.
* Generics should usually have no rebate or lower rebate.

That is what makes the data useful for model testing.

---

# 3. Generate expected rebate logic

Claude Code can build a deterministic rebate calculator.

For synthetic data, you can keep the contract rules simple:

```text
Contract basis options:
- PER_30_DAY_SCRIPT
- PERCENT_GROSS_COST
- PER_UNIT
- PMPM_GUARANTEE
```

Example expected rebate calculation:

```python
def calculate_expected_rebate(row):
    if row["rebate_basis"] == "PER_30_DAY_SCRIPT":
        return row["rebate_rate"] * (row["days_supply"] / 30.0)

    if row["rebate_basis"] == "PERCENT_GROSS_COST":
        return row["rebate_rate"] * row["gross_cost"]

    if row["rebate_basis"] == "PER_UNIT":
        return row["rebate_rate"] * row["quantity"]

    return 0.0
```

In the normal synthetic world:

```python
actual_rebate = expected_rebate * random_noise
```

where the noise is small, for example 95% to 105%.

That baseline is what anomaly models learn as "normal."

---

# 4. Inject realistic rebate-leakage anomalies

This is where Claude Code is especially useful. You can ask it to create reusable scenario functions.

## Scenario A: Missing rebate for eligible claims

```text
For one contracted brand and one quarter, set actual rebate to zero
even though expected rebate is positive.
```

This tests whether the model catches:

* expected rebate > 0
* actual rebate = 0
* material rebate gap

## Scenario B: New NDC not mapped to contract

```text
Create a new NDC under an existing brand family.
Generate claims for it.
Do not include it in the rebate invoice.
Label the missing expected rebate as recoverable leakage.
```

This tests NDC mapping controls.

## Scenario C: Rebate yield collapse

```text
For a high-volume brand, reduce actual rebate by 70% in one quarter
without changing utilization, formulary status, or contract terms.
```

This tests time-series anomaly detection.

## Scenario D: Specialty channel omission

```text
For the same NDC and client, calculate rebates normally for retail claims
but set actual rebates to zero for specialty claims.
```

This tests channel-specific leakage detection.

## Scenario E: Unit conversion error

```text
For an injectable drug, divide expected units by 10 when generating invoice rebates.
Actual rebate becomes exactly 10% of expected.
```

This tests ratio-based anomaly detection.

## Scenario F: Manufacturer dispute spike

```text
Keep invoiced rebates correct, but set paid rebates low because disputed rebates spike.
```

This tests invoice-to-payment reconciliation.

## Scenario G: Guarantee true-up missing

```text
Generate aggregate rebates below a PMPM guarantee, but omit the true-up payment.
```

This tests contract-level recovery.

Claude Code can implement each scenario as a function:

```python
def inject_missing_rebate(invoice_df, labels_df, ndc11, group_id, quarter):
    mask = (
        (invoice_df["ndc11"] == ndc11)
        & (invoice_df["group_id"] == group_id)
        & (invoice_df["quarter"] == quarter)
    )

    original_actual = invoice_df.loc[mask, "actual_rebate"].copy()
    invoice_df.loc[mask, "actual_rebate"] = 0.0

    labels = pd.DataFrame({
        "entity_type": ["ndc_group_quarter"],
        "ndc11": [ndc11],
        "group_id": [group_id],
        "quarter": [quarter],
        "anomaly_type": ["MISSING_REBATE"],
        "recoverable": [True],
        "estimated_impact": [original_actual.sum()],
    })

    labels_df = pd.concat([labels_df, labels], ignore_index=True)
    return invoice_df, labels_df
```

---

# 5. Use Claude Code to create validation tests

Bad synthetic data will mislead you. Claude Code should generate tests that prove the data makes sense.

Examples:

```python
def test_all_claim_ndcs_exist_in_drug_master(claims, drugs):
    assert set(claims["ndc11"]).issubset(set(drugs["ndc11"]))

def test_expected_rebate_non_negative(invoice):
    assert (invoice["expected_rebate"] >= 0).all()

def test_missing_rebate_anomalies_have_positive_expected_rebate(invoice, labels):
    missing = labels[labels["anomaly_type"] == "MISSING_REBATE"]
    for _, label in missing.iterrows():
        row = invoice[
            (invoice["ndc11"] == label["ndc11"])
            & (invoice["group_id"] == label["group_id"])
            & (invoice["quarter"] == label["quarter"])
        ]
        assert row["expected_rebate"].sum() > 0
        assert row["actual_rebate"].sum() == 0
```

This is a good Claude Code task because it can write the tests, run them, inspect failures, and patch the generator until the synthetic data is internally consistent.

---

# 6. Use Claude Code to generate experiment notebooks

After creating synthetic data, ask Claude Code to create notebooks or scripts that run the anomaly methods.

For example:

```text
Create a notebook that:
1. Loads the synthetic claims, contracts, invoices, and labels.
2. Aggregates data to NDC × group × quarter × channel.
3. Engineers rebate realization, rebate gap, rebate per 30-day script, QoQ change,
   missing contract rate, and missing invoice flags.
4. Trains Isolation Forest.
5. Applies rule-based leakage flags.
6. Evaluates precision@25, precision@100, recall, and dollars captured in top K.
7. Produces a ranked audit queue.
```

Claude Code can then produce code similar to:

```python
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

features = [
    "claim_count",
    "script_30_equiv",
    "gross_cost",
    "expected_rebate",
    "actual_rebate",
    "rebate_gap",
    "rebate_realization",
    "rebate_per_30",
    "qoq_rebate_realization_change",
    "missing_invoice_flag",
]

X = agg[features]

pipe = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", RobustScaler()),
    ("model", IsolationForest(
        n_estimators=300,
        contamination=0.02,
        random_state=42
    ))
])

pipe.fit(X)
agg["anomaly_score"] = -pipe.decision_function(X)
agg["is_anomaly"] = pipe.predict(X) == -1
```

Then evaluate against the synthetic labels:

```python
def precision_at_k(scored, label_col, k):
    top = scored.sort_values("priority_score", ascending=False).head(k)
    return top[label_col].mean()

def dollars_captured_at_k(scored, k):
    top = scored.sort_values("priority_score", ascending=False).head(k)
    return top.loc[top["is_true_anomaly"], "estimated_impact"].sum()
```

---

# 7. Use Claude Code custom commands for repeatable synthetic-data workflows

Claude Code supports custom slash commands through files, and Anthropic's docs say custom commands can be defined as markdown files; the newer recommended format is under `.claude/skills/<name>/SKILL.md`. ([Claude Code][4])

You could create commands such as:

```text
/generate-rx-synth
/evaluate-rebate-anomaly-model
/inject-rebate-scenario
/rebuild-audit-queue
```

Example `.claude/skills/generate-rx-synth/SKILL.md`:

```markdown
Generate or update the synthetic Rx rebate dataset.

Steps:
1. Read configs/base.yaml and configs/anomaly_scenarios.yaml.
2. Generate pharmacy claims, drug master, formulary, contract, invoice, payment, and label files.
3. Ensure all generated data is synthetic and contains no PHI.
4. Run pytest.
5. Run the reconciliation script.
6. Summarize row counts, anomaly counts, and validation results.
```

Then a user could run:

```bash
claude "/generate-rx-synth with 2 million claims, 100 groups, 500 NDCs, and 25 injected anomalies"
```

This turns synthetic-data generation into a reproducible development workflow rather than a one-off script.

---

# 8. Use Claude Code in CI/CD

Claude Code's GitHub Action can answer questions, review code, and implement changes on PRs/issues; the repository says it can be activated through workflow context such as `@claude` mentions, issue assignments, or explicit automation prompts. ([GitHub][3])

For this use case, you could use it to:

* review synthetic-data generator changes
* check whether anomaly scenarios are correctly labeled
* update documentation when schemas change
* add tests for new leakage patterns
* regenerate demo data on demand
* create pull requests for new scenario modules

Example GitHub issue:

```text
@claude Add a synthetic anomaly scenario for formulary tier mismatch:
- Product is preferred during the claim period.
- Invoice applies non-preferred rebate rate.
- Label the gap as TIER_STATUS_MISMATCH.
- Add tests and update the README.
```

Claude Code can implement that change across the codebase.

---

# 9. What synthetic data should be used for

Synthetic data is good for:

* validating feature engineering
* testing pipeline joins
* developing anomaly logic
* proving models can detect known injected defects
* estimating precision/recall under controlled conditions
* onboarding analysts without exposing PHI or contract data
* building demos
* testing dashboards
* CI regression tests

Synthetic data is weak for:

* estimating actual recoverable dollars
* calibrating real false-positive rates
* learning actual PBM/manufacturer behavior
* replacing contract review
* proving production ROI
* capturing messy real-world edge cases

Tell it like it is: synthetic data helps you build the machinery, but it does not prove the business case by itself.

---

# 10. Best synthetic-data design for this problem

The best design is **simulation with known injected anomalies**, not generic tabular synthesis.

Use this structure:

```text
Normal claims and rebates
        ↓
Contract-aware expected rebate engine
        ↓
Invoice/payment simulator
        ↓
Controlled anomaly injection
        ↓
Ground-truth labels
        ↓
Anomaly model evaluation
```

The synthetic data should preserve:

* drug-to-manufacturer relationships
* NDC-to-brand-family relationships
* effective-dated formulary status
* effective-dated contract rules
* channel-specific behavior
* quarter-based invoicing
* realistic rebate noise
* realistic high-cost specialty skew
* reversal/adjustment behavior
* known injected leakage labels

That is exactly where Claude Code is useful: it can create the generator, tests, scenario library, notebooks, and CI hooks, then keep them synchronized as your rebate-recovery approach evolves.

[1]: https://code.claude.com/docs/en/overview "Overview - Claude Code Docs"
[2]: https://www.anthropic.com/product/claude-code "Claude Code | Anthropic's agentic coding system  \ Anthropic"
[3]: https://github.com/anthropics/claude-code-action "GitHub - anthropics/claude-code-action · GitHub"
[4]: https://code.claude.com/docs/en/agent-sdk/slash-commands "Slash Commands in the SDK - Claude Code Docs"
