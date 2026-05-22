"""
Drug master generator for the synthetic Rx rebate data generation system.

Produces drug reference records keyed to the NDC11 codes that appear in
the generated claims, including brand family, manufacturer, GPI class,
specialty flag, package size, and effective dates.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from synthetic_data_gen.config import BaseConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Representative GPI-14 therapeutic class codes (first 4 digits used as class)
_GPI_CODES: list[str] = [
    "0101",  # Penicillins
    "0102",  # Cephalosporins
    "0121",  # Macrolides
    "0201",  # Antifungals
    "0241",  # Anti-inflammatories (NSAIDs)
    "0281",  # Antineoplastics
    "0331",  # Cardiovascular / Antihypertensives
    "0340",  # Beta Blockers
    "0360",  # Calcium Channel Blockers
    "0380",  # ACE Inhibitors / ARBs
    "0400",  # Diuretics
    "0510",  # Anticoagulants
    "0590",  # Antidiabetics (Oral)
    "0610",  # Insulin
    "2140",  # Respiratory / Bronchodilators
    "2430",  # Immunosuppressants / Biologics
    "2680",  # Gastrointestinals / PPIs
    "2724",  # Antidepressants
    "2750",  # Antipsychotics
    "2780",  # ADHD / CNS Stimulants
]

# Package sizes for oral solids vs. injectables
_ORAL_PACKAGE_SIZES = [30, 60, 90]
_INJECTABLE_PACKAGE_SIZES = [1, 10, 100]

# GPI prefixes typically associated with injectables
_INJECTABLE_GPI_PREFIXES = {"0281", "0510", "0610", "2430"}

_LAUNCH_DATE_START = date(2020, 1, 1)
_LAUNCH_DATE_END = date(2024, 1, 1)


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------


class DrugGenerator:
    """
    Generates drug master reference records for all NDCs found in claims.

    Produces a polars DataFrame with ndc11, brand_family, manufacturer,
    gpi_class, specialty_flag, package_size, effective_date_start,
    effective_date_end, and launch_date columns.

    Args:
        config: BaseConfig instance.
        claims: polars DataFrame produced by ClaimsGenerator.
        seed: Integer seed for the numpy random number generator.
    """

    def __init__(
        self,
        config: BaseConfig,
        claims: pl.DataFrame,
        seed: int = 42,
    ) -> None:
        self.config = config
        self.claims = claims
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pl.DataFrame:
        """
        Generate drug master records for each unique NDC in claims.

        Returns:
            polars DataFrame with columns:
            ndc11, brand_family, manufacturer, gpi_class, specialty_flag,
            package_size, effective_date_start, effective_date_end, launch_date.
        """
        cfg = self.config

        # Extract unique NDCs from claims, sorted for determinism
        unique_ndcs: list[str] = (
            self.claims.select("ndc11")
            .unique()
            .sort("ndc11")
            .get_column("ndc11")
            .to_list()
        )
        n = len(unique_ndcs)

        # --- brand_family -----------------------------------------------
        # Group NDCs into brand families: roughly 1 brand per 5 NDCs
        # (e.g., a brand has multiple strengths / package sizes)
        ndcs_per_brand = 5
        brand_families = [
            f"Brand_{i // ndcs_per_brand}" for i in range(n)
        ]

        # --- manufacturer -----------------------------------------------
        n_mfrs = cfg.n_manufacturers  # 20
        mfr_indices = self.rng.integers(0, n_mfrs, size=n)
        manufacturers = [f"M{idx:02d}" for idx in mfr_indices]

        # --- gpi_class --------------------------------------------------
        gpi_indices = self.rng.integers(0, len(_GPI_CODES), size=n)
        gpi_classes = [_GPI_CODES[i] for i in gpi_indices]

        # --- specialty_flag ---------------------------------------------
        # Base probability from config (default 15%); injectable therapeutic
        # classes (antineoplastics, biologics, anticoagulants, insulin) are
        # always specialty, so effective rate will be slightly higher than the
        # config probability depending on how many NDCs fall into those classes.
        base_specialty = (
            self.rng.random(size=n) < cfg.specialty_flag_probability
        )
        # Force specialty for antineoplastics (0281), anticoagulants (0510),
        # insulin (0610), and biologics/immunosuppressants (2430)
        forced_specialty = np.array(
            [g[:4] in _INJECTABLE_GPI_PREFIXES for g in gpi_classes]
        )
        specialty_flags = (base_specialty | forced_specialty).tolist()

        # --- package_size -----------------------------------------------
        package_sizes: list[float] = []
        for g in gpi_classes:
            if g[:4] in _INJECTABLE_GPI_PREFIXES:
                sz = float(
                    self.rng.choice(_INJECTABLE_PACKAGE_SIZES)
                )
            else:
                sz = float(
                    self.rng.choice(_ORAL_PACKAGE_SIZES)
                )
            package_sizes.append(sz)

        # --- effective dates -------------------------------------------
        effective_date_start = date(2023, 1, 1)
        effective_date_end = date(2026, 12, 31)

        # --- launch_date -----------------------------------------------
        launch_span = (_LAUNCH_DATE_END - _LAUNCH_DATE_START).days
        launch_offsets = self.rng.integers(0, launch_span + 1, size=n)
        launch_dates = [
            _LAUNCH_DATE_START + timedelta(days=int(d)) for d in launch_offsets
        ]

        # --- Assemble DataFrame -----------------------------------------
        df = pl.DataFrame(
            {
                "ndc11": unique_ndcs,
                "brand_family": brand_families,
                "manufacturer": manufacturers,
                "gpi_class": gpi_classes,
                "specialty_flag": specialty_flags,
                "package_size": package_sizes,
                "effective_date_start": [effective_date_start] * n,
                "effective_date_end": [effective_date_end] * n,
                "launch_date": launch_dates,
            }
        ).with_columns(
            pl.col("effective_date_start").cast(pl.Date),
            pl.col("effective_date_end").cast(pl.Date),
            pl.col("launch_date").cast(pl.Date),
        )

        return df
