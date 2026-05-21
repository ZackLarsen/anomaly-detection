# Explainability

Rebate analysts and contract teams need explanations, not just scores.

## What analysts need to understand

For every anomaly, generate a reason summary:

```text
Brand X / NDC Y / Client Z / 2025 Q2 was flagged because:
- Expected rebate was $420,000 but actual rebate was $95,000.
- Rebate realization was 23%, versus 92% rolling four-quarter median.
- The NDC belongs to a contracted brand family.
- The product was preferred on formulary during the claim period.
- 81% of the gap comes from specialty-channel claims.
- This NDC was newly launched and absent from prior invoice mapping.

Recommended action: Check invoice for missing NDC mapping.
Potential recovery: $325,000
```

## Explanation components

Provide for every anomaly:

* **Top contributing features**: Which features drove the anomaly score
* **Historical trend chart**: How this metric has trended over time
* **Peer comparison**: How this compares to similar products/clients
* **Contract rule applied**: Which contract rules were supposed to apply
* **Claim sample**: 5–10 representative claims
* **Invoice line sample**: Corresponding invoice lines (if any)
* **Recommended next action**: What should analyst do

## SHAP for supervised models

If you build a supervised ranking model, use SHAP for feature importance:

```python
import shap

# Train a tree-based model
model = xgb.XGBRanker()
model.fit(X_train, y_train)

# Compute SHAP values
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Plot top features for a single case
shap.force_plot(explainer.expected_value, shap_values[0], X_test.iloc[0])

# Summary plot showing all feature importance
shap.summary_plot(shap_values, X_test)
```

## Simple reason codes for unsupervised models

For unsupervised models (rules + isolation forest), reason codes are often more practical than SHAP:

* **MISSING_REBATE**: Expected rebate > $1000, actual = $0
* **LOW_REALIZATION**: Actual/expected < 0.75
* **YIELD_COLLAPSE**: Rebate per script dropped > 50% QoQ
* **PEER_OUTLIER**: Rebate realization > 3 MADs below peer mean
* **NEW_NDC_UNMAPPED**: NDC launched < 12 months, absent from invoice
* **HIGH_DISPUTE_RATE**: Disputes > 5% of invoiced rebates
* **GUARANTEE_SHORTFALL**: Aggregate rebate < contract guarantee
* **UNIT_MISMATCH**: Possible unit conversion error (ratio near 0.1, 10, 100x)

## Generating explanations programmatically

```python
def explain_anomaly(case, agg_df, historical_df, contracts_df):
    """Generate human-readable explanation for flagged case."""
    
    explanation = []
    
    # Basic fact
    explanation.append(f"{case['brand']} / NDC {case['ndc11']} / {case['client']} / {case['quarter']}")
    explanation.append("")
    
    # Financial gap
    gap = case['expected_rebate'] - case['actual_rebate']
    explanation.append(f"Expected rebate: ${case['expected_rebate']:,.0f}")
    explanation.append(f"Actual rebate: ${case['actual_rebate']:,.0f}")
    explanation.append(f"Gap: ${gap:,.0f}")
    explanation.append("")
    
    # Reason codes
    reasons = []
    if case['rule_flag_missing_rebate']:
        reasons.append("MISSING_REBATE: Expected > $1000, actual = $0")
    if case['rule_flag_low_realization']:
        reasons.append(f"LOW_REALIZATION: {case['rebate_realization']:.1%} vs {case['rolling_median']:.1%} median")
    if case['ml_anomaly_score'] > 0.8:
        reasons.append("ML_ANOMALY: Multi-dimensional outlier")
    
    explanation.append("Reason codes:")
    for reason in reasons:
        explanation.append(f"  • {reason}")
    explanation.append("")
    
    # Contract
    contract = contracts_df[
        (contracts_df['brand'] == case['brand'])
        & (contracts_df['client'] == case['client'])
        & (contracts_df['eff_date'] <= case['quarter_end'])
    ].iloc[0]
    
    explanation.append(f"Contract terms: {contract['rebate_basis']} @ {contract['rebate_rate']}")
    explanation.append("")
    
    # Trend
    historical = historical_df[
        (historical_df['ndc11'] == case['ndc11'])
        & (historical_df['client'] == case['client'])
    ].sort_values('quarter')
    
    if len(historical) > 0:
        avg_realization = historical['rebate_realization'].mean()
        explanation.append(f"Historical average realization: {avg_realization:.1%}")
        explanation.append(f"Current: {case['rebate_realization']:.1%}")
        explanation.append("")
    
    # Next steps
    explanation.append("Recommended action: Review invoice for missing NDC mapping")
    explanation.append(f"Potential recovery: ${gap:,.0f}")
    
    return "\n".join(explanation)
```

