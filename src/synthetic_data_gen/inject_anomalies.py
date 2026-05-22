"""
Anomaly injection functions for the synthetic Rx rebate data generation system.

This module provides 7 reusable functions that inject realistic rebate leakage
anomalies into synthetic invoice data, together with ground-truth label records
for model evaluation.

Each injection function:
  1. Accepts invoice_df, labels_df, contracts_df, and scenario-specific parameters.
  2. Selects target rows (NDC, client, quarter combinations).
  3. Modifies invoice data to simulate leakage.
  4. Creates corresponding label records.
  5. Returns updated (invoice_df, labels_df, contracts_df).

All DataFrame operations use polars.

Usage:
    >>> from synthetic_data_gen.inject_anomalies import inject_missing_rebate
    >>> invoice_df, labels_df, contracts_df = inject_missing_rebate(
    ...     invoice_df, labels_df, contracts_df, count=5
    ... )
"""

from __future__ import annotations

import polars as pl

from synthetic_data_gen.config import AnomalyScenarioConfig


# ---------------------------------------------------------------------------
# Labels DataFrame schema
# ---------------------------------------------------------------------------

#: Schema used when constructing the initial empty labels DataFrame and when
#: appending new label rows.  The ``manufacturer`` and ``brand_family`` columns
#: are extended fields beyond the core AnomalyLabel pydantic model to support
#: manufacturer-brand-level anomalies (e.g. DISPUTE_SPIKE).
LABELS_SCHEMA: dict[str, type] = {
    "entity_type": pl.Utf8,
    "ndc11": pl.Utf8,
    "client_id": pl.Utf8,
    "quarter": pl.Utf8,
    "manufacturer": pl.Utf8,
    "brand_family": pl.Utf8,
    "channel": pl.Utf8,
    "anomaly_type": pl.Utf8,
    "recoverable": pl.Boolean,
    "estimated_impact": pl.Float64,
    "root_cause": pl.Utf8,
}


def make_empty_labels_df() -> pl.DataFrame:
    """
    Create an empty labels DataFrame with the canonical LABELS_SCHEMA.

    Returns:
        Empty polars DataFrame with all label columns typed correctly.
    """
    return pl.DataFrame(schema=LABELS_SCHEMA)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_random_sample(
    df: pl.DataFrame,
    count: int,
    key_cols: list[str],
    seed: int,
) -> pl.DataFrame:
    """
    Select ``count`` random unique combinations of ``key_cols`` from ``df``.

    Args:
        df: Source DataFrame to sample from.
        count: Number of unique key-column combinations to select.
        key_cols: Column names that define the sampling key.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame containing ``count`` rows (or fewer if not enough unique
        combinations exist), with only the ``key_cols`` columns present.
    """
    unique_keys = df.select(key_cols).unique()
    n_available = len(unique_keys)
    actual_count = min(count, n_available)
    return unique_keys.sample(n=actual_count, seed=seed, shuffle=True)


def _calculate_quarter_from_date(date_str: str) -> str:
    """
    Convert an ISO date string to a quarter label.

    Args:
        date_str: Date in ``YYYY-MM-DD`` format (e.g. ``"2024-01-15"``).

    Returns:
        Quarter string in ``YYYY-QN`` format (e.g. ``"2024-Q1"``).

    Example:
        >>> _calculate_quarter_from_date("2024-07-15")
        '2024-Q3'
    """
    year, month, _ = date_str.split("-")
    quarter = (int(month) - 1) // 3 + 1
    return f"{year}-Q{quarter}"


def _append_label(
    labels_df: pl.DataFrame,
    *,
    entity_type: str,
    ndc11: str | None,
    client_id: str | None,
    quarter: str,
    manufacturer: str | None,
    brand_family: str | None,
    channel: str | None,
    anomaly_type: str,
    recoverable: bool,
    estimated_impact: float,
    root_cause: str,
) -> pl.DataFrame:
    """
    Append a single label row to ``labels_df`` and return the updated DataFrame.

    All string fields default to an empty string when ``None`` is passed, so
    that the labels DataFrame remains a uniform ``Utf8`` column without nulls.

    Args:
        labels_df: Existing labels DataFrame.
        entity_type: Granularity of the labeled entity.
        ndc11: 11-digit NDC, or ``None`` for non-NDC anomalies.
        client_id: Client identifier, or ``None``.
        quarter: Affected quarter in ``YYYY-QN`` format.
        manufacturer: Manufacturer name, or ``None``.
        brand_family: Brand family name, or ``None``.
        channel: Channel name (e.g. ``"specialty"``), or ``None``.
        anomaly_type: Category of the injected anomaly.
        recoverable: Whether the leakage is theoretically recoverable.
        estimated_impact: Dollar amount of the leakage gap.
        root_cause: Human-readable explanation.

    Returns:
        Updated labels DataFrame with the new row appended.
    """
    new_row = pl.DataFrame(
        {
            "entity_type": [entity_type],
            "ndc11": [ndc11 or ""],
            "client_id": [client_id or ""],
            "quarter": [quarter],
            "manufacturer": [manufacturer or ""],
            "brand_family": [brand_family or ""],
            "channel": [channel or ""],
            "anomaly_type": [anomaly_type],
            "recoverable": [recoverable],
            "estimated_impact": [float(estimated_impact)],
            "root_cause": [root_cause],
        },
        schema=LABELS_SCHEMA,
    )
    return pl.concat([labels_df, new_row], how="diagonal_relaxed")


# ---------------------------------------------------------------------------
# Anomaly 1: Missing Rebate
# ---------------------------------------------------------------------------


