"""
Orchestration module for the synthetic Rx rebate data generation system.

Coordinates all generators, anomaly injectors, and validation checks to
produce a complete synthetic dataset and save it to disk as parquet files.

Usage:
    >>> from synthetic_data_gen.runner import generate_and_save
    >>> results = generate_and_save(
    ...     config_path="configs/base.yaml",
    ...     anomaly_config_path="configs/anomaly_scenarios.yaml",
    ...     output_dir="data/synthetic",
    ...     seed=42,
    ... )
    >>> print(results["claims_count"])
    500000
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def generate_and_save(
    config_path: str = "configs/base.yaml",
    anomaly_config_path: str = "configs/anomaly_scenarios.yaml",
    output_dir: str = "data/synthetic",
    seed: int = 42,
    inject_anomalies: bool = True,
    run_validation: bool = True,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Generate complete synthetic Rx rebate dataset and save to output directory.

    Coordinates all five generators (claims, drugs, formulary, contracts,
    invoices), optional anomaly injection, optional validation, and writes
    every table to a parquet file.  Returns a summary dictionary with file
    paths, row counts, validation results, timing, and estimated recoverable
    dollar impact.

    Args:
        config_path: Path to base.yaml config file.
        anomaly_config_path: Path to anomaly_scenarios.yaml config file.
        output_dir: Directory to save output parquet files.
        seed: Integer random seed for full reproducibility.
        inject_anomalies: If True, inject anomaly scenarios from
            anomaly_config_path into the invoice data.
        run_validation: If True, run all validation checks after generation.
        verbose: If True, print progress messages to stdout.

    Returns:
        Dictionary with keys:
        - ``claims_path``, ``drugs_path``, ``formulary_path``,
          ``contracts_path``, ``invoices_path``, ``labels_path`` (str)
        - ``claims_count``, ``drugs_count``, ``formulary_count``,
          ``contracts_count``, ``invoices_count``, ``labels_count`` (int)
        - ``validation_results`` (dict, only present when run_validation=True)
        - ``generation_time_seconds`` (float)
        - ``estimated_recoverable_dollars`` (float)

    Raises:
        FileNotFoundError: If config_path or anomaly_config_path does not
            exist (raised by the config loader).
        OSError: If output_dir cannot be created.
    """
    from synthetic_data_gen.config import load_config, load_anomaly_scenarios
    from synthetic_data_gen.generate_claims import ClaimsGenerator
    from synthetic_data_gen.generate_drugs import DrugGenerator
    from synthetic_data_gen.generate_formulary import FormularyGenerator
    from synthetic_data_gen.generate_contracts import ContractGenerator
    from synthetic_data_gen.generate_invoices import InvoiceGenerator
    from synthetic_data_gen.inject_anomalies import inject_scenario, make_empty_labels_df
    from synthetic_data_gen.validate import run_all_validations

    start_time = time.time()

    # ------------------------------------------------------------------
    # Step 1: Load configs
    # ------------------------------------------------------------------
    cfg = load_config(config_path)
    # Override the config's seed with the caller-supplied seed so that the
    # seed argument is the single source of truth for reproducibility.
    cfg.random_seed = seed

    scenarios = []
    if inject_anomalies:
        scenarios = load_anomaly_scenarios(anomaly_config_path)

    # ------------------------------------------------------------------
    # Step 2: Create output directory
    # ------------------------------------------------------------------
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 3: Generate claims
    # ------------------------------------------------------------------
    if verbose:
        print(f"Generating claims... ({cfg.n_claims:,} rows)")
    claims = ClaimsGenerator(cfg, seed=seed).generate()

    # ------------------------------------------------------------------
    # Step 4: Generate drugs
    # ------------------------------------------------------------------
    if verbose:
        print(f"Generating drugs... ({len(claims['ndc11'].unique())} rows)")
    drugs = DrugGenerator(cfg, claims, seed=seed).generate()

    # ------------------------------------------------------------------
    # Step 5: Generate formulary
    # ------------------------------------------------------------------
    formulary = FormularyGenerator(cfg, claims, drugs, seed=seed).generate()
    if verbose:
        print(f"Generating formulary... ({len(formulary):,} rows)")

    # ------------------------------------------------------------------
    # Step 6: Generate contracts
    # ------------------------------------------------------------------
    contracts = ContractGenerator(cfg, drugs, seed=seed).generate()
    if verbose:
        print(f"Generating contracts... ({len(contracts):,} rows)")

    # ------------------------------------------------------------------
    # Step 7: Generate invoices
    # ------------------------------------------------------------------
    invoices = InvoiceGenerator(
        cfg, claims, contracts, drugs, formulary, seed=seed
    ).generate()
    if verbose:
        print(f"Generating invoices... ({len(invoices):,} rows)")

    # ------------------------------------------------------------------
    # Step 8: Optionally inject anomalies
    # ------------------------------------------------------------------
    labels = make_empty_labels_df()

    if inject_anomalies and scenarios:
        for i, scenario in enumerate(scenarios):
            # Stagger the per-scenario seed to avoid identical sampling
            scenario_seed = seed + i
            invoices, labels, contracts = inject_scenario(
                invoice_df=invoices,
                labels_df=labels,
                contracts_df=contracts,
                scenario_config=scenario,
                seed=scenario_seed,
                drugs_df=drugs,
                claims_df=claims,
            )

        estimated_impact = (
            float(labels["estimated_impact"].sum())
            if len(labels) > 0
            else 0.0
        )
        n_anomalies = len(labels)
        if verbose:
            print(
                f"Injecting anomalies... "
                f"({n_anomalies} anomalies, ${estimated_impact:,.2f} estimated impact)"
            )
    else:
        estimated_impact = 0.0

    # ------------------------------------------------------------------
    # Step 9: Optionally run validation checks
    # ------------------------------------------------------------------
    validation_results: dict[str, Any] = {}
    if run_validation:
        raw_results = run_all_validations(
            claims=claims,
            drugs=drugs,
            formulary=formulary,
            contracts=contracts,
            invoices=invoices,
            labels=labels if len(labels) > 0 else None,
        )
        # Summarise to a JSON-serialisable dict: {check_name: {"passed": bool, "messages": [...]}}
        validation_results = {
            name: {"passed": passed, "messages": messages}
            for name, (passed, messages) in raw_results.items()
        }
        n_checks = len(raw_results)
        n_passed = sum(1 for passed, _ in raw_results.values() if passed)
        all_passed = n_passed == n_checks
        if verbose:
            status = "all passed" if all_passed else f"{n_checks - n_passed} failed"
            print(f"Running validation checks... ({n_checks} checks, {status})")

    # ------------------------------------------------------------------
    # Step 10: Save all DataFrames as parquet
    # ------------------------------------------------------------------
    claims_path = out_path / "claims.parquet"
    drugs_path = out_path / "drugs.parquet"
    formulary_path = out_path / "formulary.parquet"
    contracts_path = out_path / "contracts.parquet"
    invoices_path = out_path / "invoices.parquet"
    labels_path = out_path / "anomaly_labels.parquet"

    claims.write_parquet(claims_path)
    drugs.write_parquet(drugs_path)
    formulary.write_parquet(formulary_path)
    contracts.write_parquet(contracts_path)
    invoices.write_parquet(invoices_path)
    labels.write_parquet(labels_path)

    if verbose:
        print(f"Saved outputs to {output_dir}/")

    # ------------------------------------------------------------------
    # Step 11: Build summary report
    # ------------------------------------------------------------------
    elapsed = time.time() - start_time

    summary: dict[str, Any] = {
        # File paths
        "claims_path": str(claims_path),
        "drugs_path": str(drugs_path),
        "formulary_path": str(formulary_path),
        "contracts_path": str(contracts_path),
        "invoices_path": str(invoices_path),
        "labels_path": str(labels_path),
        # Row counts
        "claims_count": len(claims),
        "drugs_count": len(drugs),
        "formulary_count": len(formulary),
        "contracts_count": len(contracts),
        "invoices_count": len(invoices),
        "labels_count": len(labels),
        # Timing and impact
        "generation_time_seconds": round(elapsed, 2),
        "estimated_recoverable_dollars": round(estimated_impact, 2),
    }

    if run_validation:
        summary["validation_results"] = validation_results

    if verbose:
        print(
            f"\nGeneration complete in {elapsed:.1f}s  |  "
            f"${estimated_impact:,.2f} estimated recoverable"
        )

    return summary
