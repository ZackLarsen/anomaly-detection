"""
Configuration loading for the synthetic Rx rebate data generation system.

This module provides dataclass-based configuration models and YAML loading
functions for both the baseline generation parameters and the anomaly injection
scenario definitions.

Usage:
    >>> from synthetic_data_gen.config import load_config, load_anomaly_scenarios
    >>> cfg = load_config("configs/base.yaml")
    >>> scenarios = load_anomaly_scenarios("configs/anomaly_scenarios.yaml")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _load_yaml(yaml_path: str) -> dict[str, Any]:
    """
    Load a YAML file and return its contents as a dictionary.

    Args:
        yaml_path: Path to the YAML file. Relative paths are resolved from the
                   current working directory.

    Returns:
        Parsed YAML contents as a nested dictionary.

    Raises:
        FileNotFoundError: If the YAML file does not exist at the given path.
        yaml.YAMLError: If the file contains invalid YAML syntax.
    """
    import yaml  # lazy import so the module loads even without pyyaml on PATH

    abs_path = os.path.abspath(yaml_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Config file not found: {abs_path}")

    with open(abs_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------


@dataclass
class DateRangeConfig:
    """Start and end dates for the synthetic data generation window."""

    start: str = "2024-01-01"
    end: str = "2025-12-31"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DateRangeConfig":
        """Construct from a raw dictionary (typically from YAML)."""
        return cls(
            start=str(data.get("start", "2024-01-01")),
            end=str(data.get("end", "2025-12-31")),
        )


# ---------------------------------------------------------------------------
# Distribution configs
# ---------------------------------------------------------------------------


@dataclass
class ChannelDistributionConfig:
    """Probability weights for each dispensing channel."""

    retail: float = 0.70
    mail: float = 0.20
    specialty: float = 0.10

    def __post_init__(self) -> None:
        total = self.retail + self.mail + self.specialty
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Channel distribution probabilities must sum to 1.0, got {total:.4f}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelDistributionConfig":
        """Construct from a raw dictionary (typically from YAML)."""
        return cls(
            retail=float(data.get("retail", 0.70)),
            mail=float(data.get("mail", 0.20)),
            specialty=float(data.get("specialty", 0.10)),
        )


@dataclass
class DaysSupplyDistributionConfig:
    """Probability weights for common days-supply values."""

    d30: float = 0.65
    d60: float = 0.05
    d84: float = 0.10
    d90: float = 0.20

    def __post_init__(self) -> None:
        total = self.d30 + self.d60 + self.d84 + self.d90
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Days-supply distribution probabilities must sum to 1.0, got {total:.4f}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DaysSupplyDistributionConfig":
        """Construct from a raw dictionary mapping int keys to probabilities."""
        return cls(
            d30=float(data.get(30, data.get("30", 0.65))),
            d60=float(data.get(60, data.get("60", 0.05))),
            d84=float(data.get(84, data.get("84", 0.10))),
            d90=float(data.get(90, data.get("90", 0.20))),
        )


@dataclass
class DistributionsConfig:
    """Bundled distribution configurations for all categorical variables."""

    channel: ChannelDistributionConfig = field(default_factory=ChannelDistributionConfig)
    days_supply: DaysSupplyDistributionConfig = field(
        default_factory=DaysSupplyDistributionConfig
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DistributionsConfig":
        """Construct from a raw dictionary (typically from YAML)."""
        return cls(
            channel=ChannelDistributionConfig.from_dict(data.get("channel", {})),
            days_supply=DaysSupplyDistributionConfig.from_dict(data.get("days_supply", {})),
        )


# ---------------------------------------------------------------------------
# Base generation config
# ---------------------------------------------------------------------------


@dataclass
class BaseConfig:
    """
    Top-level configuration for baseline synthetic data generation.

    All volume parameters (n_claims, n_ndcs, n_groups, n_manufacturers) control
    the size of the generated dataset. The distributions sub-config governs the
    mix of categorical variables. rebate_noise_range introduces realistic noise
    into the expected-vs-actual rebate relationship.
    """

    n_claims: int = 500_000
    n_ndcs: int = 300
    n_groups: int = 50
    n_manufacturers: int = 20
    date_range: DateRangeConfig = field(default_factory=DateRangeConfig)
    distributions: DistributionsConfig = field(default_factory=DistributionsConfig)
    specialty_flag_probability: float = 0.15
    rebate_noise_range: tuple[float, float] = (0.95, 1.05)
    random_seed: int = 42

    def __post_init__(self) -> None:
        if not (0.0 <= self.specialty_flag_probability <= 1.0):
            raise ValueError(
                f"specialty_flag_probability must be in [0, 1], "
                f"got {self.specialty_flag_probability}"
            )
        lo, hi = self.rebate_noise_range
        if lo > hi:
            raise ValueError(
                f"rebate_noise_range lower bound ({lo}) must be <= upper bound ({hi})"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseConfig":
        """Construct from a raw dictionary (typically from YAML)."""
        noise_raw = data.get("rebate_noise_range", [0.95, 1.05])
        return cls(
            n_claims=int(data.get("n_claims", 500_000)),
            n_ndcs=int(data.get("n_ndcs", 300)),
            n_groups=int(data.get("n_groups", 50)),
            n_manufacturers=int(data.get("n_manufacturers", 20)),
            date_range=DateRangeConfig.from_dict(data.get("date_range", {})),
            distributions=DistributionsConfig.from_dict(data.get("distributions", {})),
            specialty_flag_probability=float(data.get("specialty_flag_probability", 0.15)),
            rebate_noise_range=(float(noise_raw[0]), float(noise_raw[1])),
            random_seed=int(data.get("random_seed", 42)),
        )


# ---------------------------------------------------------------------------
# Anomaly scenario config
# ---------------------------------------------------------------------------


@dataclass
class AnomalyScenarioConfig:
    """
    Configuration for a single anomaly injection scenario.

    Each scenario has a type identifier, a count (how many independent instances
    to inject), and a free-form parameters dictionary that carries scenario-specific
    settings (e.g. reduction_factor for yield collapse, affected_quarter for
    targeted injection).
    """

    scenario_type: str
    count: int = 1
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(
                f"Anomaly scenario count must be >= 1, got {self.count} "
                f"for scenario '{self.scenario_type}'"
            )

    @classmethod
    def from_dict(cls, scenario_type: str, data: dict[str, Any]) -> "AnomalyScenarioConfig":
        """Construct from a scenario-type key and its configuration dictionary."""
        params = {k: v for k, v in data.items() if k != "count"}
        return cls(
            scenario_type=scenario_type,
            count=int(data.get("count", 1)),
            parameters=params,
        )


# ---------------------------------------------------------------------------
# Public loading functions
# ---------------------------------------------------------------------------


def load_config(yaml_path: str) -> BaseConfig:
    """
    Load baseline generation configuration from a YAML file.

    Args:
        yaml_path: Path to the base configuration YAML (e.g. 'configs/base.yaml').
                   Relative paths are resolved from the current working directory.

    Returns:
        A fully populated BaseConfig instance with validated field values.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If any configuration value fails validation.

    Example:
        >>> cfg = load_config("configs/base.yaml")
        >>> print(cfg.n_claims)
        500000
    """
    raw = _load_yaml(yaml_path)
    return BaseConfig.from_dict(raw)


def load_anomaly_scenarios(yaml_path: str) -> list[AnomalyScenarioConfig]:
    """
    Load anomaly injection scenario configurations from a YAML file.

    The YAML file should be a mapping of scenario type names to their configuration
    dictionaries. For example::

        missing_rebate:
          count: 5
          reduction_factor: 1.0

    Args:
        yaml_path: Path to the anomaly scenarios YAML (e.g. 'configs/anomaly_scenarios.yaml').
                   Relative paths are resolved from the current working directory.

    Returns:
        List of AnomalyScenarioConfig instances, one per scenario type defined in the file.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If any scenario count is less than 1.

    Example:
        >>> scenarios = load_anomaly_scenarios("configs/anomaly_scenarios.yaml")
        >>> for s in scenarios:
        ...     print(s.scenario_type, s.count)
    """
    raw = _load_yaml(yaml_path)
    return [
        AnomalyScenarioConfig.from_dict(scenario_type=key, data=val)
        for key, val in raw.items()
        if isinstance(val, dict)
    ]
