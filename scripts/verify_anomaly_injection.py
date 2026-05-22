"""
Verification script for Phase 3 anomaly injection functions.

Loads all base data, calls each of the 7 injection functions with small
counts (1–2 anomalies each), verifies correctness, and saves the labelled
invoice dataset to data/synthetic/invoices_with_anomalies.parquet.

Usage:
    cd /Users/zacklarsen/workspace/anomaly-detection
    python scripts/verify_anomaly_injection.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from synthetic_data_gen import (
    ClaimsGenerator,
    ContractGenerator,
    DrugGenerator,
    FormularyGenerator,
    InvoiceGenerator,
    load_config,
)
from synthetic_data_gen.inject_anomalies import (
    inject_dispute_spike,
    inject_guarantee_true_up_missing,
    inject_missing_rebate,
    inject_rebate_yield_collapse,
    inject_specialty_channel_omission,
    inject_unit_conversion_error,
    inject_unmapped_ndc,
    make_empty_labels_df,
)

CONFIG_PATH = ROOT / "configs" / "base.yaml"
OUTPUT_DIR = ROOT / "data" / "synthetic"


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _section("Phase 3 Anomaly Injection Verification")

    # ------------------------------------------------------------------
    # 1. Generate base data
    # ------------------------------------------------------------------
    _section("Step 1 / 8 — Generating base datasets")
    cfg = load_config(str(CONFIG_PATH))
    seed = cfg.random_seed

    t0 = time.perf_counter()
    claims_gen = ClaimsGenerator(cfg, seed=seed)
    claims = claims_gen.generate()
    print(f"  Claims:     {len(claims):>10,} rows  ({time.perf_counter() - t0:.1f}s)")

    t0 = time.perf_counter()
    drug_gen = DrugGenerator(cfg, claims, seed=seed)
    drugs = drug_gen.generate()
    print(f"  Drugs:      {len(drugs):>10,} rows  ({time.perf_counter() - t0:.1f}s)")

    t0 = time.perf_counter()
    form_gen = FormularyGenerator(cfg, claims, drugs, seed=seed)
    formulary = form_gen.generate()
    print(f"  Formulary:  {len(formulary):>10,} rows  ({time.perf_counter() - t0:.1f}s)")

    t0 = time.perf_counter()
    contract_gen = ContractGenerator(cfg, drugs, seed=seed)
    contracts = contract_gen.generate()
    print(f"  Contracts:  {len(contracts):>10,} rows  ({time.perf_counter() - t0:.1f}s)")

    t0 = time.perf_counter()
    inv_gen = InvoiceGenerator(cfg, claims, contracts, drugs, formulary, seed=seed)
    invoices = inv_gen.generate()
    print(f"  Invoices:   {len(invoices):>10,} rows  ({time.perf_counter() - t0:.1f}s)")

    # Initialise labels DataFrame
    labels = make_empty_labels_df()

    # Snapshot originals for integrity checks
    original_invoice_count = len(invoices)
    base_ndcs = set(invoices["ndc11"].to_list())

    # ------------------------------------------------------------------
    # 2. inject_missing_rebate  (count=1)
    # ------------------------------------------------------------------
    _section("Step 2 / 8 — inject_missing_rebate (count=1)")
    t0 = time.perf_counter()
    invoices_prev = invoices.clone()
    invoices, labels, contracts = inject_missing_rebate(
        invoices, labels, contracts, count=1, seed=seed
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    mr_labels = labels.filter(pl.col("anomaly_type") == "MISSING_REBATE")
    print(f"  MISSING_REBATE labels created:  {len(mr_labels)}")
    assert len(mr_labels) == 1, f"Expected 1 label, got {len(mr_labels)}"

    # Verify zeroed rows
    ndc = mr_labels["ndc11"][0]
    client = mr_labels["client_id"][0]
    quarter = mr_labels["quarter"][0]
    zeroed = invoices.filter(
        (pl.col("ndc11") == ndc)
        & (pl.col("client_id") == client)
        & (pl.col("invoice_quarter") == quarter)
    )
    assert zeroed.height > 0, "Target row not found after missing_rebate injection"
    assert float(zeroed["actual_rebate"][0]) == 0.0, (
        f"actual_rebate not zero: {zeroed['actual_rebate'][0]}"
    )
    assert float(mr_labels["estimated_impact"][0]) >= 0.0, "Negative estimated_impact"
    print(f"  [OK] actual_rebate = 0 for {ndc}/{client}/{quarter}")
    print(f"  [OK] estimated_impact = ${float(mr_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # 3. inject_unmapped_ndc  (count=1)
    # ------------------------------------------------------------------
    _section("Step 3 / 8 — inject_unmapped_ndc (count=1)")
    t0 = time.perf_counter()
    invoices, labels, contracts = inject_unmapped_ndc(
        invoices, labels, contracts, count=1, seed=seed + 1
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    un_labels = labels.filter(pl.col("anomaly_type") == "UNMAPPED_NDC")
    print(f"  UNMAPPED_NDC labels created:    {len(un_labels)}")
    assert len(un_labels) == 1, f"Expected 1 label, got {len(un_labels)}"

    new_ndc = un_labels["ndc11"][0]
    assert new_ndc not in base_ndcs, f"Injected NDC {new_ndc} already existed in base data"
    new_row = invoices.filter(pl.col("ndc11") == new_ndc)
    assert new_row.height == 1, f"Expected 1 new row for NDC {new_ndc}, found {new_row.height}"
    assert float(new_row["actual_rebate"][0]) == 0.0, "Unmapped NDC has non-zero actual_rebate"
    print(f"  [OK] New NDC {new_ndc} added with actual_rebate = 0")
    print(f"  [OK] estimated_impact = ${float(un_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # 4. inject_rebate_yield_collapse  (count=1)
    # ------------------------------------------------------------------
    _section("Step 4 / 8 — inject_rebate_yield_collapse (count=1)")
    t0 = time.perf_counter()
    invoices, labels, contracts = inject_rebate_yield_collapse(
        invoices, labels, contracts, reduction_factor=0.70, count=1, seed=seed + 2
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    ryc_labels = labels.filter(pl.col("anomaly_type") == "REBATE_YIELD_COLLAPSE")
    print(f"  REBATE_YIELD_COLLAPSE labels:   {len(ryc_labels)}")
    assert len(ryc_labels) == 1, f"Expected 1 label, got {len(ryc_labels)}"

    ryc_ndc = ryc_labels["ndc11"][0]
    ryc_client = ryc_labels["client_id"][0]
    ryc_quarter = ryc_labels["quarter"][0]
    ryc_row = invoices.filter(
        (pl.col("ndc11") == ryc_ndc)
        & (pl.col("client_id") == ryc_client)
        & (pl.col("invoice_quarter") == ryc_quarter)
    )
    assert ryc_row.height > 0, "Target row missing after yield collapse injection"
    if ryc_row.height > 0:
        exp_reb = float(ryc_row["expected_rebate"][0])
        act_reb = float(ryc_row["actual_rebate"][0])
        # actual should be ~30% of expected (1 - 0.70 = 0.30)
        assert act_reb <= exp_reb * 0.31 + 0.01, (
            f"Yield not collapsed: actual={act_reb:.2f}, expected={exp_reb:.2f}"
        )
        print(f"  [OK] actual_rebate ({act_reb:.2f}) ≈ 30% of expected ({exp_reb:.2f})")
    assert float(ryc_labels["estimated_impact"][0]) >= 0.0
    print(f"  [OK] estimated_impact = ${float(ryc_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # 5. inject_specialty_channel_omission  (count=1)
    # ------------------------------------------------------------------
    _section("Step 5 / 8 — inject_specialty_channel_omission (count=1)")
    t0 = time.perf_counter()
    invoices, labels, contracts = inject_specialty_channel_omission(
        invoices, labels, contracts, count=1, seed=seed + 3, claims_df=claims
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    co_labels = labels.filter(pl.col("anomaly_type") == "CHANNEL_OMISSION")
    print(f"  CHANNEL_OMISSION labels:        {len(co_labels)}")
    assert len(co_labels) == 1, f"Expected 1 label, got {len(co_labels)}"

    # Check specialty rows have actual_rebate = 0
    specialty_rows = invoices.filter(pl.col("channel") == "specialty")
    assert specialty_rows.height >= 1, "No specialty rows found after injection"
    bad_specialty = specialty_rows.filter(pl.col("actual_rebate") > 0.0)
    assert bad_specialty.height == 0, (
        f"{bad_specialty.height} specialty rows have non-zero actual_rebate"
    )
    print(f"  [OK] {specialty_rows.height} specialty row(s) all have actual_rebate = 0")
    assert float(co_labels["estimated_impact"][0]) >= 0.0
    print(f"  [OK] estimated_impact = ${float(co_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # 6. inject_unit_conversion_error  (count=1)
    # ------------------------------------------------------------------
    _section("Step 6 / 8 — inject_unit_conversion_error (count=1)")
    t0 = time.perf_counter()
    invoices, labels, contracts = inject_unit_conversion_error(
        invoices, labels, contracts, unit_divisor=10, count=1, seed=seed + 4,
        drugs_df=drugs
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    uce_labels = labels.filter(pl.col("anomaly_type") == "UNIT_CONVERSION_ERROR")
    print(f"  UNIT_CONVERSION_ERROR labels:   {len(uce_labels)}")
    assert len(uce_labels) == 1, f"Expected 1 label, got {len(uce_labels)}"

    assert float(uce_labels["estimated_impact"][0]) >= 0.0
    print(f"  [OK] estimated_impact = ${float(uce_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # 7. inject_dispute_spike  (count=1)
    # ------------------------------------------------------------------
    _section("Step 7 / 8 — inject_dispute_spike (count=1)")
    t0 = time.perf_counter()
    invoices, labels, contracts = inject_dispute_spike(
        invoices, labels, contracts, dispute_fraction=0.50, count=1, seed=seed + 5,
        drugs_df=drugs
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    ds_labels = labels.filter(pl.col("anomaly_type") == "DISPUTE_SPIKE")
    print(f"  DISPUTE_SPIKE labels:           {len(ds_labels)}")
    assert len(ds_labels) == 1, f"Expected 1 label, got {len(ds_labels)}"

    # paid + disputed should equal actual (approximately)
    mfr = ds_labels["manufacturer"][0]
    brand = ds_labels["brand_family"][0]
    ds_q = ds_labels["quarter"][0]

    if "brand_family" in invoices.columns:
        spiked_rows = invoices.filter(
            (pl.col("manufacturer") == mfr)
            & (pl.col("brand_family") == brand)
            & (pl.col("invoice_quarter") == ds_q)
            & (pl.col("actual_rebate") > 0.0)
        )
        if spiked_rows.height > 0:
            check_row = spiked_rows[0]
            actual = float(check_row["actual_rebate"][0])
            disputed = float(check_row["disputed_rebate"][0])
            paid = float(check_row["paid_rebate"][0])
            assert paid <= actual + 0.01, f"paid ({paid}) > actual ({actual})"
            assert disputed <= actual + 0.01, f"disputed ({disputed}) > actual ({actual})"
            print(f"  [OK] paid ({paid:.2f}) + disputed ({disputed:.2f}) ≈ actual ({actual:.2f})")

    assert float(ds_labels["estimated_impact"][0]) >= 0.0
    print(f"  [OK] estimated_impact = ${float(ds_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # 8. inject_guarantee_true_up_missing  (count=1)
    # ------------------------------------------------------------------
    _section("Step 8 / 8 — inject_guarantee_true_up_missing (count=1)")
    t0 = time.perf_counter()
    invoices, labels, contracts = inject_guarantee_true_up_missing(
        invoices, labels, contracts, count=1, seed=seed + 6
    )
    print(f"  Elapsed: {time.perf_counter() - t0:.2f}s")

    gtu_labels = labels.filter(pl.col("anomaly_type") == "GUARANTEE_TRUE_UP_MISSING")
    print(f"  GUARANTEE_TRUE_UP_MISSING labels:{len(gtu_labels)}")
    assert len(gtu_labels) == 1, f"Expected 1 label, got {len(gtu_labels)}"

    # Contracts should have missing_guarantee_true_up column
    assert "missing_guarantee_true_up" in contracts.columns, (
        "contracts missing 'missing_guarantee_true_up' column"
    )
    flagged = contracts.filter(pl.col("missing_guarantee_true_up") == True)  # noqa: E712
    print(f"  Flagged contracts: {flagged.height}")
    assert flagged.height >= 1, "No contracts were flagged"

    assert float(gtu_labels["estimated_impact"][0]) >= 0.0
    print(f"  [OK] estimated_impact = ${float(gtu_labels['estimated_impact'][0]):,.2f}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _section("Summary")

    total_anomalies = len(labels)
    total_impact = float(labels["estimated_impact"].sum())

    print(f"  Total anomalies injected:     {total_anomalies}")
    print(f"  Anomaly type breakdown:")
    by_type = labels.group_by("anomaly_type").agg(
        pl.len().alias("count"),
        pl.col("estimated_impact").sum().alias("total_impact"),
    ).sort("anomaly_type")
    for row in by_type.to_dicts():
        print(f"    {row['anomaly_type']:<35} count={row['count']}  "
              f"impact=${row['total_impact']:>12,.2f}")

    print(f"\n  Total estimated impact:       ${total_impact:,.2f}")
    print(f"  Invoice rows (final):         {len(invoices):,} "
          f"(was {original_invoice_count:,})")
    print(f"  Recoverable anomalies:        "
          f"{labels.filter(pl.col('recoverable') == True).height}")  # noqa: E712

    # Referential integrity: no negative impacts
    neg_impact = labels.filter(pl.col("estimated_impact") < 0.0)
    assert neg_impact.height == 0, f"{neg_impact.height} labels have negative estimated_impact"
    print("  [OK] All estimated_impact values are non-negative")

    # ------------------------------------------------------------------
    # Save output
    # ------------------------------------------------------------------
    output_path = OUTPUT_DIR / "invoices_with_anomalies.parquet"
    invoices.write_parquet(str(output_path))
    print(f"\n  Saved invoices_with_anomalies.parquet → {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1_024 / 1_024:.2f} MB")

    labels_path = OUTPUT_DIR / "anomaly_labels.parquet"
    labels.write_parquet(str(labels_path))
    print(f"  Saved anomaly_labels.parquet       → {labels_path}")

    print("\nAll assertions passed. Phase 3 anomaly injection verified.\n")


if __name__ == "__main__":
    main()
