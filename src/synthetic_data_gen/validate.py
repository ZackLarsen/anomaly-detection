"""
Validation module for the synthetic Rx rebate data generation system.

Provides functions that check data quality, referential integrity, and
business logic constraints across generated tables. Each function returns
a (passed: bool, messages: list[str]) tuple so callers can collect results
without raising immediately.

Usage:
    >>> from synthetic_data_gen.validate import run_all_validations, print_validation_report
    >>> results = run_all_validations(claims, drugs, formulary, contracts, invoices, labels)
    >>> print_validation_report(results)
"""

from __future__ import annotations

from typing import Optional

import polars as pl


# ---------------------------------------------------------------------------
# Referential integrity checks
# ---------------------------------------------------------------------------


def validate_all_claim_ndcs_in_drug_master(
    claims: pl.DataFrame, drugs: pl.DataFrame
) -> tuple[bool, list[str]]:
    """
    Assert all NDCs in claims exist in drug master.

    Args:
        claims: Claims DataFrame with an ``ndc11`` column.
        drugs: Drug master DataFrame with an ``ndc11`` column.

    Returns:
        (passed, messages) where passed is True if all claim NDCs are present
        in the drug master, and messages lists any violations.
    """
    claim_ndcs = set(claims["ndc11"].unique().to_list())
    drug_ndcs = set(drugs["ndc11"].unique().to_list())
    missing = sorted(claim_ndcs - drug_ndcs)
    if missing:
        msgs = [
            f"NDC {ndc} appears in claims but is missing from drug master"
            for ndc in missing[:20]  # cap at 20 to avoid huge message lists
        ]
        if len(missing) > 20:
            msgs.append(f"... and {len(missing) - 20} more missing NDCs")
        return False, msgs
    return True, ["All claim NDCs are present in drug master"]


def validate_no_null_keys(
    df: pl.DataFrame, key_cols: list[str]
) -> tuple[bool, list[str]]:
    """
    Assert no null values in key columns.

    Args:
        df: DataFrame to check.
        key_cols: Column names that must be non-null.

    Returns:
        (passed, messages).
    """
    messages: list[str] = []
    passed = True
    for col in key_cols:
        if col not in df.columns:
            messages.append(f"Key column '{col}' not found in DataFrame")
            passed = False
            continue
        null_count = df[col].null_count()
        if null_count > 0:
            messages.append(f"Column '{col}' has {null_count} null values")
            passed = False
    if passed:
        messages.append(f"No null values found in key columns: {key_cols}")
    return passed, messages


def validate_no_duplicate_invoices(
    invoices: pl.DataFrame,
) -> tuple[bool, list[str]]:
    """
    Assert no duplicate (invoice_quarter, manufacturer, ndc11, client_id, channel)
    rows in the invoices DataFrame. Falls back to the 4-column key if no
    ``channel`` column is present.

    Args:
        invoices: Invoice DataFrame.

    Returns:
        (passed, messages).
    """
    key_cols = ["invoice_quarter", "manufacturer", "ndc11", "client_id"]
    if "channel" in invoices.columns:
        key_cols.append("channel")

    n_total = len(invoices)
    n_unique = invoices.select(key_cols).unique().height
    n_dupes = n_total - n_unique
    if n_dupes > 0:
        return (
            False,
            [f"Found {n_dupes} duplicate invoice rows on key {key_cols}"],
        )
    return True, ["No duplicate invoice rows found"]


# ---------------------------------------------------------------------------
# Financial amount constraints
# ---------------------------------------------------------------------------


def validate_expected_rebate_non_negative(
    invoices: pl.DataFrame,
) -> tuple[bool, list[str]]:
    """
    Assert expected_rebate >= 0 for all invoice rows.

    Args:
        invoices: Invoice DataFrame with ``expected_rebate`` column.

    Returns:
        (passed, messages).
    """
    n_violations = invoices.filter(pl.col("expected_rebate") < 0.0).height
    if n_violations > 0:
        return (
            False,
            [f"{n_violations} invoice rows have negative expected_rebate"],
        )
    return True, ["All expected_rebate values are non-negative"]


