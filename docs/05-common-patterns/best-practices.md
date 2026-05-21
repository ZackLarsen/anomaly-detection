# Best Practices and Common Mistakes

## What NOT to do

Avoid these mistakes:

* **Don't start with deep learning** before fixing contract logic
  - Garbage contracts → garbage model
  - Spend weeks on rules and reconciliation first

* **Don't model raw claim lines only**; aggregate to business-relevant grains
  - NDC × client × quarter is usually right
  - Claim-level too noisy; contract-level too coarse

* **Don't ignore reversals and adjustments**
  - Net them correctly before modeling
  - They represent legitimate claim corrections

* **Don't compare rebate yield across drugs without controlling for contract/formulary/channel**
  - A $50 brand drug may have legitimately low yield
  - A $5 generic may have high yield
  - Normalize within peer groups

* **Don't use current formulary status for historical claims**
  - Claims from March should use March formulary rules
  - Not December rules

* **Don't treat all anomalies as recoverable**
  - Many patterns are contractually valid
  - Distinguish clearly

* **Don't optimize for anomaly count**; optimize for recovered dollars
  - Finding 1000 cases worth $50 each is worse than 10 cases worth $50K each
  - Set a minimum dollar threshold

* **Don't trust NDC mappings without effective dates**
  - An NDC-to-contract mapping valid today may not have been valid last quarter
  - Store mappings with effective date ranges

* **Don't ignore audit windows and dispute deadlines**
  - Rebate disputes have limited windows (usually 120–180 days)
  - A $1M case expires in 30 days
  - Track audit window expiration

* **Don't build a black box** that rebate analysts cannot explain to PBMs or manufacturers
  - Every flagged case must have a clear reason
  - "ML said so" is not acceptable

## What TO do

Best practices:

* **Start with deterministic rules** and reconciliation
  - Implement in days, not weeks
  - High ROI
  - Fully explainable
  - Catches 30–50% of leakage

* **Aggregate to the right grain early**
  - NDC × client × quarter is the sweet spot
  - Not claim-level (too noisy)
  - Not manufacturer-level (too coarse)

* **Validate data quality before modeling**
  - Missing NDC? Stop and fix.
  - Invoice mismatch? Stop and fix.
  - Bad data wastes weeks of modeling time

* **Use effective dating everywhere**
  - Claims matched to contracts active on fill date
  - Formulary matched to rules active on fill date
  - NDCs matched to master data active on fill date

* **Monitor data quality continuously**
  - Missing NDC rate, invoice match rate, etc.
  - Alert on degradation
  - Fix issues immediately

* **Prioritize by recoverable dollars**
  - Not anomaly count
  - Not anomaly probability
  - Net expected recovery = gap × recoverability × confidence

* **Involve analysts early**
  - Show them top 20 cases after Phase 1
  - Get their feedback on true positives vs false positives
  - Let them guide which patterns matter

* **Track outcomes obsessively**
  - Every case should log analyst decision and recovered dollars
  - This feedback loop is what makes the model better
  - Quarterly retraining beats one-shot training

* **Separate concerns**
  - Rules engine for known patterns
  - Statistical layer for trends
  - ML layer for multi-dimensional anomalies
  - Prioritization layer for business value
  - Not one monolithic model

* **Be transparent with manufacturers**
  - Explain why you're disputing
  - Show contract language
  - Show supporting claims
  - Manufacturers respect clear logic more than "ML said"

## Common failure modes

### Failure mode 1: Bad contract data

**Symptom**: Model flags cases that turn out to be contractually valid.

**Root cause**: Contract terms incomplete, outdated, or misinterpreted.

**Fix**:
- Audit contracts with legal/procurement team
- Create data quality checks (e.g., all rebate-eligible brands have contracts)
- Version contract rules with effective dates
- Get legal review before disputing

### Failure mode 2: Data quality degradation

**Symptom**: Model performance drops mysteriously over time.

**Root cause**: PBM changed their data feed, NDC normalization broke, invoicing changed.

**Fix**:
- Monitor data quality metrics daily
- Alert on changes (missing NDC rate, invoice match rate)
- Investigate immediately when alert fires
- Update pipeline if data format changes

### Failure mode 3: Overfitting to synthetic anomalies

**Symptom**: Model detects all synthetic anomalies perfectly but misses real ones.

**Root cause**: Trained on too much synthetic data; didn't validate on real data.

**Fix**:
- Validate on hold-out real data (analyst-reviewed cases)
- If synthetic ≠ real, adjust synthetic data generation
- Test on known past incidents
- Backtest on historical quarters

### Failure mode 4: Analyst fatigue

**Symptom**: Analysts stop reviewing cases seriously.

**Root cause**: Too many false positives, low precision.

**Fix**:
- Don't send top 500 cases; send top 50 with high confidence
- Precision@K > 70% is minimum
- Have supervisors spot-check analyst work
- Adjust rules/thresholds if precision drops

### Failure mode 5: Manufacturer friction

**Symptom**: Manufacturers push back on disputes; disputes fail.

**Root cause**: Cases not clearly explained, contract logic questioned.

**Fix**:
- Involve legal in dispute language
- Show clear contract language + supporting claims
- Respect dispute windows
- Don't dispute marginal cases ($5K when cost of dispute is $2K)

### Failure mode 6: Ignoring audit windows

**Symptom**: Cases become non-recoverable before action is taken.

**Root cause**: No tracking of audit window expiration; cases age.

**Fix**:
- Flag cases expiring in < 30 days as urgent
- Separate queue for audit-window risks
- Weekly monitoring of aging cases
- Escalate to management if approaching deadline

## Metrics for success

Track these and adjust:

* **Precision@100**: Of top 100 cases, % confirmed as valid leakage (target: > 70%)
* **Dollars@100**: Of top 100, total recovery potential (target: > $500K)
* **Recovery rate**: Recovered $ / identified $ (target: > 50%)
* **Analyst agreement**: Multiple reviewers agree on same cases (target: > 80%)
* **Disputes won**: % of disputes that succeed (target: > 50%)
* **Audit window preservation**: % of cases recovered before expiration (target: > 80%)
* **Time to recovery**: Days from identification to recovery (target: < 120 days)
* **False positive cost**: Analyst hours spent on invalid cases (target: < 10% of total)

## When to pivot

Stop and reassess if:

- [ ] Precision@100 < 50% for 2 consecutive months
- [ ] Recovery rate < 20%
- [ ] Analyst agreement < 60%
- [ ] Data quality metrics trending worse (missing NDC rate increasing)
- [ ] Disputes consistently failing (< 30% win rate)

Likely fixes:

1. Contract data is wrong → audit with legal
2. Data quality degraded → investigate feed change
3. Rules too aggressive → calibrate thresholds
4. Model overfitting → simplify feature set
5. Analyst misunderstanding → better explanations needed

## The golden rule

> **If you can't explain it to a manufacturer, don't dispute it.**

Every case should have a clear, simple explanation:

✓ "Expected rebate: $50K per contract rule X. Actual: $0. Invoice shows product excluded. Should be included per contract."

✗ "ML anomaly score 0.87, combined with low realization 23% vs 92% peer median, indicates possible mapping error."

The first will win disputes. The second will lose them.
