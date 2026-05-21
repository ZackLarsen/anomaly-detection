# Evaluation Metrics

Standard ML metrics are not enough. This is the most important part.

## Business evaluation metrics

Use:

* **Dollars identified**: Total estimated leakage surfaced by the model
* **Dollars validated**: Amount confirmed as true leakage by analysts
* **Dollars recovered**: Actual money recovered through audit/disputes
* **Recovery rate**: Recovered / identified
* **False-positive review cost**: Analyst time spent on invalid cases
* **Net recovery after cost**: Recovered dollars minus analyst review cost
* **Time to recovery**: Days from identification to recovery
* **Manufacturer/PBM dispute success rate**: Dispute win rate
* **Percent of anomalies reviewed**: How many cases did analysts review
* **Percent of reviewed anomalies confirmed**: Precision of what we showed analysts
* **Average dollars per confirmed case**: Quality of prioritization
* **Audit-window preservation rate**: Cases recovered before audit deadline expires

**Key metric:**

```text
net_value = recovered_dollars - review_cost - dispute_cost - implementation_cost
```

If net value is negative, the system is not working.

## Model evaluation metrics

If labels exist:

* **Precision at K**: Of top K cases, how many were real leakage
* **Recall at K**: Of all true leakage, what percentage is in top K
* **Average precision**: Area under the precision-recall curve
* **ROC AUC**: Trade-off between true and false positive rates
* **PR AUC**: Precision-recall AUC (more meaningful than ROC for imbalanced data)
* **Lift over random**: How much better than random selection
* **Dollars captured in top K**: Of top K cases, how much money was recovered
* **Dollars captured in top decile**: Of top 10%, how much recovery

**For rebate recovery, precision@K and dollars captured@K matter more than ROC AUC.**

**Example evaluation:**

```python
def evaluate(scored_cases, true_labels):
    """
    Evaluate ranked list of cases against ground truth.
    """
    merged = scored_cases.merge(true_labels, on="case_id")
    merged = merged.sort_values("priority_score", ascending=False)
    
    results = {}
    
    for k in [25, 50, 100, 200]:
        top_k = merged.head(k)
        
        # Precision@K: how many are true
        results[f"precision@{k}"] = top_k["is_true_anomaly"].mean()
        
        # Dollars@K: how much recovery
        results[f"dollars@{k}"] = top_k[top_k["is_true_anomaly"]]["recovered_dollars"].sum()
        
        # Recall@K
        all_true_anomalies = merged["is_true_anomaly"].sum()
        results[f"recall@{k}"] = top_k["is_true_anomaly"].sum() / all_true_anomalies
    
    return results
```

## Unsupervised evaluation

When you do not have labels:

* **Analyst review agreement**: Do multiple analysts agree on same cases?
* **Backtesting against known recoveries**: How many known-good cases does the model catch?
* **Stability across quarters**: Do anomaly patterns make sense over time?
* **Concentration of anomalies**: Are they reasonable by manufacturer/client?
* **Manual case quality score**: Do flagged cases "feel" like leakage to domain experts?
* **Overlap with deterministic rules**: What % are also caught by simple rules?
* **Synthetic anomaly injection**: Can the model catch injected defects?
* **Historical event detection**: Can it retroactively detect known incidents?

### Synthetic anomaly testing

```python
def test_can_detect_missing_rebate():
    """Inject missing rebate and verify detection."""
    # Create synthetic case with:
    # - expected_rebate = $50,000
    # - actual_rebate = $0
    # - claim_count = 500
    
    anomalous_case = pd.DataFrame({
        "ndc11": ["12345678901"],
        "expected_rebate": [50000],
        "actual_rebate": [0],
        "rebate_realization": [0.0],
        "claim_count": [500],
    })
    
    # Score the case
    score = model.score(anomalous_case)
    
    # Should be flagged as high-priority
    assert score[0] > threshold, "Failed to detect missing rebate anomaly"

def test_can_detect_yield_collapse():
    """Inject 70% rebate reduction."""
    normal_history = agg[
        (agg["ndc11"] == "98765432109")
        & (agg["quarter"] < "2025-Q1")
    ]
    
    # Baseline rebate realization
    baseline = normal_history["rebate_realization"].mean()
    
    # Inject anomaly
    anomaly = pd.DataFrame({
        "ndc11": ["98765432109"],
        "quarter": ["2025-Q1"],
        "rebate_realization": [baseline * 0.3],
        "rebate_per_30": [normal_history["rebate_per_30"].mean() * 0.3],
    })
    
    score = model.score(anomaly)
    assert score[0] > threshold, "Failed to detect yield collapse"
```