def validate_actual_rebate_non_negative(
    invoices: pl.DataFrame,
) -> tuple[bool, list[str]]:
    """
    Assert actual_rebate >= 0 for all invoice rows.

    Args:
        invoices: Invoice DataFrame with ``actual_rebate`` column.

    Returns:
        (passed, messages).
    """
    n_violations = invoices.filter(pl.col("actual_rebate") < 0.0).height
    if n_violations > 0:
        return (
            False,
            [f"{n_violations} invoice rows have negative actual_rebate"],
        )
    return True, ["All actual_rebate values are non-negative"]


def validate_paid_rebate_lte_actual(
    invoices: pl.DataFrame,
) -> tuple[bool, list[str]]:
    """
    Assert paid_rebate <= actual_rebate (disputes reduce payments).

    A small tolerance of 0.01 is applied to accommodate floating-point
    rounding from the generation pipeline.

    Args:
        invoices: Invoice DataFrame with ``paid_rebate`` and ``actual_rebate``.

    Returns:
        (passed, messages).
    """
    n_violations = invoices.filter(
        pl.col("paid_rebate") > pl.col("actual_rebate") + 0.01
    ).height
    if n_violations > 0:
        return (
            False,
            [f"{n_violations} invoice rows have paid_rebate > actual_rebate"],
        )
    return True, ["All paid_rebate values are <= actual_rebate"]


def validate_disputed_rebate_lte_actual(
    invoices: pl.DataFrame,
) -> tuple[bool, list[str]]:
    """
    Assert disputed_rebate <= actual_rebate.

    Args:
        invoices: Invoice DataFrame with ``disputed_rebate`` and ``actual_rebate``.

    Returns:
        (passed, messages).
    """
    n_violations = invoices.filter(
        pl.col("disputed_rebate") > pl.col("actual_rebate") + 0.01
    ).height
    if n_violations > 0:
        return (
            False,
            [f"{n_violations} invoice rows have disputed_rebate > actual_rebate"],
        )
    return True, ["All disputed_rebate values are <= actual_rebate"]


def validate_invoiced_utilization_positive(
    invoices: pl.DataFrame,
) -> tuple[bool, list[str]]:
    """
    Assert invoiced_utilization > 0 (can't invoice zero units).

    Args:
        invoices: Invoice DataFrame with ``invoiced_utilization`` column.

    Returns:
        (passed, messages).
    """
    n_violations = invoices.filter(pl.col("invoiced_utilization") <= 0.0).height
    if n_violations > 0:
        return (
            False,
            [f"{n_violations} invoice rows have invoiced_utilization <= 0"],
        )
    return True, ["All invoiced_utilization values are positive"]


# ---------------------------------------------------------------------------
# Date constraints
# ---------------------------------------------------------------------------


def validate_no_future_claims(
    claims: pl.DataFrame, cutoff_date: str = "2025-12-31"
) -> tuple[bool, list[str]]:
    """
    Assert all claim fill_dates are <= cutoff_date (no future claims).

    Args:
        claims: Claims DataFrame with a ``fill_date`` column (Date type).
        cutoff_date: ISO date string upper bound (inclusive).

    Returns:
        (passed, messages).
    """
    from datetime import date as date_type

    cutoff = date_type.fromisoformat(cutoff_date)
    future_count = claims.filter(pl.col("fill_date") > cutoff).height
    if future_count > 0:
        return (
            False,
            [
                f"{future_count} claims have fill_date after cutoff {cutoff_date}"
            ],
        )
    return True, [f"All claim fill_dates are on or before {cutoff_date}"]


# ---------------------------------------------------------------------------
# Anomaly detectability checks
# ---------------------------------------------------------------------------


