"""
Tests for invoice generation and claim-to-invoice reconciliation.

Verifies financial constraints, invoice structure, that rebate amounts
are consistent with contract terms, and that invoice aggregation correctly
reconciles back to claim-level data.
"""

from __future__ import annotations

import polars as pl
import pytest


# ---------------------------------------------------------------------------
# Invoice structure tests
# ---------------------------------------------------------------------------


def test_invoices_columns_present(small_invoices):
    """All required invoice columns must be present."""
    expected_cols = [
        "invoice_quarter",
        "manufacturer",
        "ndc11",
        "client_id",
        "invoiced_utilization",
        "expected_rebate",
        "actual_rebate",
        "disputed_rebate",
        "paid_rebate",
    ]
    for col in expected_cols:
        assert col in small_invoices.columns, f"Missing column: {col}"


def test_invoices_no_null_keys(small_invoices):
    """Key columns must not contain nulls."""
    key_cols = ["invoice_quarter", "manufacturer", "ndc11", "client_id"]
    for col in key_cols:
        assert small_invoices[col].null_count() == 0, f"Null values in '{col}'"


def test_invoices_quarter_format(small_invoices):
    """All invoice_quarter values must match YYYY-QN format."""
    import re

    pattern = re.compile(r"^\d{4}-Q[1-4]$")
    bad = [
        q
        for q in small_invoices["invoice_quarter"].unique().to_list()
        if not pattern.match(q)
    ]
    assert not bad, f"Invalid invoice_quarter values: {bad}"


def test_invoices_non_empty(small_invoices):
    """Invoice DataFrame must not be empty."""
    assert len(small_invoices) > 0


# ---------------------------------------------------------------------------
# Financial constraint tests
# ---------------------------------------------------------------------------


def test_expected_rebate_non_negative(small_invoices):
    """expected_rebate must be >= 0 for all rows."""
    violations = small_invoices.filter(pl.col("expected_rebate") < 0.0)
    assert violations.height == 0, (
        f"{violations.height} rows have negative expected_rebate"
    )


def test_actual_rebate_non_negative(small_invoices):
    """actual_rebate must be >= 0 for all rows."""
    violations = small_invoices.filter(pl.col("actual_rebate") < 0.0)
    assert violations.height == 0, (
        f"{violations.height} rows have negative actual_rebate"
    )


def test_paid_rebate_lte_actual_rebate(small_invoices):
    """paid_rebate must be <= actual_rebate (within small float tolerance)."""
    violations = small_invoices.filter(
        pl.col("paid_rebate") > pl.col("actual_rebate") + 0.01
    )
    assert violations.height == 0, (
        f"{violations.height} rows have paid_rebate > actual_rebate"
    )


def test_disputed_rebate_lte_actual_rebate(small_invoices):
    """disputed_rebate must be <= actual_rebate."""
    violations = small_invoices.filter(
        pl.col("disputed_rebate") > pl.col("actual_rebate") + 0.01
    )
    assert violations.height == 0, (
        f"{violations.height} rows have disputed_rebate > actual_rebate"
    )


def test_invoiced_utilization_positive(small_invoices):
    """invoiced_utilization must be > 0 for all rows."""
    violations = small_invoices.filter(pl.col("invoiced_utilization") <= 0.0)
    assert violations.height == 0, (
        f"{violations.height} rows have invoiced_utilization <= 0"
    )


def test_baseline_disputed_rebate_is_zero(small_invoices):
    """
    In the baseline (no anomaly injection), disputed_rebate should be 0
    for all rows.
    """
    non_zero_disputes = small_invoices.filter(pl.col("disputed_rebate") > 0.0)
    assert non_zero_disputes.height == 0, (
        f"{non_zero_disputes.height} rows have disputed_rebate > 0 in baseline"
    )


def test_baseline_paid_equals_actual(small_invoices):
    """
    In the baseline, paid_rebate should equal actual_rebate for all rows.
    """
    mismatches = small_invoices.filter(
        (pl.col("paid_rebate") - pl.col("actual_rebate")).abs() > 0.01
    )
    assert mismatches.height == 0, (
        f"{mismatches.height} rows have paid_rebate != actual_rebate in baseline"
    )


# ---------------------------------------------------------------------------
# No duplicate invoice rows
# ---------------------------------------------------------------------------


def test_no_duplicate_invoice_rows(small_invoices):
    """
    Each (invoice_quarter, manufacturer, ndc11, client_id) combination
    should appear at most once.
    """
    key_cols = ["invoice_quarter", "manufacturer", "ndc11", "client_id"]
    n_total = len(small_invoices)
    n_unique = small_invoices.select(key_cols).unique().height
    assert n_total == n_unique, (
        f"Found {n_total - n_unique} duplicate invoice rows"
    )


# ---------------------------------------------------------------------------
# Invoice–claim reconciliation
# ---------------------------------------------------------------------------


def test_invoice_rows_backed_by_claims(small_claims, small_invoices):
    """
    All invoice rows should correspond to at least one claim
    (before anomaly injection, there are no phantom NDCs).
    """
    claim_ndcs = set(small_claims["ndc11"].unique().to_list())
    invoice_ndcs = set(small_invoices["ndc11"].unique().to_list())
    unbacked = invoice_ndcs - claim_ndcs
    assert not unbacked, (
        f"{len(unbacked)} invoice NDCs have no corresponding claims: "
        f"{sorted(unbacked)[:5]}"
    )


def test_invoiced_utilization_matches_claim_aggregates(small_claims, small_invoices):
    """
    invoiced_utilization should match the sum of quantity from claims,
    aggregated to the (ndc11, client_id, invoice_quarter) grain.

    A 1% relative tolerance is applied.
    """
    # Build quarter from fill_date
    claims_with_q = small_claims.with_columns(
        (
            pl.col("fill_date").dt.year().cast(pl.Utf8)
            + pl.lit("-Q")
            + ((pl.col("fill_date").dt.month() - 1) // 3 + 1).cast(pl.Utf8)
        ).alias("invoice_quarter"),
        pl.col("group_id").alias("client_id"),
    )

    # Aggregate claims
    claim_agg = (
        claims_with_q.group_by(["ndc11", "client_id", "invoice_quarter"])
        .agg(pl.col("quantity").sum().alias("claim_util"))
    )

    # Join to invoices
    joined = small_invoices.join(
        claim_agg,
        on=["ndc11", "client_id", "invoice_quarter"],
        how="inner",
    )

    assert len(joined) > 0, "No invoice rows could be matched to claim aggregates"

    # Check utilization within 1% tolerance
    mismatches = joined.filter(
        (pl.col("claim_util") - pl.col("invoiced_utilization")).abs()
        > pl.col("claim_util") * 0.01 + 0.01
    )

    pct = 100.0 * mismatches.height / len(joined)
    assert mismatches.height == 0, (
        f"{mismatches.height}/{len(joined)} ({pct:.1f}%) invoice rows have "
        "invoiced_utilization inconsistent with claim aggregates"
    )


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_invoices_sorted(small_invoices):
    """Invoices must be sorted by (invoice_quarter, manufacturer, ndc11, client_id)."""
    sort_cols = ["invoice_quarter", "manufacturer", "ndc11", "client_id"]
    sorted_df = small_invoices.sort(sort_cols)
    assert small_invoices.equals(sorted_df), (
        "Invoice DataFrame is not sorted by the expected key columns"
    )