def inject_missing_rebate(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    ndc_selection: str = "random",
    count: int = 5,
    seed: int = 42,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject MISSING_REBATE anomalies into the invoice DataFrame.

    For ``count`` contracted (NDC, client, quarter) rows where expected_rebate
    is positive and the channel is not excluded by the contract, set
    actual_rebate, disputed_rebate, and paid_rebate to zero to simulate a
    manufacturer failing to submit the invoice.

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame (may be empty).
        contracts_df: Contracts DataFrame with rebate terms and exclusions.
        ndc_selection: Selection strategy; currently only ``"random"``
            is supported.
        count: Number of (NDC, client, quarter) combinations to modify.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, contracts_df).
        ``contracts_df`` is returned unchanged.

    Raises:
        AssertionError: If any modified row still has a non-zero actual_rebate
            after injection.
    """
    # Candidates: invoice rows with expected_rebate > 0
    candidates = invoice_df.filter(pl.col("expected_rebate") > 0.0)

    # Sample target (ndc11, client_id, invoice_quarter) combinations
    target_keys = _get_random_sample(
        candidates,
        count=count,
        key_cols=["ndc11", "client_id", "invoice_quarter"],
        seed=seed,
    )

    if len(target_keys) == 0:
        return invoice_df, labels_df, contracts_df

    # Build a join key to identify target rows
    target_with_marker = target_keys.with_columns(
        pl.lit(True).alias("_target")
    )

    invoice_marked = invoice_df.join(
        target_with_marker,
        on=["ndc11", "client_id", "invoice_quarter"],
        how="left",
    )

    # Capture original expected_rebate for label impact calculation
    original_impact = (
        invoice_marked.filter(pl.col("_target") == True)  # noqa: E712
        .select(["ndc11", "client_id", "invoice_quarter", "expected_rebate"])
    )

    # Zero out rebate fields for target rows
    updated_invoice = invoice_marked.with_columns(
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then(pl.lit(0.0))
        .otherwise(pl.col("actual_rebate"))
        .alias("actual_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then(pl.lit(0.0))
        .otherwise(pl.col("disputed_rebate"))
        .alias("disputed_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then(pl.lit(0.0))
        .otherwise(pl.col("paid_rebate"))
        .alias("paid_rebate"),
    ).drop("_target")

    # Validation: all targeted rows now have actual_rebate == 0
    validation_rows = updated_invoice.join(
        target_with_marker.drop("_target"),
        on=["ndc11", "client_id", "invoice_quarter"],
        how="inner",
    )
    assert (
        validation_rows.filter(pl.col("actual_rebate") > 0.0).height == 0
    ), "inject_missing_rebate: some target rows still have non-zero actual_rebate"

    # Append one label row per injected anomaly
    impact_rows = original_impact.to_dicts()
    for row in impact_rows:
        labels_df = _append_label(
            labels_df,
            entity_type="ndc_group_quarter",
            ndc11=row["ndc11"],
            client_id=row["client_id"],
            quarter=row["invoice_quarter"],
            manufacturer=None,
            brand_family=None,
            channel=None,
            anomaly_type="MISSING_REBATE",
            recoverable=True,
            estimated_impact=float(row["expected_rebate"]),
            root_cause=(
                "Contracted rebate expected but no actual invoice submitted "
                "by manufacturer for this NDC-client-quarter"
            ),
        )

    return updated_invoice, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Anomaly 2: Unmapped NDC
# ---------------------------------------------------------------------------


def inject_unmapped_ndc(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    count: int = 3,
    seed: int = 42,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject UNMAPPED_NDC anomalies by creating synthetic invoice rows for new
    NDCs that are not linked to any rebate invoice.

    For each anomaly, a new NDC is fabricated under an existing brand family
    and manufacturer.  An invoice row is created with expected_rebate derived
    from the median rebate of sibling NDCs in the same brand, but actual_rebate
    and paid_rebate are set to zero to represent the omission.

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame (may be empty).
        contracts_df: Contracts DataFrame with rebate terms.
        count: Number of new (synthetic) NDC anomalies to inject.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, contracts_df).
        ``contracts_df`` is returned unchanged.

    Raises:
        AssertionError: If injected rows are not present in the output
            DataFrame, or if any injected row has a non-zero actual_rebate.
    """
    import numpy as np

    rng = np.random.default_rng(seed)

    # Join invoice to contracts to get brand_family and manufacturer
    # Use a dedup'd contract lookup (manufacturer, brand_family, client_id) -> manufacturer
    contract_lookup = (
        contracts_df.select(["manufacturer", "brand_family", "client_id"])
        .unique(subset=["manufacturer", "brand_family", "client_id"])
    )

    # Get (manufacturer, brand_family) pairs that appear in invoices
    inv_with_brand = invoice_df.join(
        contract_lookup,
        on=["manufacturer", "client_id"],
        how="left",
    )

    # Brand-level aggregation to find brands with decent rebate volume
    brand_stats = (
        inv_with_brand.filter(pl.col("expected_rebate") > 0.0)
        .group_by(["manufacturer", "brand_family", "client_id"])
        .agg(
            pl.col("expected_rebate").median().alias("median_expected_rebate"),
            pl.col("invoice_quarter").first().alias("sample_quarter"),
        )
        .filter(pl.col("brand_family").is_not_null())
        .filter(pl.col("median_expected_rebate") > 0.0)
        .sort("median_expected_rebate", descending=True)
    )

    if len(brand_stats) == 0:
        return invoice_df, labels_df, contracts_df

    sampled = brand_stats.sample(
        n=min(count, len(brand_stats)),
        seed=seed,
        shuffle=True,
    )

    # Find the maximum existing NDC as integer to ensure uniqueness
    existing_ndcs = invoice_df["ndc11"].cast(pl.Int64).max()
    if existing_ndcs is None:
        existing_ndcs = 10_000_000_000
    # Start new NDCs well above the existing range
    new_ndc_base = max(int(existing_ndcs) + 601, 10_000_000_900)

    new_rows: list[dict] = []
    injected_ndcs: list[str] = []

    for i, row in enumerate(sampled.to_dicts()):
        new_ndc = f"{new_ndc_base + i:011d}"
        injected_ndcs.append(new_ndc)

        expected_rebate = round(float(row["median_expected_rebate"]), 2)
        quarter = str(row["sample_quarter"])
        manufacturer = str(row["manufacturer"])
        client_id = str(row["client_id"])

        # Invoiced utilization: estimate from median ratio if possible; use 1.0 as fallback
        new_rows.append(
            {
                "invoice_quarter": quarter,
                "manufacturer": manufacturer,
                "ndc11": new_ndc,
                "client_id": client_id,
                "invoiced_utilization": 1.0,
                "expected_rebate": expected_rebate,
                "actual_rebate": 0.0,
                "disputed_rebate": 0.0,
                "paid_rebate": 0.0,
            }
        )

        brand_family = row.get("brand_family") or ""
        labels_df = _append_label(
            labels_df,
            entity_type="ndc_group_quarter",
            ndc11=new_ndc,
            client_id=client_id,
            quarter=quarter,
            manufacturer=manufacturer,
            brand_family=brand_family,
            channel=None,
            anomaly_type="UNMAPPED_NDC",
            recoverable=True,
            estimated_impact=expected_rebate,
            root_cause="New NDC not added to invoice feed",
        )

    if not new_rows:
        return invoice_df, labels_df, contracts_df

    new_rows_df = pl.DataFrame(
        new_rows,
        schema={
            "invoice_quarter": pl.Utf8,
            "manufacturer": pl.Utf8,
            "ndc11": pl.Utf8,
            "client_id": pl.Utf8,
            "invoiced_utilization": pl.Float64,
            "expected_rebate": pl.Float64,
            "actual_rebate": pl.Float64,
            "disputed_rebate": pl.Float64,
            "paid_rebate": pl.Float64,
        },
    )

    updated_invoice = pl.concat([invoice_df, new_rows_df], how="diagonal_relaxed")

    # Validation: injected NDCs are present and have actual_rebate == 0
    injected_rows = updated_invoice.filter(
        pl.col("ndc11").is_in(injected_ndcs)
    )
    assert injected_rows.height == len(injected_ndcs), (
        f"inject_unmapped_ndc: expected {len(injected_ndcs)} injected rows, "
        f"found {injected_rows.height}"
    )
    assert injected_rows.filter(pl.col("actual_rebate") > 0.0).height == 0, (
        "inject_unmapped_ndc: some injected rows have non-zero actual_rebate"
    )

    return updated_invoice, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Anomaly 3: Rebate Yield Collapse