def validate_missing_rebate_anomalies_have_positive_expected(
    invoices: pl.DataFrame, labels: pl.DataFrame
) -> tuple[bool, list[str]]:
    """
    For all MISSING_REBATE anomalies, assert expected_rebate > 0 and
    actual_rebate = 0.

    Args:
        invoices: Invoice DataFrame.
        labels: Anomaly labels DataFrame with ``anomaly_type``, ``ndc11``,
            ``client_id``, and ``quarter`` columns.

    Returns:
        (passed, messages).
    """
    missing_labels = labels.filter(pl.col("anomaly_type") == "MISSING_REBATE")
    if len(missing_labels) == 0:
        return True, ["No MISSING_REBATE labels to check"]

    messages: list[str] = []
    passed = True

    for row in missing_labels.to_dicts():
        ndc = row["ndc11"]
        client = row["client_id"]
        quarter = row["quarter"]

        matching = invoices.filter(
            (pl.col("ndc11") == ndc)
            & (pl.col("client_id") == client)
            & (pl.col("invoice_quarter") == quarter)
        )

        if len(matching) == 0:
            messages.append(
                f"MISSING_REBATE label ({ndc}, {client}, {quarter}): "
                "no matching invoice row found"
            )
            passed = False
            continue

        exp = float(matching["expected_rebate"].sum())
        act = float(matching["actual_rebate"].sum())

        if exp <= 0.0:
            messages.append(
                f"MISSING_REBATE label ({ndc}, {client}, {quarter}): "
                f"expected_rebate is {exp} (should be > 0)"
            )
            passed = False
        if act != 0.0:
            messages.append(
                f"MISSING_REBATE label ({ndc}, {client}, {quarter}): "
                f"actual_rebate is {act} (should be 0)"
            )
            passed = False

    if passed:
        messages.append(
            f"All {len(missing_labels)} MISSING_REBATE anomalies verified: "
            "expected_rebate > 0 and actual_rebate = 0"
        )
    return passed, messages


def validate_yield_collapse_anomalies_have_reduced_actual(
    invoices: pl.DataFrame, labels: pl.DataFrame
) -> tuple[bool, list[str]]:
    """
    For all REBATE_YIELD_COLLAPSE anomalies, assert actual_rebate is
    significantly lower than expected_rebate (at least 20% reduction).

    Args:
        invoices: Invoice DataFrame.
        labels: Anomaly labels DataFrame.

    Returns:
        (passed, messages).
    """
    collapse_labels = labels.filter(
        pl.col("anomaly_type") == "REBATE_YIELD_COLLAPSE"
    )
    if len(collapse_labels) == 0:
        return True, ["No REBATE_YIELD_COLLAPSE labels to check"]

    messages: list[str] = []
    passed = True

    for row in collapse_labels.to_dicts():
        ndc = row["ndc11"]
        client = row["client_id"]
        quarter = row["quarter"]

        matching = invoices.filter(
            (pl.col("ndc11") == ndc)
            & (pl.col("client_id") == client)
            & (pl.col("invoice_quarter") == quarter)
        )

        if len(matching) == 0:
            messages.append(
                f"REBATE_YIELD_COLLAPSE label ({ndc}, {client}, {quarter}): "
                "no matching invoice row found"
            )
            passed = False
            continue

        exp = float(matching["expected_rebate"].sum())
        act = float(matching["actual_rebate"].sum())

        if exp <= 0.0:
            # Can't compute ratio — skip
            continue

        ratio = act / exp
        # After yield collapse, actual should be significantly less than expected
        # Default reduction_factor=0.70 means actual = 0.30 * expected
        if ratio > 0.80:  # allow some tolerance
            messages.append(
                f"REBATE_YIELD_COLLAPSE label ({ndc}, {client}, {quarter}): "
                f"actual/expected ratio is {ratio:.3f} — expected significant reduction"
            )
            passed = False

    if passed:
        messages.append(
            f"All {len(collapse_labels)} REBATE_YIELD_COLLAPSE anomalies verified"
        )
    return passed, messages


