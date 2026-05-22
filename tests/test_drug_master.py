"""
Tests for DrugGenerator (generate_drugs.py).

Verifies that the drug master contains all NDCs from claims, specialty flag
distributions match config, effective dates cover the claim date range, and
manufacturer counts are correct.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from synthetic_data_gen.generate_claims import ClaimsGenerator
from synthetic_data_gen.generate_drugs import DrugGenerator


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def test_drugs_columns_present(config_small, small_claims):
    """All required drug master columns must be present."""
    drugs = DrugGenerator(config_small, small_claims, seed=42).generate()
    expected_cols = [
        "ndc11",
        "brand_family",
        "manufacturer",
        "gpi_class",
        "specialty_flag",
        "package_size",
        "effective_date_start",
        "effective_date_end",
        "launch_date",
    ]
    for col in expected_cols:
        assert col in drugs.columns, f"Missing column: {col}"


def test_drugs_no_null_keys(config_small, small_claims):
    """Key columns ndc11, brand_family, manufacturer must have no nulls."""
    drugs = DrugGenerator(config_small, small_claims, seed=42).generate()
    for col in ["ndc11", "brand_family", "manufacturer"]:
        assert drugs[col].null_count() == 0, f"Null values in '{col}'"


def test_drugs_unique_ndcs(config_small, small_claims):
    """Each NDC in the drug master must appear exactly once."""
    drugs = DrugGenerator(config_small, small_claims, seed=42).generate()
    assert drugs["ndc11"].n_unique() == len(drugs), (
        "Drug master has duplicate NDC entries"
    )


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------


def test_drugs_contains_all_claim_ndcs(small_claims, small_drugs):
    """Drug master must contain every NDC that appears in claims."""
    claim_ndcs = set(small_claims["ndc11"].unique().to_list())
    drug_ndcs = set(small_drugs["ndc11"].unique().to_list())
    missing = claim_ndcs - drug_ndcs
    assert not missing, (
        f"Drug master is missing {len(missing)} NDCs found in claims: "
        f"{sorted(missing)[:5]}"
    )


def test_drugs_ndc_row_count_matches_unique_claim_ndcs(small_claims, small_drugs):
    """Drug master row count should equal number of unique NDCs in claims."""
    n_claim_ndcs = small_claims["ndc11"].n_unique()
    assert len(small_drugs) == n_claim_ndcs, (
        f"Drug master has {len(small_drugs)} rows but claims has "
        f"{n_claim_ndcs} unique NDCs"
    )


# ---------------------------------------------------------------------------
# Specialty flag
# ---------------------------------------------------------------------------


def test_drugs_specialty_flag_distribution(config_small, small_drugs):
    """
    At least config.specialty_flag_probability fraction of drugs should be
    specialty (injectable GPIs push the rate above the base rate).
    """
    specialty_count = small_drugs.filter(pl.col("specialty_flag") == True).height  # noqa: E712
    min_expected_frac = config_small.specialty_flag_probability * 0.8  # allow slack
    actual_frac = specialty_count / len(small_drugs)
    assert actual_frac >= min_expected_frac, (
        f"Specialty flag rate {actual_frac:.3f} is below "
        f"minimum expected {min_expected_frac:.3f}"
    )


def test_drugs_specialty_flag_is_boolean(small_drugs):
    """specialty_flag column must be boolean dtype."""
    assert small_drugs["specialty_flag"].dtype == pl.Boolean, (
        f"specialty_flag dtype is {small_drugs['specialty_flag'].dtype}, expected Boolean"
    )


# ---------------------------------------------------------------------------
# Date coverage
# ---------------------------------------------------------------------------


def test_drugs_effective_date_coverage(config_small, small_claims, small_drugs):
    """
    For every claim, the drug effective_date_start <= fill_date <=
    effective_date_end (if not None).
    """
    # Join claims to drugs on ndc11
    joined = small_claims.join(
        small_drugs.select(["ndc11", "effective_date_start", "effective_date_end"]),
        on="ndc11",
        how="left",
    )

    # Check fill_date >= effective_date_start
    before_start = joined.filter(
        pl.col("fill_date") < pl.col("effective_date_start")
    )
    assert before_start.height == 0, (
        f"{before_start.height} claims have fill_date before drug effective_date_start"
    )

    # Check fill_date <= effective_date_end (where not null)
    after_end = joined.filter(
        pl.col("effective_date_end").is_not_null()
        & (pl.col("fill_date") > pl.col("effective_date_end"))
    )
    assert after_end.height == 0, (
        f"{after_end.height} claims have fill_date after drug effective_date_end"
    )


def test_drugs_launch_dates_reasonable(small_drugs):
    """Launch dates should be in the range 2020-01-01 to 2024-01-01."""
    min_launch = date(2020, 1, 1)
    max_launch = date(2024, 1, 1)
    assert (small_drugs["launch_date"] >= min_launch).all(), (
        "Some drug launch_dates are before 2020-01-01"
    )
    assert (small_drugs["launch_date"] <= max_launch).all(), (
        "Some drug launch_dates are after 2024-01-01"
    )


# ---------------------------------------------------------------------------
# Manufacturer
# ---------------------------------------------------------------------------


def test_drugs_manufacturer_count(config_small, small_drugs):
    """Number of unique manufacturers must equal config.n_manufacturers."""
    manufacturer_count = small_drugs["manufacturer"].n_unique()
    assert manufacturer_count == config_small.n_manufacturers, (
        f"Expected {config_small.n_manufacturers} manufacturers, "
        f"got {manufacturer_count}"
    )


# ---------------------------------------------------------------------------
# Brand families
# ---------------------------------------------------------------------------


def test_drugs_brand_families_assigned(small_drugs):
    """Every drug must have a non-empty brand_family."""
    empty_brand = small_drugs.filter(pl.col("brand_family") == "").height
    assert empty_brand == 0, f"{empty_brand} drugs have empty brand_family"


def test_drugs_ndcs_per_brand_family(small_drugs):
    """Brand families should have roughly 5 NDCs each (within factor of 2)."""
    brand_counts = (
        small_drugs.group_by("brand_family")
        .agg(pl.len().alias("ndc_count"))
    )
    max_count = brand_counts["ndc_count"].max()
    # Each brand gets ~5 NDCs; allow up to 10 for the last partial group
    assert max_count <= 10, (
        f"One brand family has {max_count} NDCs, expected <= 10"
    )


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_drugs_reproducibility(config_small, small_claims):
    """Two DrugGenerators with same seed must produce identical DataFrames."""
    gen1 = DrugGenerator(config_small, small_claims, seed=42)
    gen2 = DrugGenerator(config_small, small_claims, seed=42)
    drugs1 = gen1.generate()
    drugs2 = gen2.generate()
    assert drugs1.equals(drugs2), "Drug DataFrames differ despite same seed"
