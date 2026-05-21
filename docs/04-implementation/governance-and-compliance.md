# Governance and Compliance

This use case touches sensitive financial, contractual, and health data. Implement these controls.

## HIPAA and privacy

* **Minimum necessary access**: Analysts only access data they need to resolve cases
* **PHI tokenization**: Replace member IDs with tokens; map back to real IDs only for final dispute
* **Role-based access**: Different permissions for analysts, data scientists, executives
* **Data retention**: Purge old cases per data retention policy
* **Audit logs**: Log all access and modifications

## Contract confidentiality

* **Manufacturer agreements**: Contract terms often confidential; limit access to contract team
* **PBM disputes**: Sensitive; restrict to authorized personnel
* **Client disputes**: Confidential; role-based access

## Data governance

* **Versioned contract rules**: Track all changes to contract interpretation
* **Audit trail**: Every calculated rebate should be reproducible
* **Documentation**: Why each rule exists, when it was added, who added it
* **Conflict of interest**: Separate analysts from business targets (don't push analysts to "find more leakage")

## Model governance

* **Reproducible scoring**: Same input → same output every time
* **Explainability**: Every flagged case has a clear reason
* **Bias audit**: Check for systematic bias by manufacturer, client, product class
* **Validation**: Regular testing on hold-out data
* **Approval**: Model changes require sign-off before production

Example model governance policy:

```
1. Data Scientist proposes model change
2. Code review by 2 peers
3. Testing on synthetic data + hold-out test set
4. Validation against known past incidents
5. Business validation (finance/contracts team)
6. Compliance review (legal/governance)
7. Approval by Director of Analytics
8. A/B test in production if high-risk change
9. Monitoring for first 2 months post-launch
```

## Legal and compliance

* **Clear separation**: Distinguish between:
  - Clinical appropriateness analytics (different governance)
  - Rebate maximization (this use case)
  
  A model that pushes high-rebate drugs conflicts with clinical appropriateness. Governance must be explicit.

* **Formulary governance**: Who decides what gets on the formulary?
  - Should not be the same team optimizing for rebates alone
  - Rebate team provides data; clinical/formulary committee makes decisions

* **Audit defense**: Every recovered dollar should be defensible in disputes
  - Clear contract language, not interpretation
  - Accurate utilization data, audited
  - Reasonable timelines and process

* **Dispute process**: 
  - Manufacturer dispute window (usually 120–180 days)
  - PBM must respond within specified timeframe
  - Appeal process for disputed results

## Example governance checklist

```
[ ] Access control configured
    - [ ] Role-based access in place
    - [ ] Analyst permissions locked to assigned cases
    - [ ] Executive dashboards don't show contract details

[ ] Audit logging enabled
    - [ ] All queries logged
    - [ ] All model scoring runs logged
    - [ ] All analyst actions (view, download, dispute) logged
    - [ ] Logs retained for 3 years

[ ] Data quality controls
    - [ ] Pre-scoring validation tests pass
    - [ ] Reconciliation tests pass
    - [ ] Outlier detection checks pass

[ ] Model governance
    - [ ] Model change log maintained
    - [ ] Code review completed
    - [ ] Validation on hold-out data completed
    - [ ] Performance metrics documented

[ ] Contract alignment
    - [ ] Every flagged case links to specific contract rule
    - [ ] Contract terms documented
    - [ ] Contract effective dates respected

[ ] Legal review
    - [ ] Dispute process documented
    - [ ] Appeal process documented
    - [ ] Timeline for action documented
    - [ ] Attorney sign-off obtained

[ ] Compliance training
    - [ ] All team members trained on data privacy
    - [ ] All team members trained on contract confidentiality
    - [ ] All team members trained on dispute process
    - [ ] Training refreshed annually

[ ] Documentation
    - [ ] System design document completed
    - [ ] Data dictionary completed
    - [ ] Business rules document completed
    - [ ] Analyst runbook completed
```

## Things NOT to do

* **Don't**: Optimize for "cases found" without regard to actual recovery
  - Incentivizing quantity of flagged cases leads to false positives
  
* **Don't**: Push analysts to a dollar recovery target if it creates bias
  - Targets create pressure to interpret ambiguous situations as "leakage"
  
* **Don't**: Hide contract logic in black-box ML
  - Explain every flag clearly enough for manufacturer to understand and respond
  
* **Don't**: Ignore dispute outcomes
  - If manufacturer wins disputes on a case, that's a signal the rule is wrong
  
* **Don't**: Assume all "anomalies" are recoverable
  - Many patterns are contractually valid; distinguish clearly

## Be explicit about rebate maximization

This is a rebate recovery system. It is designed to **maximize rebates owed under existing contracts**, not to push patients toward high-rebate drugs. Make this clear:

```
MISSION STATEMENT (Example)
"Identify and recover manufacturer rebates owed under existing 
commercial rebate contracts. Ensure accurate utilization reporting, 
contract compliance, and timely payment of earned rebates."

WHAT WE DO:
- Detect missing or underpaid rebates from known contracts
- Verify accurate NDC mapping and utilization reporting
- Dispute incorrect rebate calculations

WHAT WE DON'T DO:
- Influence formulary decisions (clinical/formulary team decides)
- Recommend drugs based on rebate value (clinical evaluation only)
- Override legitimate contract exclusions (audit exclusion logic, not outcomes)
```

## Audit trail example

Every case should have a complete audit trail:

```
CASE #47362: Brand X / NDC 12345678901 / Client G001 / Q2 2025

Timeline:
2025-05-01 10:23 | Automated: Flagged as MISSING_REBATE
                  |   - Expected rebate: $420K (from contract terms)
                  |   - Actual rebate: $0 (from invoice)
                  |   - Supporting claims: 145 paid claims
                  |   - Confidence: HIGH

2025-05-01 14:45 | Data Scientist: ML anomaly score added (0.87)

2025-05-02 09:15 | Analyst review: Case assigned to Jane Doe
                  |   - Validation: CONFIRMED (contract reviewed)
                  |   - Root cause: Missing from PBM invoice
                  |   - Recommended action: PBM inquiry

2025-05-05 11:30 | Analyst: PBM inquiry sent
                  |   - Reference: Invoice #PBM-2025-Q2-001
                  |   - Requested: Backfill for missing NDC

2025-06-15 14:00 | PBM response: Acknowledged missing NDC
                  |   - PBM will re-invoice manufacturer
                  |   - Timeline: 30 days

2025-07-10 10:20 | Finance: Recovery logged
                  |   - Recovered: $325,000
                  |   - Status: Received from manufacturer
                  |   - Posted to client account

Final outcome: RECOVERED $325K
Time to resolution: 70 days
```

This trail is essential for disputes and compliance reviews.
