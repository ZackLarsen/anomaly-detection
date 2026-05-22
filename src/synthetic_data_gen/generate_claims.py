"""
Claims generator for the synthetic Rx rebate data generation system.

Produces realistic pharmacy claim transactions with proper distributions
for channels, days supply, plan costs, and drug costs.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from synthetic_data_gen.config import BaseConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DAYS_SUPPLY_VALUES = [30, 60, 84, 90]

# Plan paid Gamma distribution scale parameters by channel (retail < mail < specialty)
_CHANNEL_PLAN_PAID_SCALE = {
    "retail": 25.0,
    "mail": 60.0,
    "specialty": 800.0,
}

# Specialty drug multiplier for gross_drug_cost
_SPECIALTY_COST_MULTIPLIER = 8.0


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------


class ClaimsGenerator:
    """
    Generates synthetic pharmacy claim records.

    Produces a polars DataFrame with claim_id, member_id, group_id, ndc11,
    fill_date, days_supply, quantity, channel, plan_paid, gross_drug_cost,
    and claim_status columns.

    Args:
        config: BaseConfig instance controlling dataset size and distributions.
        seed: Integer seed for the numpy random number generator.
    """

    def __init__(self, config: BaseConfig, seed: int = 42) -> None:
        self.config = config
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pl.DataFrame:
        """
        Generate pharmacy claims according to config parameters.

        Returns:
            polars DataFrame with columns:
            claim_id, member_id, group_id, ndc11, fill_date, days_supply,
            quantity, channel, plan_paid, gross_drug_cost, claim_status.
            Sorted by fill_date ascending.
        """
        n = self.config.n_claims
        cfg = self.config

        # --- claim_id ---------------------------------------------------
        claim_ids = [f"C{i:09d}" for i in range(1, n + 1)]

        # --- member_id --------------------------------------------------
        member_ids = [
            f"M{mid:07d}"
            for mid in self.rng.integers(1, 100_001, size=n)
        ]

        # --- group_id ---------------------------------------------------
        n_groups = cfg.n_groups  # 50
        group_ids = [f"G{g:03d}" for g in self.rng.integers(0, n_groups, size=n)]

        # --- ndc11 ------------------------------------------------------
        # 300 NDCs in range [10000000000, 10000000300)
        n_ndcs = cfg.n_ndcs  # 300
        ndc_base = 10_000_000_000
        ndc_ints = self.rng.integers(0, n_ndcs, size=n)
        ndc11_list = [f"{ndc_base + i:011d}" for i in ndc_ints]

        # --- fill_date --------------------------------------------------
        start_date = date.fromisoformat(cfg.date_range.start)
        end_date = date.fromisoformat(cfg.date_range.end)
        date_span_days = (end_date - start_date).days
        day_offsets = self.rng.integers(0, date_span_days + 1, size=n)
        fill_dates = [start_date + timedelta(days=int(d)) for d in day_offsets]

        # --- channel ----------------------------------------------------
        ch_cfg = cfg.distributions.channel
        channel_probs = [ch_cfg.retail, ch_cfg.mail, ch_cfg.specialty]
        channel_choices_idx = self.rng.choice(3, size=n, p=channel_probs)
        channel_names = ["retail", "mail", "specialty"]
        channels = [channel_names[i] for i in channel_choices_idx]

        # --- days_supply ------------------------------------------------
        # Base weights from config
        ds_cfg = cfg.distributions.days_supply
        base_ds_probs = np.array([ds_cfg.d30, ds_cfg.d60, ds_cfg.d84, ds_cfg.d90])

        # Mail channel biased toward 90-day supply
        # Specialty channel biased toward 30-day supply
        days_supply_list: list[int] = []
        for ch in channels:
            if ch == "mail":
                # Shift weight toward 90-day
                probs = np.array([0.20, 0.05, 0.20, 0.55])
            elif ch == "specialty":
                # Specialty typically monthly infusions/injections
                probs = np.array([0.75, 0.10, 0.05, 0.10])
            else:
                probs = base_ds_probs
            ds = int(self.rng.choice(_DAYS_SUPPLY_VALUES, p=probs))
            days_supply_list.append(ds)

        # --- quantity ---------------------------------------------------
        # Gamma distribution (shape=2.0, scale=15.0)
        quantities = self.rng.gamma(shape=2.0, scale=15.0, size=n)
        quantities = np.clip(quantities, 1.0, None)

        # --- specialty flag per claim (based on NDC index) --------------
        # NDCs 0–44 are specialty (15% of 300 = 45 NDCs)
        n_specialty_ndcs = max(1, int(n_ndcs * cfg.specialty_flag_probability))
        specialty_mask = np.array([ndc_ints[i] < n_specialty_ndcs for i in range(n)])

        # --- plan_paid --------------------------------------------------
        plan_paid_arr = np.zeros(n, dtype=np.float64)
        for ch_name, scale in _CHANNEL_PLAN_PAID_SCALE.items():
            mask = np.array([c == ch_name for c in channels])
            count = int(mask.sum())
            if count > 0:
                vals = self.rng.gamma(shape=2.0, scale=scale, size=count)
                plan_paid_arr[mask] = vals

        # Specialty drugs get higher plan_paid
        plan_paid_arr[specialty_mask] *= _SPECIALTY_COST_MULTIPLIER

        plan_paid_arr = np.clip(plan_paid_arr, 0.01, None)

        # --- gross_drug_cost --------------------------------------------
        # plan_paid + random markup (1.0–1.5x, so gdc = plan_paid * markup)
        # markup is drawn from uniform(1.0, 1.5) — gdc >= plan_paid always
        markups = self.rng.uniform(1.0, 1.5, size=n)
        gross_drug_cost_arr = plan_paid_arr * markups

        # --- claim_status -----------------------------------------------
        # Weighted: 92% paid, 3% pending, 3% adjusted, 2% reversed
        # (ClaimStatusEnum values: paid, reversed, adjusted, pending)
        status_idx = self.rng.choice(4, size=n, p=[0.92, 0.02, 0.03, 0.03])
        status_names = ["paid", "reversed", "adjusted", "pending"]
        claim_statuses = [status_names[i] for i in status_idx]

        # --- Assemble DataFrame -----------------------------------------
        df = pl.DataFrame(
            {
                "claim_id": claim_ids,
                "member_id": member_ids,
                "group_id": group_ids,
                "ndc11": ndc11_list,
                "fill_date": fill_dates,
                "days_supply": days_supply_list,
                "quantity": quantities.tolist(),
                "channel": channels,
                "plan_paid": plan_paid_arr.tolist(),
                "gross_drug_cost": gross_drug_cost_arr.tolist(),
                "claim_status": claim_statuses,
            }
        ).with_columns(
            pl.col("fill_date").cast(pl.Date),
            pl.col("quantity").round(4),
            pl.col("plan_paid").round(2),
            pl.col("gross_drug_cost").round(2),
        )

        return df.sort("fill_date")