## Visualization for analysts

Create a case detail page for each flagged anomaly:

```
╔════════════════════════════════════════════════════════════════╗
║  REBATE ANOMALY CASE DETAIL                                     ║
╠════════════════════════════════════════════════════════════════╣
║  NDC: 12345678901  |  Brand: Brand X  |  Client: G001          ║
║  Quarter: 2025-Q2  |  Channel: Retail                          ║
╠════════════════════════════════════════════════════════════════╣
║  FINANCIAL SUMMARY                                              ║
╠════════════════════════════════════════════════════════════════╣
║  Expected Rebate:          $420,000                             ║
║  Actual Rebate:            $ 95,000                             ║
║  GAP (RECOVERABLE):        $325,000  ← Primary concern         ║
║  Realization Ratio:              23%  (Historical avg: 92%)   ║
╠════════════════════════════════════════════════════════════════╣
║  ANOMALY REASONS (Why flagged)                                  ║
╠════════════════════════════════════════════════════════════════╣
║  ✓ RULE: Low realization (< 75%)                               ║
║  ✓ TREND: 70% drop from prior quarter                           ║
║  ✓ ML SCORE: 0.92 (multidimensional outlier)                    ║
╠════════════════════════════════════════════════════════════════╣
║  HISTORICAL TREND (Last 8 quarters)                             ║
╠════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Rebate Realization %      ┏━━━━━━━━                            ║
║     100% ┃                 ┃     ┃━━━┓                          ║
║      80% ┃  ┏━━━━━━━━━━━━━━┃     ┃   ┗━━━━  ← 23%             ║
║      60% ┃  ┃               ┃     ┃                             ║
║      40% ┃  ┃               ┃     ┃                             ║
║      20% ┃  ┃               ┃     ┃                             ║
║       0% ┗━━━━━━━━━━━━━━━━━┛     ┗                             ║
║         2024-Q1...Q4  2025-Q1  Q2  Q3                           ║
║                                                                  ║
╠════════════════════════════════════════════════════════════════╣
║  PEER COMPARISON (Similar NDCs, same client)                    ║
╠════════════════════════════════════════════════════════════════╣
║  NDC Y (same brand):      85% realization  (Normal)            ║
║  NDC Z (same brand):      88% realization  (Normal)            ║
║  This NDC:               23% realization  ← OUTLIER            ║
╠════════════════════════════════════════════════════════════════╣
║  CONTRACT RULES                                                 ║
╠════════════════════════════════════════════════════════════════╣
║  Contract: Mfr X → Brand X → Client G001                       ║
║  Effective: 2024-01-01 to 2026-12-31                           ║
║  Basis: PER_30_DAY_SCRIPT                                       ║
║  Rate: $12.50 per 30-day script                                 ║
║  Formulary Requirement: PREFERRED                               ║
╠════════════════════════════════════════════════════════════════╣
║  SAMPLE CLAIMS (5 of 145 paid claims)                           ║
╠════════════════════════════════════════════════════════════════╣
║  Claim ID | Fill Date | Days Supply | Gross Cost | Exp Rebate ║
║  C0001234 | 2025-04-01|    30       |    $180    |   $12.50   ║
║  C0001235 | 2025-04-05|    30       |    $180    |   $12.50   ║
║  C0001236 | 2025-04-08|    60       |    $360    |   $25.00   ║
║  C0001237 | 2025-04-15|    30       |    $180    |   $12.50   ║
║  C0001238 | 2025-04-18|    30       |    $180    |   $12.50   ║
║  ... (140 more claims)                                          ║
╠════════════════════════════════════════════════════════════════╣
║  SAMPLE INVOICE LINES                                           ║
╠════════════════════════════════════════════════════════════════╣
║  No invoice line found for this NDC in 2025-Q2                 ║
║  → Suggests missing from rebate invoice                         ║
╠════════════════════════════════════════════════════════════════╣
║  RECOMMENDED ACTION                                             ║
╠════════════════════════════════════════════════════════════════╣
║  1. Check if NDC was newly launched (may not be on contract)    ║
║  2. Request invoice detail from PBM                             ║
║  3. If missing: dispute for backfill                            ║
║                                                                  ║
║  Potential Recovery:  $325,000                                  ║
║  Effort:              Medium (invoice inquiry)                  ║
║  Confidence:          High (clear contract + claims)            ║
╚════════════════════════════════════════════════════════════════╝
```

## Key principle

**Explainability is not a luxury.** Rebate analysts and PBMs need to understand why a case was flagged before they invest time disputing it. A model that says "this is an anomaly, trust me" will be ignored. A model that says "this NDC has a 70% rebate gap despite 145 paid claims and a clear contract" will be acted upon.
