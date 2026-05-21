# Deployment Pipeline

## Monthly or quarterly workflow

```
1. Ingest latest claims
   ↓
2. Apply runout logic
   ↓
3. Refresh drug/formulary/contract data
   ↓
4. Calculate expected rebate
   ↓
5. Match actual invoice/payment data
   ↓
6. Score anomalies (rules + statistical + ML)
   ↓
7. Generate audit queue
   ↓
8. Analyst reviews cases (top 100-500)
   ↓
9. Send disputes/inquiries
   ↓
10. Track outcomes (recovered $ by case)
   ↓
11. Feed labels back into model
```

## Implementation details

### Step 1: Ingest latest claims

```python
# Load most recent claims data
new_claims = pd.read_parquet("s3://data-lake/pharmacy_claims/latest/*.parquet")

# Append to historical archive
all_claims = pd.concat([historical_claims, new_claims])
```

### Step 2: Apply runout logic

Pharmacy claims run out (late-arriving claims continue to arrive) for 6-12 months after the service date. Account for this:

```python
# Mark quarters as "complete" or "runout"
today = pd.Timestamp.now()
current_quarter = f"{today.year}-Q{(today.month - 1) // 3 + 1}"

# Quarters finalized (>= 6 months old)
finalized_quarters = quarters[quarters < f"{(today.year - 0.5)}-Q{((today.month - 1) // 3 + 1)}"]

# Quarters still in runout (< 6 months old, exclude from some analyses)
runout_quarters = quarters[quarters >= f"{(today.year - 0.5)}-Q{((today.month - 1) // 3 + 1)}"]
```

### Step 3: Refresh reference data

```python
# Download latest drug master from FDA NDC Directory
ndc_df = fetch_fda_ndc_directory()

# Load formulary files
formulary_df = load_formulary_files()

# Load contract data (from internal system)
contracts_df = load_contract_database()
```

### Step 4–7: Score anomalies

This is the core pipeline. Run in this order:

1. Calculate expected rebate (Layer 1)
2. Apply rules engine (Layer 2)
3. Add statistical features (Layer 3)
4. Score with ML (Layer 4)
5. Prioritize (Layer 5)

### Step 8: Generate audit queue

```python
audit_queue = model_output[
    model_output["rebate_gap"] > minimum_threshold
].sort_values("priority_score", ascending=False).head(500)

# Create workbench export
workbench_export = audit_queue[[
    "ndc11",
    "brand_name",
    "manufacturer",
    "group_id",
    "quarter",
    "expected_rebate",
    "actual_rebate",
    "rebate_gap",
    "claim_count",
    "rule_flags",
    "ml_score",
    "priority_score",
    "recommended_action",
]]

workbench_export.to_csv("audit_queue.csv")
```

### Step 9–11: Track outcomes and feedback

```python
# Analyst submits review
analyst_review = pd.read_csv("analyst_review.csv")

# Log outcome
for _, row in analyst_review.iterrows():
    outcome_log.append({
        "case_id": row["case_id"],
        "analyst_decision": row["decision"],  # "VALID", "INVALID", "RESEARCH"
        "disputed_amount": row["disputed_amount"],
        "recovered_amount": row["recovered_amount"],
        "dispute_status": row["dispute_status"],  # "PENDING", "WON", "LOST"
        "timestamp": pd.Timestamp.now(),
    })

# Use outcomes to label training data
labels = outcome_log[outcome_log["analyst_decision"] == "VALID"]

# Retrain supervised model quarterly
if len(labels) > 100:
    supervised_model.retrain(labels)
```

## Automation

Use an orchestration tool (Airflow, Prefect, Dagster) to schedule the pipeline:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

dag = DAG(
    "rebate_anomaly_detection",
    default_args={"owner": "data-science", "start_date": days_ago(1)},
    schedule_interval="0 2 1 * *",  # Run on 1st of every month at 2 AM
)

# Task 1: Ingest
ingest_task = PythonOperator(
    task_id="ingest_claims",
    python_callable=ingest_latest_claims,
    dag=dag,
)

# Task 2: Refresh reference data
refresh_task = PythonOperator(
    task_id="refresh_reference_data",
    python_callable=refresh_drug_master,
    dag=dag,
)

# Task 3–7: Score (depends on 1 & 2)
score_task = PythonOperator(
    task_id="score_anomalies",
    python_callable=run_full_pipeline,
    dag=dag,
    trigger_rule="all_success",
)

# Task 8: Generate queue
queue_task = PythonOperator(
    task_id="generate_audit_queue",
    python_callable=create_audit_queue,
    dag=dag,
)

# Dependencies
[ingest_task, refresh_task] >> score_task >> queue_task
```

## Alerts

Configure alerts for data quality issues or unexpected patterns:

```python
# Alert if % missing NDCs > 5%
if agg["missing_ndc"].mean() > 0.05:
    send_alert("WARN: Missing NDC rate > 5%", severity="HIGH")

# Alert if claims-to-invoice reconciliation fails
if not reconcile_claims_to_invoices():
    send_alert("ERROR: Claims-invoice reconciliation failed", severity="CRITICAL")

# Alert if no anomalies detected (might be data issue)
if len(audit_queue) == 0:
    send_alert("WARN: No anomalies detected this month", severity="MEDIUM")

# Alert if anomaly score distribution looks wrong
if anomaly_score.median() < -10:
    send_alert("WARN: Anomaly score distribution unusual", severity="MEDIUM")
```

## Monitoring

Track these metrics monthly:

* **Cases generated**: How many cases flagged
* **Cases reviewed**: How many analysts reviewed
* **Analyst agreement**: Agreement rate across multiple reviewers
* **Precision@100**: Of top 100, how many are valid
* **Dollars identified**: Total estimated leakage
* **Dollars recovered**: Total actual recovery
* **Days to recovery**: Median time from flag to recovery
* **Pipeline latency**: Hours from data ingestion to audit queue ready
* **Data quality**: NDC coverage, invoice match rate, etc.

Create a dashboard tracking these metrics over time.

## Rollback plan

If the system produces invalid results, you should be able to revert quickly:

```python
# Rollback to previous month's queue
prev_queue = load_previous_audit_queue()
active_queue.clear()
active_queue.update(prev_queue)

# Investigate issue
debug_pipeline()

# Re-run when fixed
run_pipeline(force=True)
```