# ---------------------------------------------------------------------------


def inject_rebate_yield_collapse(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    reduction_factor: float = 0.70,
    count: int = 3,
    seed: int = 42,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject REBATE_YIELD_COLLAPSE anomalies into the invoice DataFrame.

    For ``count`` high-volume (NDC, client) pairs, reduce actual_rebate by
    ``reduction_factor`` in a fixed target quarter (``2024-Q3``) without
    changing invoiced_utilization or expected_rebate.  This simulates an
    unexplained yield reduction that is detectable via time-series comparison.

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame (may be empty).
        contracts_df: Contracts DataFrame (returned unchanged).
        reduction_factor: Fraction of expected_rebate that is *removed*.
            ``0.70`` means actual_rebate is reduced to 30 % of expected.
        count: Number of (NDC, client) pairs to target.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, contracts_df).

    Raises:
        AssertionError: If any targeted row has actual_rebate greater than
            30 % of its original expected_rebate after injection (within a
            small floating-point tolerance).
    """
    # Target quarter for the collapse
    target_quarter = "2024-Q3"

    # Find top 20% by expected_rebate volume for a stable (ndc11, client_id) pair
    ndc_client_volume = (
        invoice_df.filter(pl.col("expected_rebate") > 0.0)
        .group_by(["ndc11", "client_id"])
        .agg(pl.col("expected_rebate").sum().alias("total_expected"))
        .sort("total_expected", descending=True)
    )

    # Top 20 % of (ndc11, client_id) pairs
    top_20pct_n = max(count, int(len(ndc_client_volume) * 0.20))
    top_pairs = ndc_client_volume.head(top_20pct_n)

    # Sample ``count`` pairs from the top-volume set
    sampled_pairs = _get_random_sample(
        top_pairs,
        count=count,
        key_cols=["ndc11", "client_id"],
        seed=seed,
    ).with_columns(pl.lit(True).alias("_target"))

    # Filter only rows in the target quarter
    candidates = invoice_df.filter(
        pl.col("invoice_quarter") == target_quarter
    )

    if len(candidates) == 0 or len(sampled_pairs) == 0:
        return invoice_df, labels_df, contracts_df

    candidates_marked = candidates.join(
        sampled_pairs,
        on=["ndc11", "client_id"],
        how="left",
    )

    # Calculate the impact before modification
    impact_rows = (
        candidates_marked.filter(pl.col("_target") == True)  # noqa: E712
        .select(["ndc11", "client_id", "invoice_quarter", "expected_rebate"])
        .to_dicts()
    )

    keep_fraction = 1.0 - reduction_factor

    # Apply reduction to actual_rebate (keep ``keep_fraction`` of expected)
    candidates_updated = candidates_marked.with_columns(
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then(
            (pl.col("expected_rebate") * keep_fraction).round(2)
        )
        .otherwise(pl.col("actual_rebate"))
        .alias("actual_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then(pl.lit(0.0))
        .otherwise(pl.col("paid_rebate"))
        .alias("paid_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then(pl.lit(0.0))
        .otherwise(pl.col("disputed_rebate"))
        .alias("disputed_rebate"),
    ).drop("_target")

    # Rebuild the full invoice DataFrame: non-target-quarter rows unchanged
    other_quarters = invoice_df.filter(pl.col("invoice_quarter") != target_quarter)
    updated_invoice = pl.concat([other_quarters, candidates_updated], how="diagonal_relaxed")

    # Validation: targeted rows have reduced actual_rebate
    target_rows = updated_invoice.join(
        sampled_pairs.drop("_target"),
        on=["ndc11", "client_id"],
        how="inner",
    ).filter(pl.col("invoice_quarter") == target_quarter)

    tolerance = 0.01
    violations = target_rows.filter(
        pl.col("actual_rebate") > (pl.col("expected_rebate") * keep_fraction + tolerance)
    )
    assert violations.height == 0, (
        f"inject_rebate_yield_collapse: {violations.height} rows exceed allowed actual_rebate"
    )

    # Append labels
    for row in impact_rows:
        impact = round(float(row["expected_rebate"]) * reduction_factor, 2)
        labels_df = _append_label(
            labels_df,
            entity_type="ndc_group_quarter",
            ndc11=row["ndc11"],
            client_id=row["client_id"],
            quarter=row["invoice_quarter"],
            manufacturer=None,
            brand_family=None,
            channel=None,
            anomaly_type="REBATE_YIELD_COLLAPSE",
            recoverable=True,
            estimated_impact=impact,
            root_cause="Unexplained yield reduction in high-volume product",
        )

    return updated_invoice, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Anomaly 4: Specialty Channel Omission
# ---------------------------------------------------------------------------


def inject_specialty_channel_omission(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    count: int = 4,
    seed: int = 42,
    claims_df: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject CHANNEL_OMISSION anomalies by zeroing rebates for the specialty
    channel while leaving retail/mail rebates intact.

    Because the existing invoice grain is cross-channel, this function
    creates a synthetic per-channel split for the targeted
    (ndc11, client_id, invoice_quarter) rows:

    1. An updated ``"retail"``-channel row retains the rebate proportional to
       retail utilization.
    2. A new ``"specialty"``-channel row is added with actual_rebate = 0,
       representing the omission.

    A ``channel`` column is added to invoice_df for all rows (default ``"all"``
    for untouched rows) to preserve the schema.

    Args:
        invoice_df: Invoice DataFrame (may or may not already have a ``channel``
            column; if absent it will be added).
        labels_df: Existing anomaly labels DataFrame.
        contracts_df: Contracts DataFrame (returned unchanged).
        count: Number of (NDC, client) pairs to target.
        seed: Random seed for reproducibility.
        claims_df: Optional claims DataFrame used to estimate the specialty
            utilization fraction.  If ``None``, a 20 % specialty fraction is
            assumed.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, contracts_df).
        ``updated_invoice_df`` includes a ``channel`` column.

    Raises:
        AssertionError: If any injected specialty row has non-zero actual_rebate.
    """
    # Add channel column to invoice_df if absent
    if "channel" not in invoice_df.columns:
        invoice_df = invoice_df.with_columns(pl.lit("all").alias("channel"))

    # Find (ndc11, client_id, invoice_quarter) candidates with non-zero expected
    candidates = invoice_df.filter(
        (pl.col("expected_rebate") > 0.0) & (pl.col("channel") == "all")
    )

    if len(candidates) == 0:
        return invoice_df, labels_df, contracts_df

    sampled_keys = _get_random_sample(
        candidates,
        count=count,
        key_cols=["ndc11", "client_id", "invoice_quarter"],
        seed=seed,
    ).with_columns(pl.lit(True).alias("_target"))

    # Estimate specialty fraction per (ndc11, client_id, quarter) from claims if available
    specialty_fractions: dict[tuple[str, str, str], float] = {}
    if claims_df is not None and len(claims_df) > 0:
        # Build quarter from fill_date
        claims_with_q = claims_df.with_columns(
            (
                pl.col("fill_date").dt.year().cast(pl.Utf8)
                + pl.lit("-Q")
                + ((pl.col("fill_date").dt.month() - 1) // 3 + 1).cast(pl.Utf8)
            ).alias("_quarter"),
            pl.col("group_id").alias("client_id"),
        )
        channel_util = (
            claims_with_q.group_by(["ndc11", "client_id", "_quarter", "channel"])
            .agg(pl.col("quantity").sum().alias("util"))
        )
        total_util = (
            channel_util.group_by(["ndc11", "client_id", "_quarter"])
            .agg(pl.col("util").sum().alias("total_util"))
        )
        channel_frac = channel_util.join(
            total_util, on=["ndc11", "client_id", "_quarter"], how="left"
        ).with_columns(
            (pl.col("util") / pl.col("total_util")).alias("fraction")
        )
        spec_frac = channel_frac.filter(pl.col("channel") == "specialty")

        for r in spec_frac.to_dicts():
            key = (r["ndc11"], r["client_id"], r["_quarter"])
            specialty_fractions[key] = float(r["fraction"])

    default_specialty_fraction = 0.20

    # Mark target rows in invoice_df
    invoice_marked = invoice_df.join(
        sampled_keys,
        on=["ndc11", "client_id", "invoice_quarter"],
        how="left",
    )

    # Collect target rows for splitting
    target_rows = invoice_marked.filter(pl.col("_target") == True).drop("_target")  # noqa: E712
    non_target_rows = invoice_marked.filter(pl.col("_target").is_null()).drop("_target")

    if len(target_rows) == 0:
        return invoice_df, labels_df, contracts_df

    specialty_new_rows = []
    retail_adjusted_rows = []

    for row in target_rows.to_dicts():
        key = (row["ndc11"], row["client_id"], row["invoice_quarter"])
        spec_frac = specialty_fractions.get(key, default_specialty_fraction)
        retail_frac = 1.0 - spec_frac

        expected = float(row["expected_rebate"])
        actual = float(row["actual_rebate"])
        utilization = float(row["invoiced_utilization"])

        specialty_expected = round(expected * spec_frac, 2)
        retail_actual = round(actual * retail_frac, 2)
        retail_expected = round(expected * retail_frac, 2)
        retail_utilization = round(utilization * retail_frac, 4)
        specialty_utilization = round(utilization * spec_frac, 4)

        # Adjusted retail row (retains rebate)
        retail_row = dict(row)
        retail_row["channel"] = "retail"
        retail_row["expected_rebate"] = retail_expected
        retail_row["actual_rebate"] = retail_actual
        retail_row["paid_rebate"] = retail_actual
        retail_row["disputed_rebate"] = 0.0
        retail_row["invoiced_utilization"] = retail_utilization
        retail_adjusted_rows.append(retail_row)

        # Specialty row with actual_rebate = 0 (the omission)
        specialty_row = dict(row)
        specialty_row["channel"] = "specialty"
        specialty_row["expected_rebate"] = specialty_expected
        specialty_row["actual_rebate"] = 0.0
        specialty_row["paid_rebate"] = 0.0
        specialty_row["disputed_rebate"] = 0.0
        specialty_row["invoiced_utilization"] = specialty_utilization
        specialty_new_rows.append(specialty_row)

        labels_df = _append_label(
            labels_df,
            entity_type="ndc_group_quarter_channel",
            ndc11=row["ndc11"],
            client_id=row["client_id"],
            quarter=row["invoice_quarter"],
            manufacturer=row.get("manufacturer"),
            brand_family=None,
            channel="specialty",
            anomaly_type="CHANNEL_OMISSION",
            recoverable=True,
            estimated_impact=specialty_expected,
            root_cause="Specialty channel claims excluded from rebate invoice",
        )

    # Assemble parts
    schema = invoice_df.schema
    retail_df = pl.DataFrame(retail_adjusted_rows, schema=schema) if retail_adjusted_rows else pl.DataFrame(schema=schema)
    specialty_df = pl.DataFrame(specialty_new_rows, schema=schema) if specialty_new_rows else pl.DataFrame(schema=schema)

    updated_invoice = pl.concat(
        [non_target_rows, retail_df, specialty_df],
        how="diagonal_relaxed",
    )

    # Validation: specialty rows have actual_rebate == 0
    injected_specialty = updated_invoice.filter(pl.col("channel") == "specialty")
    assert injected_specialty.filter(pl.col("actual_rebate") > 0.0).height == 0, (
        "inject_specialty_channel_omission: specialty rows have non-zero actual_rebate"
    )

    return updated_invoice, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Anomaly 5: Unit Conversion Error
# ---------------------------------------------------------------------------


def inject_unit_conversion_error(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    unit_divisor: int = 10,
    count: int = 2,
    seed: int = 42,
    drugs_df: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject UNIT_CONVERSION_ERROR anomalies into the invoice DataFrame.

    Selects ``count`` (NDC, client, quarter) rows (preferably specialty/injectable
    products) and divides invoiced_utilization by ``unit_divisor``, then
    recalculates expected_rebate and actual_rebate based on the reduced units.
    The resulting paid_rebate is set to the recalculated actual to simulate a
    manufacturer invoicing on a per-pack basis instead of per-unit.

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame.
        contracts_df: Contracts DataFrame with rebate terms.
        unit_divisor: Factor by which invoiced_utilization is divided
            (e.g. ``10`` for single-unit vs. pack confusion).
        count: Number of (NDC, client, quarter) combinations to modify.
        seed: Random seed for reproducibility.
        drugs_df: Optional drugs DataFrame used to prefer specialty/injectable
            NDCs for selection.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, contracts_df).

    Raises:
        AssertionError: If any targeted row has invoiced_utilization greater
            than original / unit_divisor (within tolerance) after injection.
    """
    # Prefer specialty NDCs when drugs_df is available
    if drugs_df is not None and len(drugs_df) > 0:
        specialty_ndcs = set(
            drugs_df.filter(pl.col("specialty_flag") == True)  # noqa: E712
            .get_column("ndc11")
            .to_list()
        )
        candidates = invoice_df.filter(
            (pl.col("expected_rebate") > 0.0)
            & (pl.col("ndc11").is_in(specialty_ndcs))
        )
        if len(candidates) < count:
            # Fall back to all non-zero rebate rows
            candidates = invoice_df.filter(pl.col("expected_rebate") > 0.0)
    else:
        candidates = invoice_df.filter(pl.col("expected_rebate") > 0.0)

    target_keys = _get_random_sample(
        candidates,
        count=count,
        key_cols=["ndc11", "client_id", "invoice_quarter"],
        seed=seed,
    ).with_columns(pl.lit(True).alias("_target"))

    if len(target_keys) == 0:
        return invoice_df, labels_df, contracts_df

    # Get contract rebate terms for recalculation
    # We'll use the ratio: new_expected = old_expected * (1 / unit_divisor)
    # (this preserves whatever formula was applied during invoice generation)
    invoice_marked = invoice_df.join(
        target_keys,
        on=["ndc11", "client_id", "invoice_quarter"],
        how="left",
    )

    # Capture original values for impact calculation
    original_rows = (
        invoice_marked.filter(pl.col("_target") == True)  # noqa: E712
        .select([
            "ndc11", "client_id", "invoice_quarter",
            "invoiced_utilization", "expected_rebate",
        ])
        .to_dicts()
    )

    recip = 1.0 / float(unit_divisor)

    updated_invoice = invoice_marked.with_columns(
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then((pl.col("invoiced_utilization") * recip).round(4))
        .otherwise(pl.col("invoiced_utilization"))
        .alias("invoiced_utilization"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then((pl.col("expected_rebate") * recip).round(2))
        .otherwise(pl.col("expected_rebate"))
        .alias("expected_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then((pl.col("actual_rebate") * recip).round(2))
        .otherwise(pl.col("actual_rebate"))
        .alias("actual_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then((pl.col("actual_rebate") * recip).round(2))
        .otherwise(pl.col("paid_rebate"))
        .alias("paid_rebate"),
    ).drop("_target")

    # Validation: utilization has been reduced
    target_after = updated_invoice.join(
        target_keys.drop("_target"),
        on=["ndc11", "client_id", "invoice_quarter"],
        how="inner",
    )
    for orig in original_rows:
        expected_util = round(float(orig["invoiced_utilization"]) * recip, 4)
        row_check = target_after.filter(
            (pl.col("ndc11") == orig["ndc11"])
            & (pl.col("client_id") == orig["client_id"])
            & (pl.col("invoice_quarter") == orig["invoice_quarter"])
        )
        if len(row_check) > 0:
            actual_util = float(row_check["invoiced_utilization"][0])
            assert abs(actual_util - expected_util) <= 0.01, (
                f"inject_unit_conversion_error: utilization mismatch for "
                f"ndc={orig['ndc11']} client={orig['client_id']} "
                f"q={orig['invoice_quarter']}: expected {expected_util}, got {actual_util}"
            )

    # Append labels
    for orig in original_rows:
        orig_expected = float(orig["expected_rebate"])
        new_expected = round(orig_expected * recip, 2)
        impact = round(orig_expected - new_expected, 2)
        labels_df = _append_label(
            labels_df,
            entity_type="ndc_group_quarter",
            ndc11=orig["ndc11"],
            client_id=orig["client_id"],
            quarter=orig["invoice_quarter"],
            manufacturer=None,
            brand_family=None,
            channel=None,
            anomaly_type="UNIT_CONVERSION_ERROR",
            recoverable=True,
            estimated_impact=impact,
            root_cause=f"Invoiced units divided by {unit_divisor} (e.g., single units vs. packs)",
        )

    return updated_invoice, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Anomaly 6: Dispute Spike
# ---------------------------------------------------------------------------


def inject_dispute_spike(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    dispute_fraction: float = 0.50,
    count: int = 3,
    seed: int = 42,
    drugs_df: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject DISPUTE_SPIKE anomalies into the invoice DataFrame.

    Selects ``count`` (manufacturer, brand_family, quarter) tuples and, for
    all invoice rows matching those tuples, sets disputed_rebate to
    ``dispute_fraction`` of actual_rebate while reducing paid_rebate by the
    same amount.  invoiced_utilization and expected_rebate are left unchanged.

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame.
        contracts_df: Contracts DataFrame with brand_family mapping.
        dispute_fraction: Fraction of actual_rebate to be disputed (0–1).
            E.g. ``0.50`` means 50 % of actual_rebate becomes disputed.
        count: Number of (manufacturer, brand_family, quarter) tuples to target.
        seed: Random seed for reproducibility.
        drugs_df: Optional drugs DataFrame used to enrich invoice rows with
            brand_family for selection.  If ``None``, the brand_family column
            must already be present in invoice_df or in contracts_df.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, contracts_df).

    Raises:
        AssertionError: If paid_rebate exceeds actual_rebate for any targeted
            row after injection.
    """
    # We need brand_family on the invoice to group by manufacturer+brand
    if drugs_df is not None and "brand_family" not in invoice_df.columns:
        brand_lookup = drugs_df.select(["ndc11", "brand_family"]).unique("ndc11")
        invoice_df = invoice_df.join(brand_lookup, on="ndc11", how="left")

    if "brand_family" not in invoice_df.columns:
        # Try to get brand_family from contracts (manufacturer, brand_family, client_id)
        brand_lookup = (
            contracts_df.select(["manufacturer", "brand_family", "client_id"])
            .unique(subset=["manufacturer", "brand_family", "client_id"])
        )
        invoice_df = invoice_df.join(
            brand_lookup,
            on=["manufacturer", "client_id"],
            how="left",
        )

    # Find (manufacturer, brand_family, invoice_quarter) tuples with high volume
    candidate_tuples = (
        invoice_df.filter(
            (pl.col("actual_rebate") > 0.0) & pl.col("brand_family").is_not_null()
        )
        .group_by(["manufacturer", "brand_family", "invoice_quarter"])
        .agg(pl.col("actual_rebate").sum().alias("total_actual"))
        .sort("total_actual", descending=True)
    )

    if len(candidate_tuples) == 0:
        return invoice_df, labels_df, contracts_df

    sampled_tuples = _get_random_sample(
        candidate_tuples,
        count=count,
        key_cols=["manufacturer", "brand_family", "invoice_quarter"],
        seed=seed,
    ).with_columns(pl.lit(True).alias("_target"))

    # Mark rows matching selected (manufacturer, brand_family, invoice_quarter)
    invoice_marked = invoice_df.join(
        sampled_tuples,
        on=["manufacturer", "brand_family", "invoice_quarter"],
        how="left",
    )

    # Capture aggregate impact per (manufacturer, brand_family, quarter)
    impact_agg = (
        invoice_marked.filter(pl.col("_target") == True)  # noqa: E712
        .group_by(["manufacturer", "brand_family", "invoice_quarter"])
        .agg(
            (pl.col("actual_rebate") * dispute_fraction).sum().alias("total_disputed")
        )
        .to_dicts()
    )

    updated_invoice = invoice_marked.with_columns(
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then((pl.col("actual_rebate") * dispute_fraction).round(2))
        .otherwise(pl.col("disputed_rebate"))
        .alias("disputed_rebate"),
        pl.when(pl.col("_target") == True)  # noqa: E712
        .then((pl.col("actual_rebate") * (1.0 - dispute_fraction)).round(2))
        .otherwise(pl.col("paid_rebate"))
        .alias("paid_rebate"),
    ).drop("_target")

    # Validation: paid_rebate <= actual_rebate for all rows
    violations = updated_invoice.filter(
        pl.col("paid_rebate") > (pl.col("actual_rebate") + 0.01)
    )
    assert violations.height == 0, (
        f"inject_dispute_spike: {violations.height} rows with paid_rebate > actual_rebate"
    )

    # Append labels
    for agg_row in impact_agg:
        labels_df = _append_label(
            labels_df,
            entity_type="manufacturer_brand_quarter",
            ndc11=None,
            client_id=None,
            quarter=agg_row["invoice_quarter"],
            manufacturer=agg_row["manufacturer"],
            brand_family=agg_row["brand_family"],
            channel=None,
            anomaly_type="DISPUTE_SPIKE",
            recoverable=True,
            estimated_impact=round(float(agg_row["total_disputed"]), 2),
            root_cause=(
                "Manufacturer disputes spike in quarter; payment delayed/reduced"
            ),
        )

    return updated_invoice, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Anomaly 7: Guarantee True-Up Missing
# ---------------------------------------------------------------------------


def inject_guarantee_true_up_missing(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    count: int = 2,
    seed: int = 42,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Inject GUARANTEE_TRUE_UP_MISSING anomalies by flagging PMPM_GUARANTEE
    contracts where actual rebates fall short of the annual minimum guarantee.

    For each selected contract, this function:

    1. Sums actual_rebate across all four quarters of 2024 for that
       (manufacturer, brand_family, client_id).
    2. Calculates the true-up gap: ``max(0, minimum_guarantee × 12 - sum_actual)``.
    3. If the gap is positive, adds a ``missing_guarantee_true_up = True`` flag
       to ``contracts_df`` for the selected contract.
    4. Creates a label row with the dollar gap as estimated_impact.

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame.
        contracts_df: Contracts DataFrame; will have a boolean column
            ``missing_guarantee_true_up`` added and set to ``True`` for the
            targeted contracts.
        count: Number of PMPM_GUARANTEE contracts to target.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (invoice_df, updated_labels_df, updated_contracts_df).
        ``invoice_df`` is returned unchanged; ``contracts_df`` gets the
        ``missing_guarantee_true_up`` flag column.

    Raises:
        AssertionError: If the flagged contracts do not have
            ``missing_guarantee_true_up == True`` after injection, or if any
            estimated_impact is negative.
    """
    # Ensure the flag column exists
    if "missing_guarantee_true_up" not in contracts_df.columns:
        contracts_df = contracts_df.with_columns(
            pl.lit(False).alias("missing_guarantee_true_up")
        )

    # Select PMPM_GUARANTEE contracts with a set minimum_guarantee
    pmpm_contracts = contracts_df.filter(
        (pl.col("rebate_basis") == "PMPM_GUARANTEE")
        & (pl.col("minimum_guarantee").is_not_null())
        & (pl.col("minimum_guarantee") > 0.0)
    )

    if len(pmpm_contracts) == 0:
        return invoice_df, labels_df, contracts_df

    # Sample ``count`` PMPM contracts
    sampled = pmpm_contracts.sample(
        n=min(count, len(pmpm_contracts)),
        seed=seed,
        shuffle=True,
    )

    # For each sampled contract, compute the true-up gap
    year_quarters = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"]

    flagged_contract_keys: list[tuple[str, str, str]] = []

    for contract_row in sampled.to_dicts():
        mfr = str(contract_row["manufacturer"])
        brand = str(contract_row["brand_family"])
        client = str(contract_row["client_id"])
        min_guarantee = float(contract_row["minimum_guarantee"])

        # Sum actual_rebate for the 4 quarters of 2024
        annual_rows = invoice_df.filter(
            (pl.col("manufacturer") == mfr)
            & (pl.col("client_id") == client)
            & (pl.col("invoice_quarter").is_in(year_quarters))
        )

        # Try brand-level matching via contracts lookup if possible
        # Since invoice doesn't have brand_family, we approximate by manufacturer + client
        sum_actual = float(annual_rows.select("actual_rebate").sum().item() or 0.0)

        # PMPM guarantee × 12 months
        annual_guarantee = min_guarantee * 12.0
        true_up_gap = max(0.0, annual_guarantee - sum_actual)

        if true_up_gap <= 0.0:
            # Artificially reduce sum_actual to force a gap for the anomaly
            sum_actual_adj = annual_guarantee * 0.70  # 30% shortfall
            true_up_gap = annual_guarantee - sum_actual_adj

        true_up_gap = round(true_up_gap, 2)
        flagged_contract_keys.append((mfr, brand, client))

        labels_df = _append_label(
            labels_df,
            entity_type="manufacturer_brand_client_year",
            ndc11=None,
            client_id=client,
            quarter="2024-Q4",  # Use Q4 as the representative quarter for the annual label
            manufacturer=mfr,
            brand_family=brand,
            channel=None,
            anomaly_type="GUARANTEE_TRUE_UP_MISSING",
            recoverable=True,
            estimated_impact=true_up_gap,
            root_cause="PMPM guarantee shortfall not paid; true-up omitted",
        )

    # Flag the contracts
    if flagged_contract_keys:
        flag_df = pl.DataFrame(
            {
                "manufacturer": [k[0] for k in flagged_contract_keys],
                "brand_family": [k[1] for k in flagged_contract_keys],
                "client_id": [k[2] for k in flagged_contract_keys],
                "_flag": [True] * len(flagged_contract_keys),
            }
        )

        contracts_marked = contracts_df.join(
            flag_df,
            on=["manufacturer", "brand_family", "client_id"],
            how="left",
        )

        contracts_df = contracts_marked.with_columns(
            pl.when(pl.col("_flag") == True)  # noqa: E712
            .then(pl.lit(True))
            .otherwise(pl.col("missing_guarantee_true_up"))
            .alias("missing_guarantee_true_up")
        ).drop("_flag")

    # Validation: all flagged contracts now have missing_guarantee_true_up == True
    for mfr, brand, client in flagged_contract_keys:
        flagged_rows = contracts_df.filter(
            (pl.col("manufacturer") == mfr)
            & (pl.col("brand_family") == brand)
            & (pl.col("client_id") == client)
            & (pl.col("missing_guarantee_true_up") == True)  # noqa: E712
        )
        assert flagged_rows.height > 0, (
            f"inject_guarantee_true_up_missing: contract ({mfr}, {brand}, {client}) "
            f"not flagged"
        )

    # Validation: all estimated_impact values in the new labels are non-negative
    new_label_impacts = labels_df.filter(
        pl.col("anomaly_type") == "GUARANTEE_TRUE_UP_MISSING"
    ).select("estimated_impact")
    assert new_label_impacts.filter(pl.col("estimated_impact") < 0.0).height == 0, (
        "inject_guarantee_true_up_missing: negative estimated_impact found"
    )

    return invoice_df, labels_df, contracts_df


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

#: Mapping from scenario_type string to injection function.
_SCENARIO_DISPATCH: dict[str, str] = {
    "missing_rebate": "inject_missing_rebate",
    "unmapped_ndc": "inject_unmapped_ndc",
    "rebate_yield_collapse": "inject_rebate_yield_collapse",
    "specialty_channel_omission": "inject_specialty_channel_omission",
    "unit_conversion_error": "inject_unit_conversion_error",
    "dispute_spike": "inject_dispute_spike",
    "guarantee_true_up_missing": "inject_guarantee_true_up_missing",
}


def inject_scenario(
    invoice_df: pl.DataFrame,
    labels_df: pl.DataFrame,
    contracts_df: pl.DataFrame,
    scenario_config: AnomalyScenarioConfig,
    seed: int = 42,
    drugs_df: pl.DataFrame | None = None,
    claims_df: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Top-level orchestrator that routes to the correct injection function based
    on ``scenario_config.scenario_type``.

    Supported scenario types (must match ``AnomalyScenarioConfig.scenario_type``):

    * ``"missing_rebate"``        → :func:`inject_missing_rebate`
    * ``"unmapped_ndc"``          → :func:`inject_unmapped_ndc`
    * ``"rebate_yield_collapse"`` → :func:`inject_rebate_yield_collapse`
    * ``"specialty_channel_omission"`` → :func:`inject_specialty_channel_omission`
    * ``"unit_conversion_error"`` → :func:`inject_unit_conversion_error`
    * ``"dispute_spike"``         → :func:`inject_dispute_spike`
    * ``"guarantee_true_up_missing"`` → :func:`inject_guarantee_true_up_missing`

    Args:
        invoice_df: Invoice DataFrame at (manufacturer, ndc11, client_id,
            invoice_quarter) grain.
        labels_df: Existing anomaly labels DataFrame.
        contracts_df: Contracts DataFrame.
        scenario_config: Configuration object that specifies the scenario type,
            count, and additional parameters.
        seed: Base random seed; added to any per-scenario offset.
        drugs_df: Optional drugs DataFrame forwarded to functions that need it.
        claims_df: Optional claims DataFrame forwarded to functions that need it.

    Returns:
        Tuple of (updated_invoice_df, updated_labels_df, updated_contracts_df).

    Raises:
        ValueError: If ``scenario_config.scenario_type`` is not a recognised
            scenario type.
    """
    scenario_type = scenario_config.scenario_type
    count = scenario_config.count
    params = scenario_config.parameters

    if scenario_type not in _SCENARIO_DISPATCH:
        raise ValueError(
            f"Unknown scenario_type: {scenario_type!r}. "
            f"Valid options: {sorted(_SCENARIO_DISPATCH.keys())}"
        )

    if scenario_type == "missing_rebate":
        return inject_missing_rebate(
            invoice_df,
            labels_df,
            contracts_df,
            ndc_selection=params.get("ndc_selection", "random"),
            count=count,
            seed=seed,
        )

    elif scenario_type == "unmapped_ndc":
        return inject_unmapped_ndc(
            invoice_df,
            labels_df,
            contracts_df,
            count=count,
            seed=seed,
        )

    elif scenario_type == "rebate_yield_collapse":
        return inject_rebate_yield_collapse(
            invoice_df,
            labels_df,
            contracts_df,
            reduction_factor=float(params.get("reduction_factor", 0.70)),
            count=count,
            seed=seed,
        )

    elif scenario_type == "specialty_channel_omission":
        return inject_specialty_channel_omission(
            invoice_df,
            labels_df,
            contracts_df,
            count=count,
            seed=seed,
            claims_df=claims_df,
        )

    elif scenario_type == "unit_conversion_error":
        return inject_unit_conversion_error(
            invoice_df,
            labels_df,
            contracts_df,
            unit_divisor=int(params.get("unit_divisor", 10)),
            count=count,
            seed=seed,
            drugs_df=drugs_df,
        )

    elif scenario_type == "dispute_spike":
        return inject_dispute_spike(
            invoice_df,
            labels_df,
            contracts_df,
            dispute_fraction=float(params.get("dispute_fraction", 0.50)),
            count=count,
            seed=seed,
            drugs_df=drugs_df,
        )

    elif scenario_type == "guarantee_true_up_missing":
        return inject_guarantee_true_up_missing(
            invoice_df,
            labels_df,
            contracts_df,
            count=count,
            seed=seed,
        )

    # Should never reach here given the dispatch check above
    raise ValueError(f"Unhandled scenario_type: {scenario_type!r}")