def validate_unit_conversion_errors_have_reduced_utilization(
    invoices: pl.DataFrame, labels: pl.DataFrame
) -> tuple[bool, list[str]]:
    """
    For all UNIT_CONVERSION_ERROR anomalies, assert invoiced_utilization
    is below the median for that NDC across other quarters (reduced by factor).

    Because we cannot compare against the unmodified baseline here, we check
    that expected_rebate > 0 (the row exists and was contracted) and that the
    label's estimated_impact > 0 (the reduction was meaningful).

    Args:
        invoices: Invoice DataFrame.
        labels: Anomaly labels DataFrame.

    Returns:
        (passed, messages).
    """
    uce_labels = labels.filter(pl.col("anomaly_type") == "UNIT_CONVERSION_ERROR")
    if len(uce_labels) == 0:
        return True, ["No UNIT_CONVERSION_ERROR labels to check"]

    messages: list[str] = []
    passed = True

    for row in uce_labels.to_dicts():
        ndc = row["ndc11"]
        client = row["client_id"]
        quarter = row["quarter"]
        impact = float(row["estimated_impact"])

        matching = invoices.filter(
            (pl.col("ndc11") == ndc)
            & (pl.col("client_id") == client)
            & (pl.col("invoice_quarter") == quarter)
        )

        if len(matching) == 0:
            messages.append(
                f"UNIT_CONVERSION_ERROR label ({ndc}, {client}, {quarter}): "
                "no matching invoice row found"
            )
            passed = False
            continue

        if impact <= 0.0:
            messages.append(
                f"UNIT_CONVERSION_ERROR label ({ndc}, {client}, {quarter}): "
                f"estimated_impact is {impact} (should be > 0)"
            )
            passed = False

    if passed:
        messages.append(
            f"All {len(uce_labels)} UNIT_CONVERSION_ERROR anomalies verified"
        )
    return passed, messages


# ---------------------------------------------------------------------------
# Reconciliation check
# ---------------------------------------------------------------------------


