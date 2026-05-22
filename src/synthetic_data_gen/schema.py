"""
Pydantic V2 data models for the synthetic Rx rebate data generation system.

Each model corresponds to a core data entity in the pharmacy rebate pipeline:
- ClaimRecord: Individual pharmacy claim transactions
- DrugRecord: Drug master reference data
- FormularyRecord: Formulary placement and management restrictions
- ContractRecord: Manufacturer rebate contract terms
- InvoiceRecord: Quarterly rebate invoice reconciliation lines
- AnomalyLabel: Ground truth labels for injected anomaly scenarios
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ChannelEnum(str, Enum):
    """Dispensing channel for pharmacy claims."""

    RETAIL = "retail"
    MAIL = "mail"
    SPECIALTY = "specialty"


class ClaimStatusEnum(str, Enum):
    """Adjudication status of a pharmacy claim."""

    PAID = "paid"
    REVERSED = "reversed"
    ADJUSTED = "adjusted"
    PENDING = "pending"


class RebateBasisEnum(str, Enum):
    """Contract rebate calculation basis options aligned with industry-standard terms."""

    PER_30_DAY_SCRIPT = "PER_30_DAY_SCRIPT"
    PERCENT_GROSS_COST = "PERCENT_GROSS_COST"
    PER_UNIT = "PER_UNIT"
    PMPM_GUARANTEE = "PMPM_GUARANTEE"


class AnomalyTypeEnum(str, Enum):
    """Enumeration of the seven supported rebate leakage anomaly patterns."""

    MISSING_REBATE = "MISSING_REBATE"
    UNMAPPED_NDC = "UNMAPPED_NDC"
    REBATE_YIELD_COLLAPSE = "REBATE_YIELD_COLLAPSE"
    SPECIALTY_CHANNEL_OMISSION = "SPECIALTY_CHANNEL_OMISSION"
    UNIT_CONVERSION_ERROR = "UNIT_CONVERSION_ERROR"
    DISPUTE_SPIKE = "DISPUTE_SPIKE"
    GUARANTEE_TRUE_UP_MISSING = "GUARANTEE_TRUE_UP_MISSING"


class EntityTypeEnum(str, Enum):
    """Granularity of the affected entity in an anomaly label."""

    NDC_GROUP_QUARTER = "ndc_group_quarter"
    NDC_QUARTER = "ndc_quarter"
    GROUP_QUARTER = "group_quarter"
    CONTRACT = "contract"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class ClaimRecord(BaseModel):
    """
    Pharmacy claim transaction record.

    Represents a single adjudicated claim event as would appear in a PBM data feed.
    Financial amounts are in USD. NDC11 is the 11-digit National Drug Code.
    """

    claim_id: Annotated[str, Field(description="Unique claim identifier (e.g. C000123456)")]
    member_id: Annotated[str, Field(description="Surrogate member identifier — no real PHI")]
    group_id: Annotated[str, Field(description="Employer/client group identifier")]
    ndc11: Annotated[
        str,
        Field(
            description="11-digit National Drug Code",
            pattern=r"^\d{11}$",
        ),
    ]
    fill_date: Annotated[date, Field(description="Date the prescription was dispensed")]
    days_supply: Annotated[
        int,
        Field(
            gt=0,
            le=365,
            description="Number of days of medication supplied (common: 30, 84, 90)",
        ),
    ]
    quantity: Annotated[
        float,
        Field(gt=0.0, description="Dispensed quantity in metric units (tablets, mL, etc.)"),
    ]
    channel: Annotated[ChannelEnum, Field(description="Dispensing channel")]
    plan_paid: Annotated[
        float,
        Field(ge=0.0, description="Amount paid by the health plan in USD"),
    ]
    gross_drug_cost: Annotated[
        float,
        Field(ge=0.0, description="Total cost of the drug before member cost-share in USD"),
    ]
    claim_status: Annotated[ClaimStatusEnum, Field(description="Adjudication status")]

    @field_validator("ndc11")
    @classmethod
    def ndc11_must_be_digits(cls, v: str) -> str:
        """Ensure NDC11 contains exactly 11 numeric digits."""
        if not v.isdigit() or len(v) != 11:
            raise ValueError(f"ndc11 must be exactly 11 digits, got: {v!r}")
        return v

    @field_validator("gross_drug_cost")
    @classmethod
    def gross_cost_must_cover_plan_paid(cls, v: float) -> float:
        """Gross drug cost must be non-negative (plan_paid validation via model_validator)."""
        return v

    @model_validator(mode="after")
    def plan_paid_cannot_exceed_gross_cost(self) -> "ClaimRecord":
        """Plan paid amount should not exceed the gross drug cost."""
        if self.plan_paid > self.gross_drug_cost + 0.01:
            raise ValueError(
                f"plan_paid ({self.plan_paid}) exceeds gross_drug_cost ({self.gross_drug_cost})"
            )
        return self


class DrugRecord(BaseModel):
    """
    Drug master reference record.

    Contains product-level metadata that links NDC11 codes to brand families,
    manufacturers, therapeutic classes, and packaging details. Used to enrich
    claims and validate rebate contract applicability.
    """

    ndc11: Annotated[
        str,
        Field(description="11-digit National Drug Code", pattern=r"^\d{11}$"),
    ]
    brand_family: Annotated[
        str, Field(description="Commercial brand family name (e.g. 'HUMIRA')")
    ]
    manufacturer: Annotated[str, Field(description="Manufacturer name")]
    gpi_class: Annotated[
        str,
        Field(
            description="Generic Product Identifier (GPI) therapeutic class code (14-char)",
        ),
    ]
    specialty_flag: Annotated[
        bool, Field(description="True if this is a specialty drug product")
    ]
    package_size: Annotated[
        float,
        Field(gt=0.0, description="Standard package size in dispensing units"),
    ]
    effective_date_start: Annotated[
        date, Field(description="Date this NDC record became effective")
    ]
    effective_date_end: Annotated[
        date | None,
        Field(default=None, description="Date this NDC record was retired; None if still active"),
    ]
    launch_date: Annotated[
        date, Field(description="Commercial launch date of the product")
    ]

    @field_validator("ndc11")
    @classmethod
    def ndc11_must_be_digits(cls, v: str) -> str:
        """Ensure NDC11 contains exactly 11 numeric digits."""
        if not v.isdigit() or len(v) != 11:
            raise ValueError(f"ndc11 must be exactly 11 digits, got: {v!r}")
        return v

    @model_validator(mode="after")
    def end_date_after_start_date(self) -> "DrugRecord":
        """Effective end date must be after effective start date if set."""
        if self.effective_date_end is not None:
            if self.effective_date_end <= self.effective_date_start:
                raise ValueError(
                    f"effective_date_end ({self.effective_date_end}) must be after "
                    f"effective_date_start ({self.effective_date_start})"
                )
        return self


class FormularyRecord(BaseModel):
    """
    Formulary placement and utilization management record.

    Captures the tier placement and management restriction flags (PA, ST, QL) for
    a given NDC or brand family on a client formulary, along with the effective dates
    during which those terms apply.
    """

    client_id: Annotated[str, Field(description="Client/employer group identifier")]
    ndc11: Annotated[
        str,
        Field(description="11-digit National Drug Code", pattern=r"^\d{11}$"),
    ]
    brand_family: Annotated[str, Field(description="Commercial brand family name")]
    tier: Annotated[
        int,
        Field(ge=1, le=6, description="Formulary tier (1=preferred generic, 6=specialty)"),
    ]
    preferred_flag: Annotated[
        bool, Field(description="True if product is preferred within its tier")
    ]
    pa_required: Annotated[
        bool, Field(description="Prior Authorization required flag")
    ]
    st_required: Annotated[
        bool, Field(description="Step Therapy required flag")
    ]
    ql_required: Annotated[
        bool, Field(description="Quantity Limit required flag")
    ]
    effective_date_start: Annotated[
        date, Field(description="Date this formulary placement became effective")
    ]
    effective_date_end: Annotated[
        date | None,
        Field(
            default=None,
            description="Date this formulary placement ended; None if still active",
        ),
    ]

    @field_validator("ndc11")
    @classmethod
    def ndc11_must_be_digits(cls, v: str) -> str:
        """Ensure NDC11 contains exactly 11 numeric digits."""
        if not v.isdigit() or len(v) != 11:
            raise ValueError(f"ndc11 must be exactly 11 digits, got: {v!r}")
        return v

    @model_validator(mode="after")
    def end_date_after_start_date(self) -> "FormularyRecord":
        """Effective end date must be after effective start date if set."""
        if self.effective_date_end is not None:
            if self.effective_date_end <= self.effective_date_start:
                raise ValueError(
                    f"effective_date_end ({self.effective_date_end}) must be after "
                    f"effective_date_start ({self.effective_date_start})"
                )
        return self


class ContractRecord(BaseModel):
    """
    Manufacturer rebate contract record.

    Defines the economic terms under which a manufacturer pays rebates to the PBM
    or health plan for a specific brand family and client, including rate structures,
    minimum guarantees, and exclusion lists.
    """

    manufacturer: Annotated[str, Field(description="Manufacturer name")]
    brand_family: Annotated[str, Field(description="Commercial brand family covered by contract")]
    client_id: Annotated[
        str,
        Field(description="Client identifier; empty string means national/all-client contract"),
    ]
    effective_date_start: Annotated[
        date, Field(description="Contract start date")
    ]
    effective_date_end: Annotated[
        date | None,
        Field(default=None, description="Contract end date; None if open-ended"),
    ]
    rebate_basis: Annotated[RebateBasisEnum, Field(description="Rebate calculation methodology")]
    rebate_rate: Annotated[
        float,
        Field(
            ge=0.0,
            description=(
                "Rate used for rebate calculation. Interpretation depends on rebate_basis: "
                "USD per 30-day script, decimal fraction of gross cost, USD per unit, "
                "or USD PMPM guarantee."
            ),
        ),
    ]
    minimum_guarantee: Annotated[
        float | None,
        Field(
            default=None,
            ge=0.0,
            description="Optional minimum quarterly rebate guarantee in USD; None if not applicable",
        ),
    ]
    channel_exclusions: Annotated[
        list[ChannelEnum],
        Field(
            default_factory=list,
            description="Channels excluded from rebate eligibility (e.g. specialty excluded)",
        ),
    ]
    lob_exclusions: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="Lines of business excluded from rebate (e.g. ['Medicaid', 'Medicare'])",
        ),
    ]

    @model_validator(mode="after")
    def end_date_after_start_date(self) -> "ContractRecord":
        """Effective end date must be after effective start date if set."""
        if self.effective_date_end is not None:
            if self.effective_date_end <= self.effective_date_start:
                raise ValueError(
                    f"effective_date_end ({self.effective_date_end}) must be after "
                    f"effective_date_start ({self.effective_date_start})"
                )
        return self

    @model_validator(mode="after")
    def pmpm_requires_minimum_guarantee(self) -> "ContractRecord":
        """PMPM_GUARANTEE rebate basis should have a minimum_guarantee set."""
        if self.rebate_basis == RebateBasisEnum.PMPM_GUARANTEE and self.minimum_guarantee is None:
            raise ValueError(
                "PMPM_GUARANTEE rebate_basis requires minimum_guarantee to be set"
            )
        return self


class InvoiceRecord(BaseModel):
    """
    Quarterly rebate invoice reconciliation record.

    Represents a single line in a rebate invoice, aggregated at the
    manufacturer × NDC × client × quarter grain. Expected vs. actual rebate
    discrepancies (gaps) are the primary signal for anomaly detection.
    All amounts are in USD.
    """

    invoice_quarter: Annotated[
        str,
        Field(
            description="Invoice quarter in YYYY-QN format (e.g. '2024-Q1')",
            pattern=r"^\d{4}-Q[1-4]$",
        ),
    ]
    manufacturer: Annotated[str, Field(description="Manufacturer name")]
    ndc11: Annotated[
        str,
        Field(description="11-digit National Drug Code", pattern=r"^\d{11}$"),
    ]
    client_id: Annotated[str, Field(description="Client/employer group identifier")]
    invoiced_utilization: Annotated[
        float,
        Field(ge=0.0, description="Utilization submitted on the invoice (scripts or units)"),
    ]
    expected_rebate: Annotated[
        float,
        Field(ge=0.0, description="Calculated expected rebate based on contract terms in USD"),
    ]
    actual_rebate: Annotated[
        float,
        Field(ge=0.0, description="Rebate amount actually invoiced by the manufacturer in USD"),
    ]
    disputed_rebate: Annotated[
        float,
        Field(ge=0.0, description="Amount of the invoice currently under dispute in USD"),
    ]
    paid_rebate: Annotated[
        float,
        Field(ge=0.0, description="Amount actually received/paid in USD"),
    ]

    @field_validator("ndc11")
    @classmethod
    def ndc11_must_be_digits(cls, v: str) -> str:
        """Ensure NDC11 contains exactly 11 numeric digits."""
        if not v.isdigit() or len(v) != 11:
            raise ValueError(f"ndc11 must be exactly 11 digits, got: {v!r}")
        return v

    @model_validator(mode="after")
    def paid_cannot_exceed_actual(self) -> "InvoiceRecord":
        """Paid rebate should not exceed actual rebate."""
        if self.paid_rebate > self.actual_rebate + 0.01:
            raise ValueError(
                f"paid_rebate ({self.paid_rebate}) cannot exceed actual_rebate ({self.actual_rebate})"
            )
        return self

    @model_validator(mode="after")
    def disputed_cannot_exceed_actual(self) -> "InvoiceRecord":
        """Disputed rebate should not exceed actual rebate."""
        if self.disputed_rebate > self.actual_rebate + 0.01:
            raise ValueError(
                f"disputed_rebate ({self.disputed_rebate}) cannot exceed "
                f"actual_rebate ({self.actual_rebate})"
            )
        return self


class AnomalyLabel(BaseModel):
    """
    Ground truth anomaly label for injected leakage scenarios.

    Each label identifies a specific entity (NDC + client + quarter combination)
    where a known anomaly was injected, the type of anomaly, whether the leakage
    is theoretically recoverable, the estimated dollar impact, and a plain-language
    root cause description for analyst review.
    """

    entity_type: Annotated[
        EntityTypeEnum,
        Field(description="Granularity of the labeled entity"),
    ]
    ndc11: Annotated[
        str | None,
        Field(
            default=None,
            description="11-digit NDC of the affected product; None for group-only anomalies",
        ),
    ]
    client_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Affected client identifier; None for NDC-only anomalies",
        ),
    ]
    quarter: Annotated[
        str,
        Field(
            description="Affected quarter in YYYY-QN format",
            pattern=r"^\d{4}-Q[1-4]$",
        ),
    ]
    anomaly_type: Annotated[AnomalyTypeEnum, Field(description="Category of the injected anomaly")]
    recoverable: Annotated[
        bool,
        Field(
            description=(
                "True if the leakage is theoretically recoverable through invoicing or dispute"
            ),
        ),
    ]
    estimated_impact: Annotated[
        float,
        Field(ge=0.0, description="Estimated recoverable dollar impact of this anomaly in USD"),
    ]
    root_cause: Annotated[
        str,
        Field(
            description="Plain-language description of the root cause for analyst audit trail"
        ),
    ]

    @field_validator("ndc11")
    @classmethod
    def ndc11_must_be_digits_if_set(cls, v: str | None) -> str | None:
        """Ensure NDC11 contains exactly 11 numeric digits when provided."""
        if v is not None:
            if not v.isdigit() or len(v) != 11:
                raise ValueError(f"ndc11 must be exactly 11 digits, got: {v!r}")
        return v
