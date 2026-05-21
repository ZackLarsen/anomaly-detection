# Algorithms for Rebate Anomaly Detection

Use a layered approach. Start with deterministic rules and reconciliation, then add statistical and ML anomaly detection.

## 1. Deterministic rules

These are not "less advanced." They are usually the highest ROI.

Examples:

```sql
IF expected_rebate > 0 AND actual_rebate IS NULL
THEN missing rebate anomaly

IF actual_rebate / expected_rebate < 0.8
AND expected_rebate > $10,000
THEN high-value under-realization anomaly

IF NDC belongs to contracted brand family
AND NDC launch_date < claim_date
AND NDC not present in rebate invoice
THEN possible unmapped NDC
```

Use rules for:

* Missing invoice lines
* Invalid NDCs
* Eligibility mismatches
* Contract minimum violations
* Guarantee shortfalls
* Reversal/adjustment imbalance
* Unit conversion errors
* Formulary-status mismatches

**Implementation tip:** Store rules in a configuration file so analysts can update without code changes.

```yaml
rules:
  missing_rebate:
    condition: "expected_rebate > 1000 AND actual_rebate == 0"
    severity: "high"
    recovery_likelihood: 0.9
  
  low_realization:
    condition: "actual_rebate / expected_rebate < 0.80 AND expected_rebate > 5000"
    severity: "medium"
    recovery_likelihood: 0.7
```

## 2. Statistical outlier detection

Good for interpretable early detection.

### Methods

* **Z-score**: How many standard deviations from the mean
* **Robust z-score**: Using median absolute deviation (less sensitive to outliers)
* **Interquartile range (IQR)**: Flag values outside 1.5×IQR
* **Percentile thresholds**: Flag bottom/top N%
* **Control charts**: EWMA, CUSUM for time-series
* **Seasonal decomposition**: Flag residuals outside expected bounds

### Example: Robust z-score

```python
def robust_z_score(x):
    median = np.median(x)
    mad = np.median(np.abs(x - median))
    return 0.6745 * (x - median) / mad

rebate_realization = invoices["actual_rebate"] / invoices["expected_rebate"]
z_scores = robust_z_score(rebate_realization)

# Flag observations with z < -3 (well below normal)
anomalies = z_scores < -3
```

### Useful metrics to score

* Rebate per script
* Rebate realization ratio
* Actual/expected rebate
* Quarter-over-quarter change
* Dispute rate
* Write-off rate
* Missing mapping rate

## 3. Isolation Forest

Isolation Forest is a strong general-purpose method for tabular anomaly detection. It works by isolating unusual observations through randomized decision trees; scikit-learn provides a production-ready implementation.

**Good for:**

* NDC × client × quarter anomalies
* Manufacturer × quarter anomalies
* Multi-feature outliers
* Nonlinear interactions

**Features to use:**

* Utilization
* Gross cost
* Rebate per script
* Rebate realization
* QoQ changes
* Missing mapping flags
* Formulary status
* Channel mix
* Reversal rate
* Dispute rate

**Strengths:**

* Scales well
* Handles nonlinear patterns
* Does not require labels
* Easy to implement
* Works on mixed feature types

**Weaknesses:**

* Anomaly scores require calibration
* Does not explain contract logic by itself
* Can flag high-volume legitimate changes (new launches)

```python
from sklearn.ensemble import IsolationForest

iso = IsolationForest(
    n_estimators=500,
    contamination=0.02,  # expect 2% anomalies
    max_samples="auto",
    random_state=42,
    n_jobs=-1
)

iso.fit(X_train)
scores = -iso.decision_function(X_test)  # higher score = more anomalous
predictions = iso.predict(X_test)  # -1 for anomaly, 1 for normal
```

## 4. Local Outlier Factor

Detects observations that are unusual relative to local neighbors.

**Good for:**

* Peer-comparison anomalies
* Products unusual relative to similar products
* Clients unusual relative to similar clients

**Weaknesses:**

* Less scalable on very large data
* More sensitive to feature scaling
* Harder to deploy for scoring new observations

## 5. One-Class SVM

Useful for smaller, well-scaled datasets where the "normal" boundary is complex.

**Good for:**

* Contract/product populations with enough history
* Narrow use cases

**Weaknesses:**

* Can be slow
* Sensitive to scaling and parameters
* Less practical for very large claim datasets

## 6. Clustering-based anomaly detection

Use clustering to group similar observations, then flag points far from cluster centers.

**Methods:**

* K-means distance to centroid
* Gaussian mixture model likelihood
* HDBSCAN outlier scores

**Good for:**

* Segmenting products or clients
* Finding odd rebate-yield behavior among peers
* Creating "expected peer group" benchmarks

## 7. Time-series anomaly detection

Use when you have repeated observations by NDC, brand, manufacturer, or client.

**Methods:**

* Rolling z-score
* Seasonal decomposition
* Prophet-style forecasting
* ARIMA/SARIMA residuals
* Exponential smoothing
* Bayesian structural time series
* Change-point detection

**Good for:**

* Sudden rebate yield drops
* Product disappears from invoice
* Dispute spikes
* Contract transition issues
* New quarter monitoring

**Example:**

```python
from statsmodels.tsa.seasonal import seasonal_decompose

# Decompose time series
result = seasonal_decompose(invoices["rebate_per_30"], period=4)  # quarterly seasonality
residuals = result.resid

# Flag large residuals
z_scores = np.abs((residuals - residuals.mean()) / residuals.std())
anomalies = z_scores > 3
```

## 8. Autoencoders

Autoencoders learn to reconstruct normal observations. High reconstruction error can indicate anomalies.

**Good for:**

* Large datasets
* Many correlated features
* Complex nonlinear patterns

**Weaknesses:**

* Less interpretable
* Require careful validation
* Can overfit
* Usually not the first model to deploy for audit operations

## 9. Graph-based anomaly detection

Useful if you model relationships among NDCs, manufacturers, PBMs, formularies, pharmacies, prescribers, clients, and contracts.

**Possible anomalies:**

* NDC mapped to unexpected manufacturer
* Product appears under unusual client/contract combination
* Pharmacy/channel mix inconsistent with rebate eligibility
* Manufacturer payment behavior differs from network peers

## 10. Supervised learning

If you have historical audit outcomes, use supervised models.

**Possible labels:**

* Confirmed leakage
* Recovered dollars
* False positive
* Contractually valid exception
* Data quality issue
* Manufacturer dispute sustained
* PBM adjustment recovered

**Algorithms:**

* Logistic regression
* Random forest
* Gradient boosting
* XGBoost/LightGBM/CatBoost
* Learning-to-rank models
* Uplift-style recovery models

For rebate recovery, a **supervised ranking model** is often more useful than a binary classifier because the business wants the **best cases to audit first**.

## Recommended algorithm progression

1. **Start here**: Deterministic rules + statistical outlier detection
   - Implements in days, catches 30–50% of leakage
   - Fully explainable, no false confidence

2. **Add next**: Rolling historical baselines + peer comparisons
   - Catches time-series and peer-relative anomalies
   - Additional 15–25% of leakage

3. **Then**: Isolation Forest on multi-dimensional features
   - Catches complex patterns across utilization, rebate, and data quality
   - Additional 10–20% of leakage

4. **Once you have labels**: Supervised ranking model
   - Prioritizes highest-value cases for audit
   - Dramatic improvement in analyst efficiency

Each layer compounds with the prior, not replaces it.