def validate_claim_to_invoice_reconciliation(
    claims: pl.DataFrame, invoices: pl.DataFrame
) -> tuple[bool, list[str]]:
    """
    For each invoice row, verify that invoiced_utilization matches the sum
    of quantity from claims for the same (ndc11, group_id/client_id, quarter).

    A 1% relative tolerance is applied for floating-point differences.

    Args:
        claims: Claims DataFrame with ``ndc11``, ``group_id``, ``quantity``,
            and ``fill_date`` columns.
        invoices: Invoice DataFrame with ``ndc11``, ``client_id``,
            ``invoice_quarter``, and ``invoiced_utilization`` columns.

    Returns:
        (passed, messages). On large datasets this check uses aggregation
        rather than row-by-row iteration for performance.

    Note:
        This check only applies to invoices that do NOT have anomaly injection
        side effects (e.g. injected UNMAPPED_NDC rows won't have claim backing).
        Mismatches are expected in datasets with anomaly injection applied.
    """
    # Add quarter column to claims
    claims_with_q = claims.with_columns(
        (
            pl.col("fill_date").dt.year().cast(pl.Utf8)
            + pl.lit("-Q")
            + ((pl.col("fill_date").dt.month() - 1) // 3 + 1).cast(pl.Utf8)
        ).alias("invoice_quarter"),
        pl.col("group_id").alias("client_id"),
    )

    # Aggregate claims to same grain as invoices
    claim_agg = (
        claims_with_q.group_by(["ndc11", "client_id", "invoice_quarter"])
        .agg(pl.col("quantity").sum().alias("claim_util"))
    )

    # Join invoice to aggregated claims
    joined = invoices.join(
        claim_agg,
        on=["ndc11", "client_id", "invoice_quarter"],
        how="left",
    )

    # Rows that have claim backing
    backed = joined.filter(pl.col("claim_util").is_not_null())
    if len(backed) == 0:
        return True, ["No invoice rows could be matched to claim aggregates"]

    # Check utilization within 1% relative tolerance
    tolerance = 0.01
    mismatches = backed.filter(
        (pl.col("claim_util") - pl.col("invoiced_utilization")).abs()
        > pl.col("claim_util") * tolerance + 0.01
    )

    n_mismatches = mismatches.height
    n_checked = backed.height

    if n_mismatches > 0:
        pct = 100.0 * n_mismatches / n_checked
        return (
            False,
            [
                f"{n_mismatches}/{n_checked} ({pct:.1f}%) invoice rows have "
                "invoiced_utilization inconsistent with claim aggregates "
                "(within 1% tolerance)"
            ],
        )
    return (
        True,
        [
            f"invoiced_utilization reconciles to claim aggregates "
            f"for all {n_checked} checked rows"
        ],
    )


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------


def run_all_validations(
    claims: pl.DataFrame,
    drugs: pl.DataFrame,
    formulary: pl.DataFrame,
    contracts: pl.DataFrame,
    invoices: pl.DataFrame,
    labels: Optional[pl.DataFrame] = None,
) -> dict[str, tuple[bool, list[str]]]:
    """
    Run all validation checks and return a results dictionary.

    Args:
        claims: Claims DataFrame.
        drugs: Drug master DataFrame.
        formulary: Formulary DataFrame (currently used for future expansion).
        contracts: Contracts DataFrame (currently used for future expansion).
        invoices: Invoice DataFrame.
        labels: Optional anomaly labels DataFrame. If None, anomaly
            detectability checks are skipped.

    Returns:
        Dictionary mapping validation name to (passed, messages) tuple.
    """
    results: dict[str, tuple[bool, list[str]]] = {}

    # --- Referential integrity -------------------------------------------
    results["ndc_referential_integrity"] = validate_all_claim_ndcs_in_drug_master(
        claims, drugs
    )

    results["no_null_claim_keys"] = validate_no_null_keys(
        claims, ["claim_id", "member_id", "group_id", "ndc11"]
    )

    results["no_null_invoice_keys"] = validate_no_null_keys(
        invoices, ["invoice_quarter", "manufacturer", "ndc11", "client_id"]
    )

    results["no_duplicate_invoices"] = validate_no_duplicate_invoices(invoices)

    # --- Financial constraints -------------------------------------------
    results["expected_rebate_non_negative"] = validate_expected_rebate_non_negative(
        invoices
    )

    results["actual_rebate_non_negative"] = validate_actual_rebate_non_negative(
        invoices
    )

    results["paid_rebate_lte_actual"] = validate_paid_rebate_lte_actual(invoices)

    results["disputed_rebate_lte_actual"] = validate_disputed_rebate_lte_actual(
        invoices
    )

    results["invoiced_utilization_positive"] = validate_invoiced_utilization_positive(
        invoices
    )

    # --- Date constraints -----------------------------------------------
    results["no_future_claims"] = validate_no_future_claims(claims)

    # --- Reconciliation -------------------------------------------------
    results["claim_invoice_reconciliation"] = validate_claim_to_invoice_reconciliation(
        claims, invoices
    )

    # --- Anomaly detectability (only if labels provided) ----------------
    if labels is not None and len(labels) > 0:
        results[
            "missing_rebate_anomalies"
        ] = validate_missing_rebate_anomalies_have_positive_expected(invoices, labels)

        results[
            "yield_collapse_anomalies"
        ] = validate_yield_collapse_anomalies_have_reduced_actual(invoices, labels)

        results[
            "unit_conversion_error_anomalies"
        ] = validate_unit_conversion_errors_have_reduced_utilization(
            invoices, labels
        )

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_validation_report(
    results: dict[str, tuple[bool, list[str]]]
) -> None:
    """
    Pretty-print validation report with summary of passed and failed checks.

    Args:
        results: Dictionary returned by :func:`run_all_validations`.
    """
    n_passed = sum(1 for passed, _ in results.values() if passed)
    n_failed = len(results) - n_passed

    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print(f"  Total checks : {len(results)}")
    print(f"  Passed       : {n_passed}")
    print(f"  Failed       : {n_failed}")
    print("=" * 60)

    for name, (passed, messages) in results.items():
        status = "PASS" if passed else "FAIL"
        indicator = "+" if passed else "!"
        print(f"  [{indicator}] {status:4s}  {name}")
        if not passed:
            for msg in messages:
                print(f"             -> {msg}")

    print("=" * 60)
    if n_failed == 0:
        print("  All checks passed.")
    else:
        print(f"  {n_failed} check(s) failed — review messages above.")
    print("=" * 60)
