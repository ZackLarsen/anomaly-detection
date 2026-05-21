# Implementation Roadmap: 5-Phase Approach

Build incrementally. Each phase delivers value independently; later phases enhance it.

## Phase 1: Reconciliation and rules (Weeks 1–4)

**Duration**: 2–4 weeks

**Deliverables:**

* Claim-to-invoice reconciliation script
* Expected rebate calculator for top 20 manufacturers/products
* Missing rebate flags
* Low realization flags (actual/expected < 0.8)
* New unmapped NDC report
* Guarantee shortfall report
* Data quality report

**Effort**: 1 Data Engineer + 1 Data Scientist

**Output**: Spreadsheet-based audit queue (top 50 cases)

**Value**: This alone may recover meaningful dollars. Estimates: **30–50% of recoverable leakage identified**.

**Success criteria:**

- [ ] Expected rebate calculations match manual spot-checks
- [ ] Claim-invoice reconciliation achieves 95%+ match
- [ ] Audit queue passes analyst review (70%+ agree with flagged cases)

## Phase 2: Statistical monitoring (Weeks 5–8)

**Add:**

* Rolling rebate-yield baselines (3-quarter rolling median)
* QoQ/YoY change detection
* Peer-comparison anomalies (NDC yield vs brand/class peers)
* Manufacturer dispute anomaly detection
* Specialty-channel monitoring

**Effort**: 1 Data Scientist (part-time)

**Output**: Enhanced audit queue with statistical scores

**Value**: Additional **15–25% of leakage identified** through trend and peer patterns.

**Success criteria:**

- [ ] Statistical features not correlated with Phase 1 flags
- [ ] Peer comparison catches cases Phase 1 misses
- [ ] Time-series anomalies backtest correctly on known incidents

## Phase 3: ML anomaly detection (Weeks 9–12)

**Add:**

* Isolation Forest at NDC × client × quarter grain
* PyOD ensemble comparison
* Time-series residual models for major products
* Prioritized audit queue combining all signals

**Effort**: 1 Senior Data Scientist

**Output**: ML-enhanced ranking system

**Value**: Another **10–20% of leakage identified** from multi-dimensional patterns.

**Success criteria:**

- [ ] Isolation Forest validation on synthetic anomalies > 90%
- [ ] Precision@100 > 70% (70 of top 100 are true leakage)
- [ ] Dollars@100 > $500K
- [ ] No single feature dominates; meaningful multi-feature interactions

## Phase 4: Supervised recovery model (Weeks 13–16, ongoing)

**Triggers**: After Phase 3, once 100+ cases reviewed by analysts

**Add:**

* Recoverability classifier
* Recovered-dollar regression model
* Audit queue prioritized for expected net recovery
* Model retraining quarterly as labels accumulate

**Effort**: 1 Senior Data Scientist + ongoing analyst feedback

**Output**: High-precision, business-value-optimized ranking

**Value**: **Dramatic improvement in analyst efficiency**. Precision@100 may reach 80–90%.

**Success criteria:**

- [ ] Labeling of analyst review outcomes complete
- [ ] Supervised model trains on 100+ labeled cases
- [ ] Supervised model precision@100 > 80%
- [ ] Dollars recovered / analyst time invested > $50K per analyst-month

## Phase 5: Closed-loop recovery operations (Ongoing)

**Integrate with:**

* Case management system
* PBM inquiry workflows
* Manufacturer dispute packages
* Contract amendment tracking
* Finance recovery booking
* Monthly reporting and monitoring

**Effort**: 1 Analytics Engineer + 1 Rebate Operations Manager

**Output**: Fully operational rebate recovery program

**Value**: Sustained, predictable recovery stream.

**Success criteria:**

- [ ] 100+ cases audited per month
- [ ] 50%+ success rate on disputes
- [ ] $2M+ annual recovery
- [ ] Net ROI > 5:1 (recovery / total program cost)

## Timeline and resources

```
Phase 1 (Reconciliation)      |████████████|
Phase 2 (Statistical)                    |████████████|
Phase 3 (ML)                                          |████████████|
Phase 4 (Supervised)                                                  |███→
Phase 5 (Operations)                                                  |███→

Week:  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 ...
                                                               |
                                        Monthly reporting/monitoring
```

## Resource allocation

| Phase | Data Eng | Data Scientist | Sr. DS | Analyst | Total Cost |
|-------|----------|----------------|--------|---------|-----------|
| 1     | 0.5 FTE  | 0.5 FTE        | -      | 0.25    | $100K     |
| 2     | 0.25     | 0.75           | -      | 0.5     | $120K     |
| 3     | 0.1      | 0.5            | 1.0    | 1.0     | $180K     |
| 4     | 0.1      | 0.2            | 0.5    | 1.5     | $150K     |
| 5     | 0.5      | -              | 0.2    | 2.0     | $200K/yr  |

**Total investment**: ~$550K over 16 weeks, then $200K/year for operations.

**Expected annual recovery**: $3–5M (depending on data quality and contract complexity).

**ROI**: 5–10x in Year 1, much higher in subsequent years.

## Success metrics by phase

| Phase | Metric | Target |
|-------|--------|--------|
| 1 | Cases identified | 50–100 |
| 1 | Estimated leakage | $500K–$2M |
| 2 | Additional cases | +25–50 |
| 2 | Additional leakage | +$250K–$750K |
| 3 | Additional cases | +15–30 |
| 3 | Additional leakage | +$200K–$500K |
| 4 | Precision@100 | 80%+ |
| 4 | Dollars@100 | $1M+ |
| 5 | Monthly cases resolved | 20–30 |
| 5 | Monthly recovery | $200K–$500K |
| 5 | Annual recovery | $2M–$5M |

## Risk mitigation

| Risk | Phase | Mitigation |
|------|-------|-----------|
| Poor data quality | All | Phase 1 includes quality audit; stop if > 5% missing NDC |
| Analyst pushback | 1–2 | Involve analysts early; show precision metrics |
| Manufacturer disputes | 3+ | Consult legal before disputing; respect audit windows |
| Model drift | 4–5 | Retrain quarterly; monitor precision@K monthly |
| Contract misinterpretation | All | Legal review of top rule categories |

## Decision points

**After Phase 1**: Are we getting 70%+ analyst agreement? If not, fix contract logic before proceeding.

**After Phase 2**: Are statistical features adding value beyond Phase 1? If precision@100 is still < 50%, recalibrate before Phase 3.

**After Phase 3**: Are ML scores helping? If not, stick with Phases 1–2. ML is optional.

**Before Phase 4**: Have we gotten 100+ analyst reviews with labeled outcomes? If not, delay until we do.

**Ongoing**: Is net recovery positive? If recovery < cost, investigate why before expanding.

## Next steps

1. **Assign Phase 1 lead** (Data Engineer)
2. **Audit current data quality**
3. **Develop expected rebate logic** (work with contracts team)
4. **Build first reconciliation report**
5. **Present Phase 1 results** to executive sponsor
6. **Plan Phase 2** based on Phase 1 learnings