## Audit-queue evaluation

For each scored case, track:

| Field                 | Meaning                                                  |
| --------------------- | -------------------------------------------------------- |
| model score           | raw anomaly score                                        |
| business rank         | final priority                                           |
| estimated gap         | model-estimated leakage                                  |
| analyst decision      | valid/invalid/needs research                             |
| root cause            | mapping, contract, invoice, payment, dispute, data issue |
| recovery action       | PBM inquiry, manufacturer dispute, internal correction   |
| recovered dollars     | actual money recovered                                   |
| days to resolution    | operational efficiency                                   |
| false-positive reason | why model was wrong                                      |

This feedback loop is what turns anomaly detection into a recovery program.

```python
def track_case_outcomes(case_id, model_score, analyst_decision, recovered):
    """Log case outcome for future model improvement."""
    log = {
        "case_id": case_id,
        "model_score": model_score,
        "analyst_decision": analyst_decision,  # "VALID", "INVALID", "RESEARCH"
        "recovered_dollars": recovered,
        "timestamp": pd.Timestamp.now(),
    }
    outcome_log.append(log)
    
    # Use outcomes to retrain model quarterly
```

## Visualization

Create these charts:

1. **Precision-Recall curve**: Trade-off between precision and recall at different thresholds
2. **Dollars captured vs K**: Cumulative recovery as you review more cases
3. **Anomaly score distribution**: Where does model place normal vs anomalous cases?
4. **Case outcome histogram**: Distribution of analyst decisions
5. **Recovery by manufacturer**: Which manufacturers yield most recovery
6. **Recovery by anomaly type**: Which patterns are most profitable to chase

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 3, figsize=(15, 10))

# Precision-Recall
axes[0, 0].plot(recall, precision)
axes[0, 0].set_title("Precision-Recall Curve")

# Dollars captured
top_k = [10, 25, 50, 100]
dollars = [evaluate(k)["dollars_captured"] for k in top_k]
axes[0, 1].plot(top_k, dollars)
axes[0, 1].set_title("Dollars Captured vs K")

# Score distribution
axes[0, 2].hist(normal_scores, alpha=0.5, label="Normal")
axes[0, 2].hist(anomalous_scores, alpha=0.5, label="Anomalous")
axes[0, 2].set_title("Score Distribution")

# Outcomes
axes[1, 0].bar(["Valid", "Invalid", "Research"], outcome_counts)
axes[1, 0].set_title("Analyst Decisions")

# Recovery by manufacturer
axes[1, 1].barh(manufacturers, recovery_by_mfr)
axes[1, 1].set_title("Recovery by Manufacturer")

# Recovery by anomaly type
axes[1, 2].barh(anomaly_types, recovery_by_type)
axes[1, 2].set_title("Recovery by Anomaly Type")

plt.tight_layout()
plt.savefig("model_evaluation.png")
```

## When to consider the model successful

- [ ] Precision@100 > 70% (at least 70 of top 100 are valid leakage)
- [ ] Dollars@100 > $500K (top 100 cases capture significant recovery)
- [ ] Net recovery positive (recovered dollars exceed review cost)
- [ ] Analyst agreement > 80% (multiple reviewers agree on cases)
- [ ] Synthetic anomaly detection > 90% (catches injected defects)
- [ ] Backtesting catches > 80% of known past incidents
