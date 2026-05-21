# Recommended Model Architecture

Use a hybrid architecture with five distinct layers. Each layer serves a specific purpose.

## Layer 1: Reconciliation engine

**Purpose:** Calculate expected versus actual rebate.

**Outputs:**

* Expected rebate (from contracts and claim utilization)
* Actual rebate (from invoice/payment data)
* Difference
* Eligibility status
* Contract rule matched
* Invoice matched
* Payment matched
* Rebate realization ratio

**Implementation:** SQL or Python, fully deterministic

**Key principle:** This layer should be **auditable and reproducible**. Every rebate gap should be explainable back to a specific claim, contract rule, and invoice line.

**Example:**

```sql
CREATE TABLE expected_rebate AS
SELECT
    c.claim_id,
    c.ndc11,
    c.group_id,
    c.fill_date,
    k.rebate_basis,
    k.rebate_rate,
    CASE
        WHEN k.rebate_basis = 'PER_30_DAY_SCRIPT'
            THEN (c.days_supply / 30.0) * k.rebate_rate
        WHEN k.rebate_basis = 'PERCENT_GROSS_COST'
            THEN c.gross_cost * k.rebate_rate
        WHEN k.rebate_basis = 'PER_UNIT'
            THEN c.quantity * k.rebate_rate
        ELSE NULL
    END AS expected_rebate
FROM pharmacy_claims c
JOIN drug_master d
  ON c.ndc11 = d.ndc11 AND c.fill_date BETWEEN d.eff_date AND d.end_date
LEFT JOIN rebate_contract_terms k
  ON d.brand_family_id = k.brand_family_id
 AND c.group_id = k.group_id
 AND c.fill_date BETWEEN k.eff_date AND k.end_date
WHERE c.claim_status = 'PAID'
```

## Layer 2: Rules engine

**Purpose:** Catch known leakage patterns.

**Examples:**

* Missing invoice line
* Expected rebate > 0 but paid rebate = 0
* Actual/expected < threshold
* New NDC missing from contract map
* Rebate guarantee not met
* Abnormal dispute/write-off rate
* Inactive NDC on claim date
* Unit mismatch

**Implementation:** Configurable rules (SQL or Python)

**Key principle:** Every rule should have a business owner and clear documentation of why it exists.

```python
class RulesEngine:
    def __init__(self, config):
        self.rules = config["rules"]
    
    def apply(self, data):
        flags = {}
        for rule_name, rule_config in self.rules.items():
            mask = eval(rule_config["condition"])
            flags[rule_name] = mask
        return flags
```

## Layer 3: Statistical anomaly detection

**Purpose:** Detect unusual changes and peer deviations.

**Examples:**

* Rebate per script dropped 70% QoQ
* NDC yield is below peer-class 5th percentile
* Manufacturer dispute rate is 4 MADs above normal
* Client PMPM rebate is below guarantee-adjusted expectation

**Implementation:** Rolling z-scores, seasonal decomposition, peer comparison

**Key principle:** Each statistical metric should have clear interpretation.

```python
class StatisticalDetector:
    def detect_qoq_drops(self, data, threshold=-0.5):
        data = data.sort_values(["ndc11", "quarter"])
        data["rebate_change"] = (
            data.groupby("ndc11")["rebate_per_script"]
            .pct_change()
        )
        return data["rebate_change"] < threshold
    
    def detect_peer_outliers(self, data, group_col, metric_col, z_threshold=3.0):
        data["peer_z_score"] = (
            data.groupby(group_col)[metric_col]
            .transform(lambda x: np.abs(
                (x - x.mean()) / x.std()
            ))
        )
        return data["peer_z_score"] > z_threshold
```

## Layer 4: ML anomaly detection

**Purpose:** Detect multidimensional anomalies missed by rules.

**Use:**

* Isolation Forest
* PyOD ensemble
* Autoencoder if justified
* Clustering residuals
* Time-series residuals

**Implementation:**

- Aggregate data to appropriate grain (NDC × client × quarter recommended)
- Engineer features from Layer 1–3 outputs
- Train on "normal" history (exclude known bad periods)
- Score new observations
- Calibrate anomaly scores to business-friendly thresholds

**Key principle:** ML should enhance, not replace, earlier layers. A low-probability anomaly detected by multiple rules should outrank a high-probability anomaly detected by ML alone.

```python
class MLDetector:
    def __init__(self, n_estimators=500, contamination=0.02):
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=42
        )
    
    def train(self, X_train):
        self.model.fit(X_train)
    
    def score(self, X):
        # Return anomaly score (higher = more anomalous)
        return -self.model.decision_function(X)
```

## Layer 5: Prioritization model

**Purpose:** Rank anomalies by expected recovery value.

**Formula:**

```python
priority_score = (
    anomaly_probability
    × estimated_rebate_gap
    × recoverability_probability
    × confidence_score
)
```

**Business rules to apply:**

* Minimum dollar threshold (e.g., only flag gaps > $5,000)
* Contract audit window (e.g., only recoverable within 2 years)
* Manufacturer dispute deadline
* Client materiality threshold
* Data completeness score
* Legal/compliance sensitivity

**Implementation:**

```python
class Prioritizer:
    def score(self, anomalies):
        score = (
            anomalies["rule_flag_count"] * 0.3
            + anomalies["ml_score"] * 0.2
            + np.log1p(anomalies["rebate_gap"]) * 0.5
        )
        
        # Apply business rule filters
        score[anomalies["rebate_gap"] < 5000] = -999
        score[anomalies["audit_window_expired"]] = -999
        
        return score
```

## Full pipeline diagram

```
┌──────────────────────┐
│  Pharmacy Claims     │
│  Drug Master         │
│  Contracts           │
│  Invoices/Payments   │
└──────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Layer 1: Reconciliation Engine           │
│  Calculate: expected_rebate, actual_rebate│
│            rebate_gap, rebate_realization │
└──────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Layer 2: Rules Engine                   │
│  Apply: Missing rebate, low realization,  │
│         new NDC unmapped, etc.           │
│  Output: flag_count, flag_types          │
└──────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Layer 3: Statistical Detection          │
│  Apply: QoQ drops, peer outliers,        │
│         rolling baselines                │
│  Output: statistical_anomaly_score       │
└──────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Layer 4: ML Anomaly Detection           │
│  Apply: Isolation Forest on multi-dim    │
│         features                        │
│  Output: ml_anomaly_score                │
└──────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Layer 5: Prioritization                 │
│  Combine all signals with business rules │
│  Output: ranked audit queue              │
└──────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Analyst Workbench                       │
│  Top 100 cases with explanations         │
└──────────────────────────────────────────┘
```

## Advantages of layered architecture

1. **Interpretability:** Each layer is explainable independently
2. **Auditability:** Can disable any layer for testing/debugging
3. **Modularity:** Update rules without retraining ML
4. **Reliability:** Multiple detection methods reduce false negatives
5. **Scalability:** Can parallelize across layers
6. **Governance:** Clear responsibility for each layer
