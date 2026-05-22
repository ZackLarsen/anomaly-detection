"""
Shared pytest fixtures for the synthetic data generation test suite.

Provides small and full configuration fixtures, plus a helper fixture
that generates the complete pipeline tables (claims, drugs, formulary,
contracts, invoices) using the small config for fast unit tests.
"""

from __future__ import annotations

import pytest

from synthetic_data_gen.config import BaseConfig, DateRangeConfig


# ---------------------------------------------------------------------------
# Configuration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def config_small() -> BaseConfig:
    """
    Small configuration for fast unit tests.

    Uses 1000 claims, 50 NDCs, 50 groups (minimum required by ContractGenerator
    which samples up to 30 groups per brand), and 5 manufacturers.
    Date range is a single calendar year (2024).
    """
    cfg = BaseConfig(
        n_claims=1000,
        n_ndcs=50,
        n_groups=50,
        n_manufacturers=5,
        random_seed=42,
    )
    cfg.date_range = DateRangeConfig(start="2024-01-01", end="2024-12-31")
    return cfg


@pytest.fixture(scope="session")
def config_full() -> BaseConfig:
    """
    Full configuration matching the production baseline (500K claims).

    Used for integration tests. Marked session-scoped so the large dataset
    is generated once and reused across tests.
    """
    from synthetic_data_gen.config import load_config
    import os

    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "configs", "base.yaml"
    )
    return load_config(yaml_path)


# ---------------------------------------------------------------------------
# Generated data fixtures (small)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def small_claims(config_small):
    """Claims DataFrame generated from config_small."""
    from synthetic_data_gen.generate_claims import ClaimsGenerator

    return ClaimsGenerator(config_small, seed=42).generate()


@pytest.fixture(scope="session")
def small_drugs(config_small, small_claims):
    """Drug master DataFrame generated from config_small claims."""
    from synthetic_data_gen.generate_drugs import DrugGenerator

    return DrugGenerator(config_small, small_claims, seed=42).generate()


@pytest.fixture(scope="session")
def small_formulary(config_small, small_claims, small_drugs):
    """Formulary DataFrame generated from config_small."""
    from synthetic_data_gen.generate_formulary import FormularyGenerator

    return FormularyGenerator(config_small, small_claims, small_drugs, seed=42).generate()


@pytest.fixture(scope="session")
def small_contracts(config_small, small_drugs):
    """Contracts DataFrame generated from config_small."""
    from synthetic_data_gen.generate_contracts import ContractGenerator

    return ContractGenerator(config_small, small_drugs, seed=42).generate()


@pytest.fixture(scope="session")
def small_invoices(config_small, small_claims, small_contracts, small_drugs, small_formulary):
    """Invoice DataFrame generated from config_small."""
    from synthetic_data_gen.generate_invoices import InvoiceGenerator

    return InvoiceGenerator(
        config_small, small_claims, small_contracts, small_drugs, small_formulary, seed=42
    ).generate()


@pytest.fixture(scope="session")
def full_dataset_small(small_claims, small_drugs, small_formulary, small_contracts, small_invoices):
    """Convenience fixture returning the full small-dataset tuple."""
    return small_claims, small_drugs, small_formulary, small_contracts, small_invoices
