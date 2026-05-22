"""
Contract generator for the synthetic Rx rebate data generation system.

Produces manufacturer rebate contract records for (manufacturer, brand_family)
combinations found in the drug master, with 1–3 contracts per brand covering
a random 10–30 of the 50 client groups.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from synthetic_data_gen.config import BaseConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REBATE_BASIS_OPTIONS = [
    "PER_30_DAY_SCRIPT",
    "PERCENT_GROSS_COST",
    "PER_UNIT",
    "PMPM_GUARANTEE",
]
_REBATE_BASIS_PROBS = [0.40, 0.30, 0.20, 0.10]

# Rebate rate ranges by basis type
_REBATE_RATE_RANGES: dict[str, tuple[float, float]] = {
    "PER_30_DAY_SCRIPT": (0.50, 5.00),
    "PERCENT_GROSS_COST": (0.05, 0.20),
    "PER_UNIT": (0.10, 1.00),
    "PMPM_GUARANTEE": (0.0, 0.0),  # rate unused; minimum_guarantee used instead
}

_MIN_GUARANTEE_RANGE = (10_000.0, 100_000.0)

_CHANNEL_OPTIONS = ["retail", "mail", "specialty"]
_LOB_OPTIONS = ["Medicaid", "Medicare", "Commercial", "Exchange"]

_CONTRACT_DATE_START = date(2024, 1, 1)
_CONTRACT_DATE_END = date(2025, 12, 31)

# How many of the 50 groups each brand has contracts with
_MIN_GROUPS_PER_BRAND = 10
_MAX_GROUPS_PER_BRAND = 30


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------


class ContractGenerator:
    """
    Generates rebate contract records for (manufacturer, brand_family) pairs.

    Creates 1–3 contracts per (manufacturer, brand_family) covering a random
    subset of client groups. Supports all four rebate_basis types from the
    schema, with appropriate rate distributions for each.

    Args:
        config: BaseConfig instance.
        drugs: polars DataFrame produced by DrugGenerator.
        seed: Integer seed for the numpy random number generator.
    """

    def __init__(
        self,
        config: BaseConfig,
        drugs: pl.DataFrame,
        seed: int = 42,
    ) -> None:
        self.config = config
        self.drugs = drugs
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pl.DataFrame:
        """
        Generate rebate contract records.

        Returns:
            polars DataFrame with columns:
            manufacturer, brand_family, client_id, effective_date_start,
            effective_date_end, rebate_basis, rebate_rate,
            minimum_guarantee, channel_exclusions, lob_exclusions.
        """
        cfg = self.config
        n_groups = cfg.n_groups  # 50
        all_group_ids = [f"G{g:03d}" for g in range(n_groups)]

        # Unique (manufacturer, brand_family) pairs from drugs
        brand_pairs = (
            self.drugs.select(["manufacturer", "brand_family"])
            .unique()
            .sort(["manufacturer", "brand_family"])
        )

        manufacturers_col = brand_pairs.get_column("manufacturer").to_list()
        brands_col = brand_pairs.get_column("brand_family").to_list()

        rows: list[dict] = []

        for mfr, brand in zip(manufacturers_col, brands_col):
            # 1–3 contracts per brand
            n_contracts = int(self.rng.integers(1, 4))

            for _ in range(n_contracts):
                # Random 10–30 client groups covered by this contract
                n_clients = int(
                    self.rng.integers(
                        _MIN_GROUPS_PER_BRAND, _MAX_GROUPS_PER_BRAND + 1
                    )
                )
                client_subset = self.rng.choice(
                    all_group_ids, size=n_clients, replace=False
                ).tolist()

                # Rebate basis
                basis_idx = int(
                    self.rng.choice(len(_REBATE_BASIS_OPTIONS), p=_REBATE_BASIS_PROBS)
                )
                rebate_basis = _REBATE_BASIS_OPTIONS[basis_idx]

                # Rebate rate
                lo, hi = _REBATE_RATE_RANGES[rebate_basis]
                if rebate_basis == "PMPM_GUARANTEE":
                    rebate_rate = 0.0
                    minimum_guarantee: float | None = float(
                        self.rng.uniform(*_MIN_GUARANTEE_RANGE)
                    )
                else:
                    rebate_rate = float(self.rng.uniform(lo, hi))
                    minimum_guarantee = None

                # Channel exclusions (0–1 channel excluded, ~30% chance)
                channel_exclusions: list[str] = []
                if self.rng.random() < 0.30:
                    excl = self.rng.choice(_CHANNEL_OPTIONS)
                    channel_exclusions = [str(excl)]

                # LOB exclusions (~25% chance of excluding 1 LOB)
                lob_exclusions: list[str] = []
                if self.rng.random() < 0.25:
                    excl_lob = self.rng.choice(_LOB_OPTIONS)
                    lob_exclusions = [str(excl_lob)]

                for client_id in client_subset:
                    rows.append(
                        {
                            "manufacturer": mfr,
                            "brand_family": brand,
                            "client_id": client_id,
                            "effective_date_start": _CONTRACT_DATE_START,
                            "effective_date_end": _CONTRACT_DATE_END,
                            "rebate_basis": rebate_basis,
                            "rebate_rate": round(rebate_rate, 6),
                            "minimum_guarantee": minimum_guarantee,
                            "channel_exclusions": channel_exclusions,
                            "lob_exclusions": lob_exclusions,
                        }
                    )

        # Build DataFrame from row list
        df = pl.DataFrame(
            {
                "manufacturer": [r["manufacturer"] for r in rows],
                "brand_family": [r["brand_family"] for r in rows],
                "client_id": [r["client_id"] for r in rows],
                "effective_date_start": [r["effective_date_start"] for r in rows],
                "effective_date_end": [r["effective_date_end"] for r in rows],
                "rebate_basis": [r["rebate_basis"] for r in rows],
                "rebate_rate": [r["rebate_rate"] for r in rows],
                "minimum_guarantee": [r["minimum_guarantee"] for r in rows],
                "channel_exclusions": [r["channel_exclusions"] for r in rows],
                "lob_exclusions": [r["lob_exclusions"] for r in rows],
            }
        ).with_columns(
            pl.col("effective_date_start").cast(pl.Date),
            pl.col("effective_date_end").cast(pl.Date),
        )

        return df
