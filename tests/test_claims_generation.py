"""
Tests for ClaimsGenerator (generate_claims.py).

Verifies row count, column presence, financial constraints, date range
compliance, channel/days-supply distributions, and reproducibility via seeded RNG.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from synthetic_data_gen.config import BaseConfig, DateRangeConfig
from synthetic_data_gen.generate_claims import ClaimsGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generator(config_small: BaseConfig, seed: int = 42) -> ClaimsGenerator:
    return ClaimsGenerator(config_small, seed=seed)


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def test_claims_row_count(config_small):
    """Generated claims must have exactly n_claims rows."""
    claims = _make_generator(config_small).generate()
    assert len(claims) == config_small.n_claims


def test_claims_columns_present(config_small):
    """All required columns must be present in the claims DataFrame."""
    claims = _make_generator(config_small).generate()
    expected_cols = [
        "claim_id",
        "member_id",
        "group_id",
        "ndc11",
        "fill_date",
        "days_supply",
        "quantity",
        "channel",
        "plan_paid",
        "gross_drug_cost",
        "claim_status",
    ]
    for col in expected_cols:
        assert col in claims.columns, f"Missing column: {col}"


def test_claims_no_nulls_in_key_columns(config_small):
    """Key columns must have no null values."""
    claims = _make_generator(config_small).generate()
    key_cols = ["claim_id", "member_id", "group_id", "ndc11", "fill_date"]
    for col in key_cols:
        assert claims[col].null_count() == 0, f"Null values found in '{col}'"


def test_claims_unique_claim_ids(config_small):
    """Every claim_id must be unique."""
    claims = _make_generator(config_small).generate()
    assert claims["claim_id"].n_unique() == len(claims)


# ---------------------------------------------------------------------------
# Financial constraint tests
# ---------------------------------------------------------------------------


def test_claims_plan_paid_lte_gross_drug_cost(config_small):
    """plan_paid must be <= gross_drug_cost for every claim row."""
    claims = _make_generator(config_small).generate()
    violations = claims.filter(pl.col("plan_paid") > pl.col("gross_drug_cost") + 0.01)
    assert violations.height == 0, (
        f"{violations.height} claims have plan_paid > gross_drug_cost"
    )


def test_claims_plan_paid_non_negative(config_small):
    """plan_paid must be >= 0."""
    claims = _make_generator(config_small).generate()
    assert (claims["plan_paid"] >= 0.0).all()


def test_claims_gross_drug_cost_positive(config_small):
    """gross_drug_cost must be > 0."""
    claims = _make_generator(config_small).generate()
    assert (claims["gross_drug_cost"] > 0.0).all()


def test_claims_quantity_positive(config_small):
    """quantity must be > 0."""
    claims = _make_generator(config_small).generate()
    assert (claims["quantity"] > 0.0).all()


def test_claims_days_supply_positive(config_small):
    """days_supply must be > 0."""
    claims = _make_generator(config_small).generate()
    assert (claims["days_supply"] > 0).all()


# ---------------------------------------------------------------------------
# Date range tests
# ---------------------------------------------------------------------------


def test_claims_dates_in_range(config_small):
    """All fill_dates must fall within the configured date range."""
    claims = _make_generator(config_small).generate()
    start = date.fromisoformat(config_small.date_range.start)
    end = date.fromisoformat(config_small.date_range.end)
    assert (claims["fill_date"] >= start).all(), "Some fill_dates are before start"
    assert (claims["fill_date"] <= end).all(), "Some fill_dates are after end"


def test_claims_sorted_by_fill_date(config_small):
    """Claims DataFrame must be sorted ascending by fill_date."""
    claims = _make_generator(config_small).generate()
    dates = claims["fill_date"].to_list()
    assert dates == sorted(dates), "Claims are not sorted by fill_date"


# ---------------------------------------------------------------------------
# Distribution tests
# ---------------------------------------------------------------------------


def test_claims_channel_distribution(config_small):
    """
    Channel distribution must be approximately correct within ±15%.

    Defaults: retail=70%, mail=20%, specialty=10%.
    """
    claims = _make_generator(config_small).generate()
    n = len(claims)
    channel_counts = (
        claims.group_by("channel")
        .agg(pl.len().alias("count"))
        .with_columns((pl.col("count") / n).alias("fraction"))
    )
    fracs = dict(
        zip(
            channel_counts["channel"].to_list(),
            channel_counts["fraction"].to_list(),
        )
    )
    tolerance = 0.15
    assert abs(fracs.get("retail", 0) - 0.70) < tolerance, (
        f"retail fraction {fracs.get('retail', 0):.3f} out of expected 0.70 ± {tolerance}"
    )
    assert abs(fracs.get("mail", 0) - 0.20) < tolerance, (
        f"mail fraction {fracs.get('mail', 0):.3f} out of expected 0.20 ± {tolerance}"
    )
    assert abs(fracs.get("specialty", 0) - 0.10) < tolerance, (
        f"specialty fraction {fracs.get('specialty', 0):.3f} out of expected 0.10 ± {tolerance}"
    )


def test_claims_days_supply_distribution(config_small):
    """
    Days supply must only take the four expected values and 30 must be most common.
    """
    claims = _make_generator(config_small).generate()
    valid_ds = {30, 60, 84, 90}
    actual_ds = set(claims["days_supply"].unique().to_list())
    assert actual_ds.issubset(valid_ds), (
        f"Unexpected days_supply values: {actual_ds - valid_ds}"
    )
    # 30-day is the most common value
    counts = (
        claims.group_by("days_supply")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    most_common = counts["days_supply"][0]
    assert most_common == 30, f"Expected 30-day to be most common, got {most_common}"


def test_claims_ndc_count(config_small):
    """Number of unique NDCs must equal n_ndcs."""
    claims = _make_generator(config_small).generate()
    n_unique_ndcs = claims["ndc11"].n_unique()
    assert n_unique_ndcs == config_small.n_ndcs, (
        f"Expected {config_small.n_ndcs} unique NDCs, got {n_unique_ndcs}"
    )


def test_claims_group_count(config_small):
    """Number of unique group_ids must equal n_groups."""
    claims = _make_generator(config_small).generate()
    n_unique_groups = claims["group_id"].n_unique()
    assert n_unique_groups == config_small.n_groups, (
        f"Expected {config_small.n_groups} unique group_ids, got {n_unique_groups}"
    )


def test_claims_valid_claim_status_values(config_small):
    """claim_status must only contain recognised status values."""
    claims = _make_generator(config_small).generate()
    valid_statuses = {"paid", "reversed", "adjusted", "pending"}
    actual_statuses = set(claims["claim_status"].unique().to_list())
    assert actual_statuses.issubset(valid_statuses), (
        f"Unexpected claim_status values: {actual_statuses - valid_statuses}"
    )


def test_claims_valid_ndc_format(config_small):
    """All ndc11 values must be exactly 11 numeric digits."""
    claims = _make_generator(config_small).generate()
    # Check length == 11 via string length expression
    lengths = claims["ndc11"].str.len_chars().unique().to_list()
    assert lengths == [11], f"Unexpected ndc11 lengths: {lengths}"


# ---------------------------------------------------------------------------
# Reproducibility tests
# ---------------------------------------------------------------------------


def test_claims_reproducibility(config_small):
    """Two generators with the same seed must produce identical DataFrames."""
    gen1 = ClaimsGenerator(config_small, seed=42)
    gen2 = ClaimsGenerator(config_small, seed=42)
    claims1 = gen1.generate()
    claims2 = gen2.generate()
    assert claims1.equals(claims2), "Claims DataFrames differ despite same seed"


def test_claims_different_seeds_produce_different_data(config_small):
    """Different seeds should produce different data."""
    gen1 = ClaimsGenerator(config_small, seed=42)
    gen2 = ClaimsGenerator(config_small, seed=99)
    claims1 = gen1.generate()
    claims2 = gen2.generate()
    # Very unlikely to be identical with different seeds
    assert not claims1.equals(claims2), (
        "Claims DataFrames are identical despite different seeds"
    )
