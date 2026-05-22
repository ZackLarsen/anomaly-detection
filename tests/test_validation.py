"""
Tests for the validation module (validate.py).

Verifies that validation functions pass on clean data, fail on intentionally
corrupted data, and that anomaly detectability checks correctly identify
injected anomalies.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from synthetic_data_gen.inject_anomalies import (
    inject_missing_rebate,
    inject_rebate_yield_collapse,
    inject_unit_conversion_error,
    make_empty_labels_df,
)
from synthetic_data_gen.validate import (
    print_validation_report,
    run_all_validations,
    validate_actual_rebate_non_negative,
    validate_all_claim_ndcs_in_drug_master,
    validate_claim_to_invoice_reconciliation,
    validate_disputed_rebate_lte_actual,
    validate_expected_rebate_non_negative,
    validate_invoiced_utilization_positive,
    validate_missing_rebate_anomalies_have_positive_expected,
    validate_no_duplicate_invoices,
    validate_no_future_claims,
    validate_no_null_keys,
    validate_paid_rebate_lte_actual,
    validate_unit_conversion_errors_have_reduced_utilization,
    validate_yield_collapse_anomalies_have_reduced_actual,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_invoices(**overrides) -> pl.DataFrame:
    """Return a minimal 2-row invoice DataFrame for targeted unit tests."""
    base = {
        "invoice_quarter": ["2024-Q1", "2024-Q2"],
        "manufacturer": ["M01", "M02"],
        "ndc11": ["10000000001", "10000000002"],
        "client_id": ["G001", "G002"],
        "invoiced_utilization": [100.0, 200.0],
        "expected_rebate": [50.0, 100.0],
        "actual_rebate": [48.0, 98.0],
        "disputed_rebate": [0.0, 0.0],
        "paid_rebate": [48.0, 98.0],
    }
    base.update(overrides)
    return pl.DataFrame(base)


# ---------------------------------------------------------------------------
# validate_all_claim_ndcs_in_drug_master
# ---------------------------------------------------------------------------


def test_validate_ndc_integrity_pass(small_claims, small_drugs):
    """Should pass when all claim NDCs are present in drug master."""
    passed, messages = validate_all_claim_ndcs_in_drug_master(small_claims, small_drugs)
    assert passed, f"Expected pass, got: {messages}"


def test_validate_ndc_integrity_fail():
    """Should fail when claims contain NDCs absent from drug master."""
    claims = pl.DataFrame({"ndc11": ["10000000001", "99999999999"]})
    drugs = pl.DataFrame({"ndc11": ["10000000001"]})  # 99999999999 missing
    passed, messages = validate_all_claim_ndcs_in_drug_master(claims, drugs)
    assert not passed
    assert any("99999999999" in m for m in messages)


def test_validate_ndc_integrity_all_missing():
    """Should fail and report violations when all claim NDCs are absent from drugs."""
    claims = pl.DataFrame({"ndc11": ["10000000001", "10000000002"]})
    drugs = pl.DataFrame({"ndc11": ["99000000001"]})
    passed, messages = validate_all_claim_ndcs_in_drug_master(claims, drugs)
    assert not passed
    assert len(messages) >= 2


# ---------------------------------------------------------------------------
# validate_no_null_keys
# ---------------------------------------------------------------------------


def test_validate_no_null_keys_pass():
    """Should pass when no nulls in key columns."""
    df = pl.DataFrame({"a": ["x", "y"], "b": [1, 2]})
    passed, _ = validate_no_null_keys(df, ["a", "b"])
    assert passed


def test_validate_no_null_keys_fail():
    """Should fail when a key column has nulls."""
    df = pl.DataFrame({"a": ["x", None], "b": [1, 2]})
    passed, messages = validate_no_null_keys(df, ["a"])
    assert not passed
    assert any("null" in m.lower() for m in messages)


def test_validate_no_null_keys_missing_col():
    """Should fail if a specified key column is not in the DataFrame."""
    df = pl.DataFrame({"a": ["x", "y"]})
    passed, messages = validate_no_null_keys(df, ["a", "nonexistent"])
    assert not passed


# ---------------------------------------------------------------------------
# validate_expected_rebate_non_negative
# ---------------------------------------------------------------------------


def test_validate_expected_rebate_non_negative_pass(small_invoices):
    """Should pass on clean invoice data."""
    passed, messages = validate_expected_rebate_non_negative(small_invoices)
    assert passed, f"Expected pass, got: {messages}"


def test_validate_expected_rebate_non_negative_fail():
    """Should fail when any expected_rebate is negative."""
    inv = _minimal_invoices(expected_rebate=[-1.0, 100.0])
    passed, messages = validate_expected_rebate_non_negative(inv)
    assert not passed
    assert any("negative" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# validate_actual_rebate_non_negative
# ---------------------------------------------------------------------------


def test_validate_actual_rebate_non_negative_pass(small_invoices):
    """Should pass on clean invoice data."""
    passed, _ = validate_actual_rebate_non_negative(small_invoices)
    assert passed


def test_validate_actual_rebate_non_negative_fail():
    """Should fail when actual_rebate is negative."""
    inv = _minimal_invoices(actual_rebate=[-5.0, 98.0], paid_rebate=[0.0, 98.0])
    passed, messages = validate_actual_rebate_non_negative(inv)
    assert not passed


# ---------------------------------------------------------------------------
# validate_paid_rebate_lte_actual
# ---------------------------------------------------------------------------


def test_validate_paid_rebate_lte_actual_pass(small_invoices):
    """Should pass on clean invoice data."""
    passed, _ = validate_paid_rebate_lte_actual(small_invoices)
    assert passed


def test_validate_paid_rebate_lte_actual_fail():
    """Should fail when paid_rebate > actual_rebate."""
    inv = _minimal_invoices(paid_rebate=[200.0, 98.0])  # 200 > 48 actual
    passed, messages = validate_paid_rebate_lte_actual(inv)
    assert not passed


# ---------------------------------------------------------------------------
# validate_disputed_rebate_lte_actual
# ---------------------------------------------------------------------------


def test_validate_disputed_rebate_lte_actual_pass(small_invoices):
    """Should pass on clean invoice data."""
    passed, _ = validate_disputed_rebate_lte_actual(small_invoices)
    assert passed


def test_validate_disputed_rebate_lte_actual_fail():
    """Should fail when disputed_rebate > actual_rebate."""
    inv = _minimal_invoices(disputed_rebate=[200.0, 0.0])  # 200 > 48 actual
    passed, messages = validate_disputed_rebate_lte_actual(inv)
    assert not passed


# ---------------------------------------------------------------------------
# validate_no_future_claims
# ---------------------------------------------------------------------------


def test_validate_no_future_claims_pass(small_claims):
    """Should pass when all fill_dates are within 2025-12-31."""
    passed, _ = validate_no_future_claims(small_claims, cutoff_date="2025-12-31")
    assert passed


def test_validate_no_future_claims_fail():
    """Should fail when claims have fill_dates after cutoff."""
    future_claims = pl.DataFrame({
        "fill_date": [date(2024, 1, 1), date(2030, 6, 15)],
    }).with_columns(pl.col("fill_date").cast(pl.Date))
    passed, messages = validate_no_future_claims(future_claims, cutoff_date="2025-12-31")
    assert not passed
    assert any("future" in m.lower() or "after" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# validate_invoiced_utilization_positive
# ---------------------------------------------------------------------------


def test_validate_invoiced_utilization_positive_pass(small_invoices):
    """Should pass when all invoiced_utilization values are > 0."""
    passed, _ = validate_invoiced_utilization_positive(small_invoices)
    assert passed


def test_validate_invoiced_utilization_positive_fail():
    """Should fail when invoiced_utilization contains zero."""
    inv = _minimal_invoices(invoiced_utilization=[0.0, 200.0])
    passed, messages = validate_invoiced_utilization_positive(inv)
    assert not passed


# ---------------------------------------------------------------------------
# validate_no_duplicate_invoices
# ---------------------------------------------------------------------------


def test_validate_no_duplicate_invoices_pass(small_invoices):
    """Should pass on clean invoice data with no duplicates."""
    passed, _ = validate_no_duplicate_invoices(small_invoices)
    assert passed


def test_validate_no_duplicate_invoices_fail():
    """Should fail when duplicate key rows exist."""
    dup_inv = pl.concat([_minimal_invoices(), _minimal_invoices()], how="diagonal")
    passed, messages = validate_no_duplicate_invoices(dup_inv)
    assert not passed
    assert any("duplicate" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# validate_claim_to_invoice_reconciliation
# ---------------------------------------------------------------------------


def test_validate_claim_invoice_reconciliation_pass(small_claims, small_invoices):
    """Should pass when invoiced_utilization matches claim aggregates."""
    passed, messages = validate_claim_to_invoice_reconciliation(small_claims, small_invoices)
    assert passed, f"Expected pass, got: {messages}"


# ---------------------------------------------------------------------------
# Anomaly detectability checks
# ---------------------------------------------------------------------------


def test_validate_missing_rebate_anomalies_pass(small_invoices, small_contracts):
    """Should pass after inject_missing_rebate is applied."""
    inv_mod, labels, _ = inject_missing_rebate(
        small_invoices, make_empty_labels_df(), small_contracts, count=1, seed=42
    )
    passed, messages = validate_missing_rebate_anomalies_have_positive_expected(
        inv_mod, labels
    )
    assert passed, f"Expected pass after injection, got: {messages}"


def test_validate_missing_rebate_no_labels_passes():
    """Should pass trivially when there are no MISSING_REBATE labels."""
    inv = _minimal_invoices()
    labels = make_empty_labels_df()
    passed, _ = validate_missing_rebate_anomalies_have_positive_expected(inv, labels)
    assert passed


def test_validate_yield_collapse_anomalies_pass(small_invoices, small_contracts):
    """Should pass after inject_rebate_yield_collapse is applied."""
    inv_mod, labels, _ = inject_rebate_yield_collapse(
        small_invoices, make_empty_labels_df(), small_contracts, count=1, seed=42
    )
    passed, messages = validate_yield_collapse_anomalies_have_reduced_actual(
        inv_mod, labels
    )
    assert passed, f"Expected pass after injection, got: {messages}"


def test_validate_unit_conversion_error_anomalies_pass(small_invoices, small_contracts):
    """Should pass after inject_unit_conversion_error is applied."""
    inv_mod, labels, _ = inject_unit_conversion_error(
        small_invoices, make_empty_labels_df(), small_contracts, count=1, seed=42
    )
    passed, messages = validate_unit_conversion_errors_have_reduced_utilization(
        inv_mod, labels
    )
    assert passed, f"Expected pass after injection, got: {messages}"


# ---------------------------------------------------------------------------
# run_all_validations
# ---------------------------------------------------------------------------


def test_run_all_validations_pass_on_clean_data(
    small_claims, small_drugs, small_formulary, small_contracts, small_invoices
):
    """run_all_validations must pass for all checks on clean baseline data."""
    results = run_all_validations(
        small_claims, small_drugs, small_formulary, small_contracts, small_invoices
    )

    failed = {name: msgs for name, (passed, msgs) in results.items() if not passed}
    assert not failed, (
        f"Validation failures on clean data:\n"
        + "\n".join(
            f"  {name}: {msgs}" for name, msgs in failed.items()
        )
    )


def test_run_all_validations_returns_dict(
    small_claims, small_drugs, small_formulary, small_contracts, small_invoices
):
    """run_all_validations must return a non-empty dictionary."""
    results = run_all_validations(
        small_claims, small_drugs, small_formulary, small_contracts, small_invoices
    )
    assert isinstance(results, dict)
    assert len(results) > 0


def test_run_all_validations_with_labels_pass(
    small_claims, small_drugs, small_formulary, small_contracts, small_invoices
):
    """run_all_validations with injected anomalies and matching labels should pass."""
    inv_mod, labels, contracts_mod = inject_missing_rebate(
        small_invoices, make_empty_labels_df(), small_contracts, count=1, seed=42
    )
    results = run_all_validations(
        small_claims, small_drugs, small_formulary, contracts_mod, inv_mod, labels
    )
    # The anomaly detectability checks should pass
    if "missing_rebate_anomalies" in results:
        passed, msgs = results["missing_rebate_anomalies"]
        assert passed, f"missing_rebate_anomalies check failed: {msgs}"


def test_run_all_validations_detects_bad_ndc():
    """run_all_validations detects NDC referential integrity failure."""
    claims = pl.DataFrame({"ndc11": ["99999999999", "10000000001"],
                            "claim_id": ["C1", "C2"],
                            "member_id": ["M1", "M1"],
                            "group_id": ["G1", "G1"],
                            "fill_date": [date(2024, 1, 1), date(2024, 1, 1)],
                            "days_supply": [30, 30],
                            "quantity": [30.0, 30.0],
                            "channel": ["retail", "retail"],
                            "plan_paid": [50.0, 50.0],
                            "gross_drug_cost": [75.0, 75.0],
                            "claim_status": ["paid", "paid"]}).with_columns(
        pl.col("fill_date").cast(pl.Date)
    )
    drugs = pl.DataFrame({"ndc11": ["10000000001"]})  # 99999999999 missing

    results = run_all_validations(claims, drugs, pl.DataFrame(), pl.DataFrame(), pl.DataFrame())
    ndc_check_passed, msgs = results["ndc_referential_integrity"]
    assert not ndc_check_passed


# ---------------------------------------------------------------------------
# print_validation_report
# ---------------------------------------------------------------------------


def test_print_validation_report_runs_without_error(
    small_claims, small_drugs, small_formulary, small_contracts, small_invoices, capsys
):
    """print_validation_report must complete without raising an exception."""
    results = run_all_validations(
        small_claims, small_drugs, small_formulary, small_contracts, small_invoices
    )
    print_validation_report(results)
    captured = capsys.readouterr()
    assert "VALIDATION REPORT" in captured.out
    assert "PASS" in captured.out


def test_print_validation_report_shows_failures(capsys):
    """print_validation_report must show FAIL for failing checks."""
    results = {
        "my_check": (False, ["Something is wrong"]),
        "good_check": (True, ["All good"]),
    }
    print_validation_report(results)
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "Something is wrong" in captured.out
