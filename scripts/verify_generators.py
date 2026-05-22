"""
Verification script for Phase 2 synthetic data generators.

Loads the base config, generates all 5 tables, performs basic consistency
checks, and prints a summary. Saves small sample CSVs for manual inspection.

Usage:
    cd /Users/zacklarsen/workspace/anomaly-detection
    python scripts/verify_generators.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import polars as pl

# Ensure project root is on sys.path when running directly
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

CONFIG_PATH = ROOT / "configs" / "base.yaml"
SAMPLE_DIR = ROOT / "data" / "samples"


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Phase 2 Synthetic Data Generator Verification")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Load config
    # ------------------------------------------------------------------
    cfg = load_config(str(CONFIG_PATH))
    print(f"\nConfig loaded: n_claims={cfg.n_claims:,}, n_ndcs={cfg.n_ndcs}, "
          f"n_groups={cfg.n_groups}, n_manufacturers={cfg.n_manufacturers}")
    print(f"Date range: {cfg.date_range.start} to {cfg.date_range.end}")

    seed = cfg.random_seed

    # ------------------------------------------------------------------
    # 1. Claims
    # ------------------------------------------------------------------
    print("\n[1/5] Generating claims...", flush=True)
    t0 = time.perf_counter()
    claims_gen = ClaimsGenerator(cfg, seed=seed)
    claims = claims_gen.generate()
    t1 = time.perf_counter()
    print(f"      Done in {t1 - t0:.1f}s")
    print(f"      Rows: {len(claims):,}")
    print(f"      Columns: {claims.columns}")
    print(f"      Unique NDCs: {claims['ndc11'].n_unique()}")
    print(f"      Unique groups: {claims['group_id'].n_unique()}")
    print(f"      Channel mix:\n{claims['channel'].value_counts().sort('channel')}")
    print(f"      Days supply mix:\n{claims['days_supply'].value_counts().sort('days_supply')}")
    print(f"      Claim status:\n{claims['claim_status'].value_counts().sort('claim_status')}")
    print(f"      plan_paid range: [{claims['plan_paid'].min():.2f}, {claims['plan_paid'].max():.2f}]")
    print(f"      gross_drug_cost range: [{claims['gross_drug_cost'].min():.2f}, {claims['gross_drug_cost'].max():.2f}]")

    # Verify plan_paid <= gross_drug_cost
    violation_count = claims.filter(
        (claims["plan_paid"] - claims["gross_drug_cost"]) > 0.01
    ).height
    assert violation_count == 0, f"plan_paid > gross_drug_cost for {violation_count} rows"
    print("      [OK] plan_paid <= gross_drug_cost for all rows")

    claims.head(100).write_csv(SAMPLE_DIR / "claims_sample.csv")

    # ------------------------------------------------------------------
    # 2. Drugs
    # ------------------------------------------------------------------
    print("\n[2/5] Generating drug master...", flush=True)
    t0 = time.perf_counter()
    drug_gen = DrugGenerator(cfg, claims, seed=seed)
    drugs = drug_gen.generate()
    t1 = time.perf_counter()
    print(f"      Done in {t1 - t0:.1f}s")
    print(f"      Rows: {len(drugs):,} (unique NDCs)")
    print(f"      Columns: {drugs.columns}")
    print(f"      Unique manufacturers: {drugs['manufacturer'].n_unique()}")
    print(f"      Unique brand families: {drugs['brand_family'].n_unique()}")
    print(f"      Specialty NDCs: {drugs['specialty_flag'].sum()} "
          f"({drugs['specialty_flag'].mean() * 100:.1f}%)")
    print(f"      Unique GPI classes: {drugs['gpi_class'].n_unique()}")

    # Verify all claim NDCs are in drugs
    claim_ndcs = set(claims["ndc11"].to_list())
    drug_ndcs = set(drugs["ndc11"].to_list())
    missing_ndcs = claim_ndcs - drug_ndcs
    assert len(missing_ndcs) == 0, f"{len(missing_ndcs)} claim NDCs missing from drugs"
    print("      [OK] All claim NDCs present in drug master")

    drugs.write_csv(SAMPLE_DIR / "drugs_sample.csv")

    # ------------------------------------------------------------------
    # 3. Formulary
    # ------------------------------------------------------------------
    print("\n[3/5] Generating formulary...", flush=True)
    t0 = time.perf_counter()
    form_gen = FormularyGenerator(cfg, claims, drugs, seed=seed)
    formulary = form_gen.generate()
    t1 = time.perf_counter()
    print(f"      Done in {t1 - t0:.1f}s")
    print(f"      Rows: {len(formulary):,}")
    print(f"      Columns: {formulary.columns}")
    print(f"      Tier distribution:\n{formulary['tier'].value_counts().sort('tier')}")
    print(f"      Preferred: {formulary['preferred_flag'].sum():,} "
          f"({formulary['preferred_flag'].mean() * 100:.1f}%)")
    print(f"      PA required: {formulary['pa_required'].sum():,} "
          f"({formulary['pa_required'].mean() * 100:.1f}%)")

    # Verify all formulary NDCs exist in drugs
    form_ndcs = set(formulary["ndc11"].to_list())
    bad_ndcs = form_ndcs - drug_ndcs
    assert len(bad_ndcs) == 0, f"{len(bad_ndcs)} formulary NDCs not in drug master"
    print("      [OK] All formulary NDCs present in drug master")

    # Coverage check: ~70% of (client, NDC) pairs
    all_pairs_count = (
        claims.select(["group_id", "ndc11"]).unique().height
    )
    covered_fraction = len(formulary) / all_pairs_count
    print(f"      Coverage: {covered_fraction:.1%} of (client, NDC) pairs "
          f"({all_pairs_count:,} total pairs)")
    assert 0.60 <= covered_fraction <= 0.80, (
        f"Expected ~70% formulary coverage, got {covered_fraction:.1%}"
    )
    print("      [OK] Formulary coverage within expected range (60–80%)")

    formulary.head(200).write_csv(SAMPLE_DIR / "formulary_sample.csv")

    # ------------------------------------------------------------------
    # 4. Contracts
    # ------------------------------------------------------------------
    print("\n[4/5] Generating contracts...", flush=True)
    t0 = time.perf_counter()
    contract_gen = ContractGenerator(cfg, drugs, seed=seed)
    contracts = contract_gen.generate()
    t1 = time.perf_counter()
    print(f"      Done in {t1 - t0:.1f}s")
    print(f"      Rows: {len(contracts):,}")
    print(f"      Columns: {contracts.columns}")
    print(f"      Unique manufacturers in contracts: {contracts['manufacturer'].n_unique()}")
    print(f"      Unique brands in contracts: {contracts['brand_family'].n_unique()}")
    print(f"      Rebate basis mix:\n{contracts['rebate_basis'].value_counts().sort('rebate_basis')}")

    # Verify contracts reference existing manufacturers
    drug_mfrs = set(drugs["manufacturer"].to_list())
    contract_mfrs = set(contracts["manufacturer"].to_list())
    bad_mfrs = contract_mfrs - drug_mfrs
    assert len(bad_mfrs) == 0, f"Contracts reference unknown manufacturers: {bad_mfrs}"
    print("      [OK] All contract manufacturers present in drug master")

    # PMPM contracts must have minimum_guarantee
    pmpm_rows = contracts.filter(contracts["rebate_basis"] == "PMPM_GUARANTEE")
    pmpm_no_guarantee = pmpm_rows.filter(
        pmpm_rows["minimum_guarantee"].is_null()
    ).height
    assert pmpm_no_guarantee == 0, (
        f"{pmpm_no_guarantee} PMPM contracts missing minimum_guarantee"
    )
    print("      [OK] All PMPM contracts have minimum_guarantee set")

    # Serialize list columns to JSON strings for CSV output
    contracts_csv = contracts.head(200).with_columns(
        pl.col("channel_exclusions").list.join("|").alias("channel_exclusions"),
        pl.col("lob_exclusions").list.join("|").alias("lob_exclusions"),
    )
    contracts_csv.write_csv(SAMPLE_DIR / "contracts_sample.csv")

    # ------------------------------------------------------------------
    # 5. Invoices
    # ------------------------------------------------------------------
    print("\n[5/5] Generating invoices...", flush=True)
    t0 = time.perf_counter()
    inv_gen = InvoiceGenerator(cfg, claims, contracts, drugs, formulary, seed=seed)
    invoices = inv_gen.generate()
    t1 = time.perf_counter()
    print(f"      Done in {t1 - t0:.1f}s")
    print(f"      Rows: {len(invoices):,}")
    print(f"      Columns: {invoices.columns}")
    print(f"      Unique quarters: {invoices['invoice_quarter'].n_unique()}")
    quarters = sorted(invoices["invoice_quarter"].unique().to_list())
    print(f"      Quarters: {quarters}")
    print(f"      Total expected_rebate: ${invoices['expected_rebate'].sum():,.0f}")
    print(f"      Total actual_rebate:   ${invoices['actual_rebate'].sum():,.0f}")
    print(f"      Total paid_rebate:     ${invoices['paid_rebate'].sum():,.0f}")
    print(f"      Total disputed_rebate: ${invoices['disputed_rebate'].sum():,.0f}")

    # Verify disputed <= actual and paid <= actual
    disputes_violation = invoices.filter(
        (invoices["disputed_rebate"] - invoices["actual_rebate"]) > 0.01
    ).height
    paid_violation = invoices.filter(
        (invoices["paid_rebate"] - invoices["actual_rebate"]) > 0.01
    ).height
    assert disputes_violation == 0, f"{disputes_violation} rows: disputed > actual"
    assert paid_violation == 0, f"{paid_violation} rows: paid > actual"
    print("      [OK] disputed_rebate <= actual_rebate for all rows")
    print("      [OK] paid_rebate <= actual_rebate for all rows")

    invoices.head(200).write_csv(SAMPLE_DIR / "invoices_sample.csv")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Claims:    {len(claims):>10,} rows")
    print(f"  Drugs:     {len(drugs):>10,} rows  ({drugs['manufacturer'].n_unique()} manufacturers)")
    print(f"  Formulary: {len(formulary):>10,} rows  ({formulary['client_id'].n_unique()} clients)")
    print(f"  Contracts: {len(contracts):>10,} rows  ({contracts['rebate_basis'].n_unique()} rebate basis types)")
    print(f"  Invoices:  {len(invoices):>10,} rows  ({invoices['invoice_quarter'].n_unique()} quarters)")
    print(f"\nSample CSVs saved to: {SAMPLE_DIR}")
    print("\nAll assertions passed. Phase 2 generators verified.")


if __name__ == "__main__":
    main()
