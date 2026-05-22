"""
Formulary generator for the synthetic Rx rebate data generation system.

Produces formulary placement records for (client, NDC) combinations observed
in claims, covering ~70% of all pairs to simulate realistic formulary exceptions.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from synthetic_data_gen.config import BaseConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIER_VALUES = [1, 2, 3, 4, 5, 6]
_TIER_PROBS = [0.10, 0.20, 0.35, 0.20, 0.10, 0.05]  # tier 3 is most common

_FORMULARY_COVERAGE_FRACTION = 0.70  # Cover 70% of (client, NDC) pairs

_EFFECTIVE_DATE_START = date(2024, 1, 1)
_EFFECTIVE_DATE_END = date(2025, 12, 31)


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------


class FormularyGenerator:
    """
    Generates formulary placement records for client × NDC combinations.

    Covers 70% of the (client, NDC) combinations observed in claims.
    Tier assignment, preferred flag, and management restriction flags
    (PA, ST, QL) are generated with realistic distributions.

    Args:
        config: BaseConfig instance.
        claims: polars DataFrame produced by ClaimsGenerator.
        drugs: polars DataFrame produced by DrugGenerator.
        seed: Integer seed for the numpy random number generator.
    """

    def __init__(
        self,
        config: BaseConfig,
        claims: pl.DataFrame,
        drugs: pl.DataFrame,
        seed: int = 42,
    ) -> None:
        self.config = config
        self.claims = claims
        self.drugs = drugs
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pl.DataFrame:
        """
        Generate formulary records for ~70% of (client, NDC) pairs in claims.

        Returns:
            polars DataFrame with columns:
            client_id, ndc11, brand_family, tier, preferred_flag,
            pa_required, st_required, ql_required,
            effective_date_start, effective_date_end.
        """
        # Get unique (group_id, ndc11) combos from claims
        pairs = (
            self.claims.select(["group_id", "ndc11"])
            .unique()
            .sort(["group_id", "ndc11"])
        )
        n_total = len(pairs)

        # Sample 70% of pairs
        n_covered = int(n_total * _FORMULARY_COVERAGE_FRACTION)
        selected_idx = self.rng.choice(n_total, size=n_covered, replace=False)
        selected_idx.sort()

        pairs_covered = pairs[selected_idx]
        n = len(pairs_covered)

        # Build ndc11 -> brand_family lookup from drugs
        ndc_to_brand: dict[str, str] = dict(
            zip(
                self.drugs.get_column("ndc11").to_list(),
                self.drugs.get_column("brand_family").to_list(),
            )
        )

        client_ids = pairs_covered.get_column("group_id").to_list()
        ndc11s = pairs_covered.get_column("ndc11").to_list()
        brand_families = [ndc_to_brand.get(ndc, "Unknown") for ndc in ndc11s]

        # --- tier -------------------------------------------------------
        tier_arr = self.rng.choice(_TIER_VALUES, size=n, p=_TIER_PROBS)
        tiers = tier_arr.tolist()

        # --- preferred_flag ---------------------------------------------
        # Preferred if tier <= 2
        preferred_flags = [bool(t <= 2) for t in tiers]

        # --- pa_required, st_required, ql_required ----------------------
        # 10% probability each; higher tiers (4-6) have higher chance
        pa_required: list[bool] = []
        st_required: list[bool] = []
        ql_required: list[bool] = []

        for t in tiers:
            # Higher tier = more management restrictions
            base_prob = 0.10
            if t >= 4:
                tier_boost = 0.15
            elif t == 3:
                tier_boost = 0.05
            else:
                tier_boost = 0.0

            pa_prob = min(base_prob + tier_boost, 0.40)
            pa_required.append(bool(self.rng.random() < pa_prob))
            st_required.append(bool(self.rng.random() < pa_prob))
            ql_required.append(bool(self.rng.random() < pa_prob))

        # --- Assemble DataFrame -----------------------------------------
        df = pl.DataFrame(
            {
                "client_id": client_ids,
                "ndc11": ndc11s,
                "brand_family": brand_families,
                "tier": tiers,
                "preferred_flag": preferred_flags,
                "pa_required": pa_required,
                "st_required": st_required,
                "ql_required": ql_required,
                "effective_date_start": [_EFFECTIVE_DATE_START] * n,
                "effective_date_end": [_EFFECTIVE_DATE_END] * n,
            }
        ).with_columns(
            pl.col("effective_date_start").cast(pl.Date),
            pl.col("effective_date_end").cast(pl.Date),
        )

        return df
