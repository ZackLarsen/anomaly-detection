# Quick Start: Best First Model

If you're just starting out, don't build a complex system. Use this.

## The best first production model is usually not exotic

Use this approach:

```text
Expected rebate reconciliation
+ deterministic leakage rules
+ rolling historical baselines
+ Isolation Forest for multidimensional outliers
+ business-value ranking
```

## Recommended starting grain

Aggregate data at this level:

```text
NDC × brand × manufacturer × client/group × quarter × channel
```

This grain is:

* **Granular enough** to catch product/client/channel-specific leakage
* **Coarse enough** to be stable and interpretable
* **Business-aligned** — rebate analysts think in terms of NDC-quarter-client
* **Computable** — not too large, not too sparse

## Recommended first target

```text
rebate_gap = expected_rebate - actual_rebate
```

Rank by:

```text
priority = anomaly_flag × positive_rebate_gap × recoverability_confidence
```

## Recommended first dashboard

Create one report:

```text
Top 100 recoverable rebate leakage opportunities by estimated dollars,
with reason codes and supporting claim/invoice evidence.
```

That is the fastest path from anomaly detection to actual rebate recovery.

## Typical results from this approach

* **Phase 1 (Reconciliation + Rules)**: 30–50% of recoverable dollars identified with low false-positive rate
* **Phase 2 (Add Statistical Monitoring)**: Additional 15–25% detected through trend and peer-comparison anomalies
* **Phase 3 (Add ML)**: Another 10–20% from multidimensional patterns
* **Phase 4 (Supervised Model)**: Dramatic improvement in precision@K once analyst labels exist

## Implementation timeline

* **Weeks 1–2**: Build expected rebate reconciliation engine
* **Weeks 3–4**: Implement deterministic rules
* **Weeks 5–6**: Add rolling baselines and statistical anomaly detection
* **Weeks 7–8**: Train Isolation Forest and create audit queue
* **Weeks 9–12**: Deploy, analyst review, collect labels, iterate

## Next steps

1. Understand the [data architecture](../02-data/data-model.md)
2. Design your [target outcomes](../02-data/target-outcomes.md)
3. Engineer [features](../03-modeling/feature-engineering.md)
4. Build your [model architecture](../03-modeling/model-architecture.md)
5. Deploy and [iterate](../04-implementation/deployment-pipeline.md)
