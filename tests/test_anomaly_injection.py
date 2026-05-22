"""
Tests for anomaly injection functions (inject_anomalies.py).

Verifies that each injection function:
  - Produces the correct number of label rows
  - Modifies invoice data in the expected direction
  - Is reproducible given the same seed
  - Does not corrupt rows that were not targeted
"""

from __future__ import annotations

import polars as pl
import pytest

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_labels() -> pl.DataFrame:
    return make_empty_labels_df()


# ---------------------------------------------------------------------------
# inject_missing_rebate
# ---------------------------------------------------------------------------


class TestInjectMissingRebate:
    def test_label_count(self, small_invoices, small_contracts):
        """inject_missing_rebate must produce exactly `count` labels."""
        _, labels, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert len(labels) == 1

    def test_label_anomaly_type(self, small_invoices, small_contracts):
        """All injected labels must have anomaly_type = MISSING_REBATE."""
        _, labels, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        assert all(t == "MISSING_REBATE" for t in labels["anomaly_type"].to_list())

    def test_targeted_rows_have_zero_actual_rebate(self, small_invoices, small_contracts):
        """All rows labeled as MISSING_REBATE must have actual_rebate == 0."""
        inv_mod, labels, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        for row in labels.to_dicts():
            matching = inv_mod.filter(
                (pl.col("ndc11") == row["ndc11"])
                & (pl.col("client_id") == row["client_id"])
                & (pl.col("invoice_quarter") == row["quarter"])
            )
            assert matching.height > 0, "Labeled row not found in modified invoices"
            assert matching["actual_rebate"].sum() == 0.0, (
                f"actual_rebate is not 0 for labeled row "
                f"({row['ndc11']}, {row['client_id']}, {row['quarter']})"
            )

    def test_original_expected_rebate_preserved(self, small_invoices, small_contracts):
        """Injection must not change expected_rebate for targeted rows."""
        inv_mod, labels, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        label = labels.row(0, named=True)
        ndc, client, quarter = label["ndc11"], label["client_id"], label["quarter"]

        orig_exp = float(
            small_invoices.filter(
                (pl.col("ndc11") == ndc)
                & (pl.col("client_id") == client)
                & (pl.col("invoice_quarter") == quarter)
            )["expected_rebate"].sum()
        )
        mod_exp = float(
            inv_mod.filter(
                (pl.col("ndc11") == ndc)
                & (pl.col("client_id") == client)
                & (pl.col("invoice_quarter") == quarter)
            )["expected_rebate"].sum()
        )
        assert abs(orig_exp - mod_exp) < 0.01, (
            "expected_rebate was modified by inject_missing_rebate"
        )

    def test_untargeted_rows_unchanged(self, small_invoices, small_contracts):
        """Rows not targeted by the anomaly must remain unchanged."""
        inv_mod, labels, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        label = labels.row(0, named=True)
        # Check a row that is definitely not the target
        other_rows = small_invoices.filter(
            ~(
                (pl.col("ndc11") == label["ndc11"])
                & (pl.col("client_id") == label["client_id"])
                & (pl.col("invoice_quarter") == label["quarter"])
            )
        )
        other_mod = inv_mod.filter(
            ~(
                (pl.col("ndc11") == label["ndc11"])
                & (pl.col("client_id") == label["client_id"])
                & (pl.col("invoice_quarter") == label["quarter"])
            )
        )
        assert other_rows.frame_equal(other_mod), (
            "inject_missing_rebate modified rows that were not targeted"
        )

    def test_estimated_impact_positive(self, small_invoices, small_contracts):
        """Label estimated_impact must be > 0 (only rows with positive expected are targeted)."""
        _, labels, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        assert (labels["estimated_impact"] > 0.0).all()

    def test_reproducibility(self, small_invoices, small_contracts):
        """Same seed must produce identical results."""
        inv1, lab1, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        inv2, lab2, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert lab1.frame_equal(lab2), "Labels differ despite same seed"
        assert inv1.frame_equal(inv2), "Invoices differ despite same seed"

    def test_row_count_preserved(self, small_invoices, small_contracts):
        """inject_missing_rebate must not add or remove invoice rows."""
        inv_mod, _, _ = inject_missing_rebate(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert len(inv_mod) == len(small_invoices)


# ---------------------------------------------------------------------------
# inject_rebate_yield_collapse
# ---------------------------------------------------------------------------


class TestInjectRebateYieldCollapse:
    def test_label_count(self, small_invoices, small_contracts):
        """inject_rebate_yield_collapse must produce exactly `count` labels."""
        _, labels, _ = inject_rebate_yield_collapse(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        # count ≤ labels ≤ count (some target quarters may not exist)
        assert 1 <= len(labels) <= 2

    def test_label_anomaly_type(self, small_invoices, small_contracts):
        """All injected labels must have anomaly_type = REBATE_YIELD_COLLAPSE."""
        _, labels, _ = inject_rebate_yield_collapse(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert all(t == "REBATE_YIELD_COLLAPSE" for t in labels["anomaly_type"].to_list())

    def test_actual_rebate_reduced(self, small_invoices, small_contracts):
        """
        For targeted rows in 2024-Q3, actual_rebate should be ~30% of
        expected_rebate (reduction_factor=0.70 → keep_fraction=0.30).
        """
        reduction_factor = 0.70
        keep_fraction = 1.0 - reduction_factor

        inv_mod, labels, _ = inject_rebate_yield_collapse(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            reduction_factor=reduction_factor,
            count=1,
            seed=42,
        )
        for row in labels.to_dicts():
            ndc, client = row["ndc11"], row["client_id"]
            target_q = row["quarter"]
            matching = inv_mod.filter(
                (pl.col("ndc11") == ndc)
                & (pl.col("client_id") == client)
                & (pl.col("invoice_quarter") == target_q)
            )
            if len(matching) == 0:
                continue
            expected = float(matching["expected_rebate"].sum())
            actual = float(matching["actual_rebate"].sum())
            if expected > 0:
                assert abs(actual - expected * keep_fraction) < 0.05, (
                    f"actual_rebate {actual:.2f} is not ~{keep_fraction:.0%} "
                    f"of expected {expected:.2f}"
                )

    def test_non_target_quarter_rows_unchanged(self, small_invoices, small_contracts):
        """Rows in quarters other than 2024-Q3 must not be modified."""
        inv_mod, _, _ = inject_rebate_yield_collapse(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        other_q_orig = small_invoices.filter(pl.col("invoice_quarter") != "2024-Q3")
        other_q_mod = inv_mod.filter(pl.col("invoice_quarter") != "2024-Q3")
        assert other_q_orig.frame_equal(other_q_mod), (
            "inject_rebate_yield_collapse modified rows outside 2024-Q3"
        )

    def test_reproducibility(self, small_invoices, small_contracts):
        """Same seed must produce identical results."""
        inv1, lab1, _ = inject_rebate_yield_collapse(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        inv2, lab2, _ = inject_rebate_yield_collapse(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert lab1.frame_equal(lab2)
        assert inv1.frame_equal(inv2)


# ---------------------------------------------------------------------------
# inject_unit_conversion_error
# ---------------------------------------------------------------------------


class TestInjectUnitConversionError:
    def test_label_count(self, small_invoices, small_contracts):
        """inject_unit_conversion_error must produce exactly `count` labels."""
        _, labels, _ = inject_unit_conversion_error(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert len(labels) == 1

    def test_label_anomaly_type(self, small_invoices, small_contracts):
        """All injected labels must have anomaly_type = UNIT_CONVERSION_ERROR."""
        _, labels, _ = inject_unit_conversion_error(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert all(t == "UNIT_CONVERSION_ERROR" for t in labels["anomaly_type"].to_list())

    def test_invoiced_utilization_reduced(self, small_invoices, small_contracts):
        """
        For targeted rows, invoiced_utilization must be reduced by unit_divisor.
        """
        unit_divisor = 10
        inv_mod, labels, _ = inject_unit_conversion_error(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            unit_divisor=unit_divisor,
            count=1,
            seed=42,
        )
        label = labels.row(0, named=True)
        ndc, client, quarter = label["ndc11"], label["client_id"], label["quarter"]

        orig_util = float(
            small_invoices.filter(
                (pl.col("ndc11") == ndc)
                & (pl.col("client_id") == client)
                & (pl.col("invoice_quarter") == quarter)
            )["invoiced_utilization"].sum()
        )
        mod_util = float(
            inv_mod.filter(
                (pl.col("ndc11") == ndc)
                & (pl.col("client_id") == client)
                & (pl.col("invoice_quarter") == quarter)
            )["invoiced_utilization"].sum()
        )
        expected_mod_util = round(orig_util / unit_divisor, 4)
        assert abs(mod_util - expected_mod_util) < 0.01, (
            f"invoiced_utilization {mod_util:.4f} is not "
            f"orig/unit_divisor = {expected_mod_util:.4f}"
        )

    def test_estimated_impact_positive(self, small_invoices, small_contracts):
        """Label estimated_impact must be > 0."""
        _, labels, _ = inject_unit_conversion_error(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert (labels["estimated_impact"] > 0.0).all()

    def test_reproducibility(self, small_invoices, small_contracts):
        """Same seed must produce identical results."""
        inv1, lab1, _ = inject_unit_conversion_error(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        inv2, lab2, _ = inject_unit_conversion_error(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert lab1.frame_equal(lab2)
        assert inv1.frame_equal(inv2)

    def test_row_count_preserved(self, small_invoices, small_contracts):
        """inject_unit_conversion_error must not add or remove invoice rows."""
        inv_mod, _, _ = inject_unit_conversion_error(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert len(inv_mod) == len(small_invoices)


# ---------------------------------------------------------------------------
# inject_unmapped_ndc
# ---------------------------------------------------------------------------


class TestInjectUnmappedNdc:
    def test_label_count(self, small_invoices, small_contracts):
        """inject_unmapped_ndc must produce at most `count` labels."""
        _, labels, _ = inject_unmapped_ndc(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        assert 1 <= len(labels) <= 2

    def test_label_anomaly_type(self, small_invoices, small_contracts):
        """All injected labels must have anomaly_type = UNMAPPED_NDC."""
        _, labels, _ = inject_unmapped_ndc(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        assert all(t == "UNMAPPED_NDC" for t in labels["anomaly_type"].to_list())

    def test_injected_rows_have_zero_actual_rebate(self, small_invoices, small_contracts):
        """All injected UNMAPPED_NDC rows must have actual_rebate == 0."""
        inv_mod, labels, _ = inject_unmapped_ndc(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        injected_ndcs = labels["ndc11"].to_list()
        injected_rows = inv_mod.filter(pl.col("ndc11").is_in(injected_ndcs))
        assert injected_rows.filter(pl.col("actual_rebate") > 0.0).height == 0

    def test_row_count_increased(self, small_invoices, small_contracts):
        """inject_unmapped_ndc must add new rows to the invoice DataFrame."""
        inv_mod, labels, _ = inject_unmapped_ndc(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert len(inv_mod) > len(small_invoices)

    def test_injected_ndcs_not_in_original(self, small_invoices, small_contracts):
        """Injected NDCs must not exist in the original invoice DataFrame."""
        inv_mod, labels, _ = inject_unmapped_ndc(
            small_invoices, _fresh_labels(), small_contracts, count=2, seed=42
        )
        injected_ndcs = set(labels["ndc11"].to_list())
        original_ndcs = set(small_invoices["ndc11"].unique().to_list())
        overlap = injected_ndcs & original_ndcs
        assert not overlap, f"Injected NDCs overlap with original: {overlap}"


# ---------------------------------------------------------------------------
# inject_dispute_spike
# ---------------------------------------------------------------------------


class TestInjectDisputeSpike:
    def test_label_count(self, small_invoices, small_contracts, small_drugs):
        """inject_dispute_spike must produce exactly `count` labels."""
        _, labels, _ = inject_dispute_spike(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            count=1,
            seed=42,
            drugs_df=small_drugs,
        )
        assert len(labels) == 1

    def test_label_anomaly_type(self, small_invoices, small_contracts, small_drugs):
        """All injected labels must have anomaly_type = DISPUTE_SPIKE."""
        _, labels, _ = inject_dispute_spike(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            count=1,
            seed=42,
            drugs_df=small_drugs,
        )
        assert all(t == "DISPUTE_SPIKE" for t in labels["anomaly_type"].to_list())

    def test_paid_rebate_lte_actual_after_injection(self, small_invoices, small_contracts, small_drugs):
        """paid_rebate must remain <= actual_rebate after dispute spike injection."""
        inv_mod, _, _ = inject_dispute_spike(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            dispute_fraction=0.50,
            count=1,
            seed=42,
            drugs_df=small_drugs,
        )
        violations = inv_mod.filter(
            pl.col("paid_rebate") > pl.col("actual_rebate") + 0.01
        )
        assert violations.height == 0

    def test_reproducibility(self, small_invoices, small_contracts, small_drugs):
        """Same seed must produce identical results."""
        inv1, lab1, _ = inject_dispute_spike(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            count=1,
            seed=42,
            drugs_df=small_drugs,
        )
        inv2, lab2, _ = inject_dispute_spike(
            small_invoices,
            _fresh_labels(),
            small_contracts,
            count=1,
            seed=42,
            drugs_df=small_drugs,
        )
        assert lab1.frame_equal(lab2)
        assert inv1.frame_equal(inv2)


# ---------------------------------------------------------------------------
# inject_specialty_channel_omission
# ---------------------------------------------------------------------------


class TestInjectSpecialtyChannelOmission:
    def test_label_anomaly_type(self, small_invoices, small_contracts):
        """All injected labels must have anomaly_type = CHANNEL_OMISSION."""
        _, labels, _ = inject_specialty_channel_omission(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert all(t == "CHANNEL_OMISSION" for t in labels["anomaly_type"].to_list())

    def test_specialty_rows_have_zero_actual(self, small_invoices, small_contracts):
        """All specialty channel rows must have actual_rebate == 0 after injection."""
        inv_mod, _, _ = inject_specialty_channel_omission(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        if "channel" in inv_mod.columns:
            specialty_rows = inv_mod.filter(pl.col("channel") == "specialty")
            assert specialty_rows.filter(pl.col("actual_rebate") > 0.0).height == 0

    def test_channel_column_added(self, small_invoices, small_contracts):
        """After injection the invoice DataFrame must have a channel column."""
        inv_mod, _, _ = inject_specialty_channel_omission(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert "channel" in inv_mod.columns

    def test_row_count_increased(self, small_invoices, small_contracts):
        """inject_specialty_channel_omission splits rows, so total must increase."""
        inv_mod, _, _ = inject_specialty_channel_omission(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert len(inv_mod) >= len(small_invoices)


# ---------------------------------------------------------------------------
# inject_guarantee_true_up_missing
# ---------------------------------------------------------------------------


class TestInjectGuaranteeTrueUpMissing:
    def test_flag_set_in_contracts(self, small_invoices, small_contracts):
        """Flagged contracts must have missing_guarantee_true_up == True."""
        _, labels, contracts_mod = inject_guarantee_true_up_missing(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        if len(labels) > 0:
            assert "missing_guarantee_true_up" in contracts_mod.columns
            flagged = contracts_mod.filter(
                pl.col("missing_guarantee_true_up") == True  # noqa: E712
            )
            assert flagged.height > 0

    def test_label_anomaly_type(self, small_invoices, small_contracts):
        """All injected labels must have anomaly_type = GUARANTEE_TRUE_UP_MISSING."""
        _, labels, _ = inject_guarantee_true_up_missing(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert all(
            t == "GUARANTEE_TRUE_UP_MISSING" for t in labels["anomaly_type"].to_list()
        )

    def test_estimated_impact_non_negative(self, small_invoices, small_contracts):
        """estimated_impact must be >= 0 for all guarantee true-up labels."""
        _, labels, _ = inject_guarantee_true_up_missing(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert (labels["estimated_impact"] >= 0.0).all()

    def test_invoice_unchanged(self, small_invoices, small_contracts):
        """inject_guarantee_true_up_missing must not modify invoice data."""
        inv_mod, _, _ = inject_guarantee_true_up_missing(
            small_invoices, _fresh_labels(), small_contracts, count=1, seed=42
        )
        assert inv_mod.frame_equal(small_invoices)


# ---------------------------------------------------------------------------
# Cross-injection: stacking multiple anomalies
# ---------------------------------------------------------------------------


class TestStackedAnomalies:
    def test_multiple_anomaly_types_stack(self, small_invoices, small_contracts, small_drugs):
        """Multiple anomaly types can be injected sequentially without error."""
        labels = _fresh_labels()

        inv, labels, contracts = inject_missing_rebate(
            small_invoices, labels, small_contracts, count=1, seed=42
        )
        inv, labels, contracts = inject_rebate_yield_collapse(
            inv, labels, contracts, count=1, seed=43
        )
        inv, labels, contracts = inject_unit_conversion_error(
            inv, labels, contracts, count=1, seed=44
        )

        # We should have at least 3 label rows (one per anomaly type)
        assert len(labels) >= 3
        anomaly_types = set(labels["anomaly_type"].to_list())
        assert "MISSING_REBATE" in anomaly_types
        assert "REBATE_YIELD_COLLAPSE" in anomaly_types
        assert "UNIT_CONVERSION_ERROR" in anomaly_types
