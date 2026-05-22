"""
synthetic_data_gen - Synthetic pharmacy claims data generator for Rx rebate anomaly detection.

This package provides tools for generating realistic synthetic pharmacy claims data,
drug master records, formulary history, rebate contracts, rebate invoices, and
injected anomaly labels for use in building and evaluating rebate leakage detection models.
"""

__version__ = "0.1.0"

from synthetic_data_gen.config import BaseConfig, load_config, load_anomaly_scenarios
from synthetic_data_gen.generate_claims import ClaimsGenerator
from synthetic_data_gen.generate_contracts import ContractGenerator
from synthetic_data_gen.generate_drugs import DrugGenerator
from synthetic_data_gen.generate_formulary import FormularyGenerator
from synthetic_data_gen.generate_invoices import InvoiceGenerator
from synthetic_data_gen.inject_anomalies import (
    inject_dispute_spike,
    inject_guarantee_true_up_missing,
    inject_missing_rebate,
    inject_rebate_yield_collapse,
    inject_scenario,
    inject_specialty_channel_omission,
    inject_unit_conversion_error,
    inject_unmapped_ndc,
    make_empty_labels_df,
)

__all__ = [
    "__version__",
    # Config
    "BaseConfig",
    "load_config",
    "load_anomaly_scenarios",
    # Generators
    "ClaimsGenerator",
    "ContractGenerator",
    "DrugGenerator",
    "FormularyGenerator",
    "InvoiceGenerator",
    # Anomaly injection
    "inject_dispute_spike",
    "inject_guarantee_true_up_missing",
    "inject_missing_rebate",
    "inject_rebate_yield_collapse",
    "inject_scenario",
    "inject_specialty_channel_omission",
    "inject_unit_conversion_error",
    "inject_unmapped_ndc",
    "make_empty_labels_df",
]
