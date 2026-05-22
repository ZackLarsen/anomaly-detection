"""
Invoice generator for the synthetic Rx rebate data generation system.

Aggregates claims to the (NDC, client, quarter) grain and calculates
expected rebates by applying contract terms. Adds realistic noise to
produce actual_rebate values.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from synthetic_data_gen.config import BaseConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of days in a 30-day period (for PER_30_DAY_SCRIPT calculation)
_DAYS_PER_SCRIPT = 30.0


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------


class InvoiceGenerator:
    """
    Generates quarterly rebate invoice records.

    Aggregates claims to the (manufacturer, NDC, client, quarter) grain,
    applies contract rebate rules, and adds realistic noise between expected
    and actual rebate amounts.

    Args:
        config: BaseConfig instance.
        claims: polars DataFrame produced by ClaimsGenerator.
        contracts: polars DataFrame produced by ContractGenerator.
        drugs: polars DataFrame produced by DrugGenerator.
        formulary: polars DataFrame produced by FormularyGenerator.
        seed: Integer seed for the numpy random number generator.
    """

    def __init__(
        self,
        config: BaseConfig,
        claims: pl.DataFrame,
        contracts: pl.DataFrame,
        drugs: pl.DataFrame,
        formulary: pl.DataFrame,
        seed: int = 42,
    ) -> None:
        self.config = config
        self.claims = claims
        self.contracts = contracts
        self.drugs = drugs
        self.formulary = formulary
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pl.DataFrame:
        """
        Generate quarterly rebate invoice records.

        Returns:
            polars DataFrame with columns:
            invoice_quarter, manufacturer, ndc11, client_id,
            invoiced_utilization, expected_rebate, actual_rebate,
            disputed_rebate, paid_rebate.
        """
        # Step 1: Add quarter column to claims
        claims_with_quarter = self.claims.with_columns(
            _quarter_expr().alias("invoice_quarter")
        )

        # Step 2: Enrich claims with manufacturer and brand_family from drugs
        drug_lookup = self.drugs.select(["ndc11", "brand_family", "manufacturer"])
        claims_enriched = claims_with_quarter.join(
            drug_lookup, on="ndc11", how="left"
        )

        # Step 3: Aggregate to (manufacturer, ndc11, group_id, invoice_quarter)
        agg = (
            claims_enriched.group_by(
                ["manufacturer", "ndc11", "brand_family", "group_id", "invoice_quarter"]
            )
            .agg(
                [
                    pl.col("quantity").sum().alias("invoiced_utilization"),
                    pl.col("days_supply").sum().alias("total_days_supply"),
                    pl.col("gross_drug_cost").sum().alias("total_gross_cost"),
                    pl.col("channel")
                    .value_counts()
                    .alias("channel_counts"),  # for channel-level exclusions
                ]
            )
            .rename({"group_id": "client_id"})
        )

        # Step 4: Build contract lookup keyed by (manufacturer, brand_family, client_id)
        contracts_lookup = self.contracts.select(
            [
                "manufacturer",
                "brand_family",
                "client_id",
                "rebate_basis",
                "rebate_rate",
                "minimum_guarantee",
                "channel_exclusions",
                "lob_exclusions",
            ]
        )

        # Step 5: Join aggregated claims to contracts
        # Deduplicate contracts per (manufacturer, brand_family, client_id):
        # Keep only the first contract if multiple exist (simplification for invoice calc)
        contracts_dedup = contracts_lookup.unique(
            subset=["manufacturer", "brand_family", "client_id"], keep="first"
        )

        joined = agg.join(
            contracts_dedup,
            on=["manufacturer", "brand_family", "client_id"],
            how="left",
        )

        # Step 6: Compute expected_rebate row by row using the contract terms
        expected_rebates: list[float] = []

        rebate_basis_col = joined.get_column("rebate_basis").to_list()
        rebate_rate_col = joined.get_column("rebate_rate").to_list()
        min_guarantee_col = joined.get_column("minimum_guarantee").to_list()
        utilization_col = joined.get_column("invoiced_utilization").to_list()
        days_supply_col = joined.get_column("total_days_supply").to_list()
        gross_cost_col = joined.get_column("total_gross_cost").to_list()

        for i in range(len(joined)):
            basis = rebate_basis_col[i]
            rate = rebate_rate_col[i] if rebate_rate_col[i] is not None else 0.0
            min_g = min_guarantee_col[i]

            expected = self._calculate_expected_rebate(
                rebate_basis=basis,
                rebate_rate=rate,
                minimum_guarantee=min_g,
                total_quantity=utilization_col[i],
                total_days_supply=days_supply_col[i],
                total_gross_cost=gross_cost_col[i],
            )
            expected_rebates.append(expected)

        # Step 7: Add noise to get actual_rebate
        noise_lo, noise_hi = self.config.rebate_noise_range
        n_rows = len(joined)
        noise = self.rng.uniform(noise_lo, noise_hi, size=n_rows)
        actual_rebates = [
            round(max(0.0, er * noise[i]), 2)
            for i, er in enumerate(expected_rebates)
        ]
        expected_rebates_rounded = [round(er, 2) for er in expected_rebates]

        # Step 8: disputed_rebate = 0.0, paid_rebate = actual_rebate for baseline
        disputed_rebates = [0.0] * n_rows
        paid_rebates = actual_rebates[:]

        # Step 9: Assemble final DataFrame
        result = joined.select(
            [
                "invoice_quarter",
                "manufacturer",
                "ndc11",
                "client_id",
                "invoiced_utilization",
            ]
        ).with_columns(
            [
                pl.Series("expected_rebate", expected_rebates_rounded),
                pl.Series("actual_rebate", actual_rebates),
                pl.Series("disputed_rebate", disputed_rebates),
                pl.Series("paid_rebate", paid_rebates),
            ]
        )

        # Round invoiced_utilization
        result = result.with_columns(
            pl.col("invoiced_utilization").round(4)
        )

        return result.sort(["invoice_quarter", "manufacturer", "ndc11", "client_id"])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def calculate_expected_rebate(self, row: dict) -> float:
        """
        Apply contract rules to calculate expected rebate for a single row.

        Args:
            row: Dictionary with keys: rebate_basis, rebate_rate,
                 minimum_guarantee, invoiced_utilization, total_days_supply,
                 total_gross_cost.

        Returns:
            Expected rebate in USD.
        """
        return self._calculate_expected_rebate(
            rebate_basis=row.get("rebate_basis"),
            rebate_rate=row.get("rebate_rate", 0.0),
            minimum_guarantee=row.get("minimum_guarantee"),
            total_quantity=row.get("invoiced_utilization", 0.0),
            total_days_supply=row.get("total_days_supply", 0.0),
            total_gross_cost=row.get("total_gross_cost", 0.0),
        )

    @staticmethod
    def _calculate_expected_rebate(
        rebate_basis: str | None,
        rebate_rate: float,
        minimum_guarantee: float | None,
        total_quantity: float,
        total_days_supply: float,
        total_gross_cost: float,
    ) -> float:
        """
        Calculate expected rebate based on contract rebate_basis.

        Logic:
            PER_30_DAY_SCRIPT  : rebate_rate × (total_days_supply / 30)
            PERCENT_GROSS_COST : rebate_rate × total_gross_cost
            PER_UNIT           : rebate_rate × total_quantity
            PMPM_GUARANTEE     : minimum_guarantee / 12 (monthly portion)
            None (no contract) : 0.0

        Args:
            rebate_basis: Rebate calculation method string or None.
            rebate_rate: Numeric rate for the rebate calculation.
            minimum_guarantee: Optional PMPM guarantee amount in USD.
            total_quantity: Sum of quantity for the aggregation grain.
            total_days_supply: Sum of days_supply for the aggregation grain.
            total_gross_cost: Sum of gross_drug_cost for the aggregation grain.

        Returns:
            Expected rebate amount in USD (non-negative).
        """
        if rebate_basis is None or rebate_rate is None:
            return 0.0

        if rebate_basis == "PER_30_DAY_SCRIPT":
            return max(0.0, rebate_rate * (total_days_supply / _DAYS_PER_SCRIPT))

        elif rebate_basis == "PERCENT_GROSS_COST":
            return max(0.0, rebate_rate * total_gross_cost)

        elif rebate_basis == "PER_UNIT":
            return max(0.0, rebate_rate * total_quantity)

        elif rebate_basis == "PMPM_GUARANTEE":
            # Monthly portion of the quarterly guarantee
            if minimum_guarantee is not None:
                return max(0.0, minimum_guarantee / 12.0)
            return 0.0

        return 0.0


# ---------------------------------------------------------------------------
# Helper expression
# ---------------------------------------------------------------------------


def _quarter_expr() -> pl.Expr:
    """
    Build a polars expression to convert a Date column named 'fill_date'
    into a quarter string like '2024-Q1'.
    """
    # Extract year and month, then compute quarter digit
    year_expr = pl.col("fill_date").dt.year().cast(pl.Utf8)
    month_expr = pl.col("fill_date").dt.month()
    # quarter: (month - 1) // 3 + 1 gives 1..4
    quarter_digit = ((month_expr - 1) // 3 + 1).cast(pl.Utf8)
    return pl.concat_str([year_expr, pl.lit("-Q"), quarter_digit])
