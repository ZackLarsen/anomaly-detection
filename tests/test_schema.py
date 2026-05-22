"""
Tests for Pydantic schema models (schema.py).

Verifies that valid records are accepted, invalid records raise
ValidationError with descriptive messages, and all enum values
are correctly enumerated.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from synthetic_data_gen.schema import (
    AnomalyLabel,
    AnomalyTypeEnum,
    ClaimRecord,
    ContractRecord,
    DrugRecord,
    EntityTypeEnum,
    FormularyRecord,
    InvoiceRecord,
    RebateBasisEnum,
)


# ---------------------------------------------------------------------------
# ClaimRecord
# ---------------------------------------------------------------------------


def test_claim_record_valid():
    """A correctly formed ClaimRecord should instantiate without error."""
    record = ClaimRecord(
        claim_id="C000000001",
        member_id="M0000001",
        group_id="G001",
        ndc11="12345678901",
        fill_date=date(2024, 3, 15),
        days_supply=30,
        quantity=30.0,
        channel="retail",
        plan_paid=50.00,
        gross_drug_cost=75.00,
        claim_status="paid",
    )
    assert record.claim_id == "C000000001"
    assert record.channel.value == "retail"
    assert record.claim_status.value == "paid"


def test_claim_record_invalid_ndc_too_short():
    """NDC11 shorter than 11 digits must raise ValidationError."""
    with pytest.raises(ValidationError, match="ndc11"):
        ClaimRecord(
            claim_id="C000000001",
            member_id="M0000001",
            group_id="G001",
            ndc11="1234567890",  # 10 digits
            fill_date=date(2024, 3, 15),
            days_supply=30,
            quantity=30.0,
            channel="retail",
            plan_paid=50.00,
            gross_drug_cost=75.00,
            claim_status="paid",
        )


def test_claim_record_invalid_ndc_non_digit():
    """NDC11 containing non-numeric characters must raise ValidationError."""
    with pytest.raises(ValidationError, match="ndc11"):
        ClaimRecord(
            claim_id="C000000001",
            member_id="M0000001",
            group_id="G001",
            ndc11="1234567890X",
            fill_date=date(2024, 3, 15),
            days_supply=30,
            quantity=30.0,
            channel="retail",
            plan_paid=50.00,
            gross_drug_cost=75.00,
            claim_status="paid",
        )


def test_claim_record_invalid_plan_paid_exceeds_gross():
    """plan_paid > gross_drug_cost must raise ValidationError."""
    with pytest.raises(ValidationError, match="plan_paid"):
        ClaimRecord(
            claim_id="C000000001",
            member_id="M0000001",
            group_id="G001",
            ndc11="12345678901",
            fill_date=date(2024, 3, 15),
            days_supply=30,
            quantity=30.0,
            channel="retail",
            plan_paid=100.00,  # exceeds gross
            gross_drug_cost=75.00,
            claim_status="paid",
        )


def test_claim_record_plan_paid_equals_gross_is_valid():
    """plan_paid == gross_drug_cost is the boundary case and must succeed."""
    record = ClaimRecord(
        claim_id="C000000002",
        member_id="M0000001",
        group_id="G001",
        ndc11="12345678901",
        fill_date=date(2024, 3, 15),
        days_supply=30,
        quantity=30.0,
        channel="retail",
        plan_paid=75.00,
        gross_drug_cost=75.00,
        claim_status="paid",
    )
    assert record.plan_paid == record.gross_drug_cost


def test_claim_record_all_channels():
    """ClaimRecord accepts all valid ChannelEnum values."""
    for channel in ["retail", "mail", "specialty"]:
        record = ClaimRecord(
            claim_id="C000000001",
            member_id="M0000001",
            group_id="G001",
            ndc11="12345678901",
            fill_date=date(2024, 3, 15),
            days_supply=30,
            quantity=30.0,
            channel=channel,
            plan_paid=50.00,
            gross_drug_cost=75.00,
            claim_status="paid",
        )
        assert record.channel.value == channel


def test_claim_record_all_statuses():
    """ClaimRecord accepts all valid ClaimStatusEnum values."""
    for status in ["paid", "reversed", "adjusted", "pending"]:
        record = ClaimRecord(
            claim_id="C000000001",
            member_id="M0000001",
            group_id="G001",
            ndc11="12345678901",
            fill_date=date(2024, 3, 15),
            days_supply=30,
            quantity=30.0,
            channel="retail",
            plan_paid=50.00,
            gross_drug_cost=75.00,
            claim_status=status,
        )
        assert record.claim_status.value == status


# ---------------------------------------------------------------------------
# DrugRecord
# ---------------------------------------------------------------------------


def test_drug_record_valid():
    """A correctly formed DrugRecord should instantiate without error."""
    record = DrugRecord(
        ndc11="12345678901",
        brand_family="TESTBRAND",
        manufacturer="TestMfr",
        gpi_class="0101",
        specialty_flag=False,
        package_size=30.0,
        effective_date_start=date(2023, 1, 1),
        effective_date_end=date(2026, 12, 31),
        launch_date=date(2023, 6, 1),
    )
    assert record.ndc11 == "12345678901"
    assert record.specialty_flag is False


def test_drug_record_end_before_start_raises():
    """effective_date_end before effective_date_start must raise ValidationError."""
    with pytest.raises(ValidationError, match="effective_date_end"):
        DrugRecord(
            ndc11="12345678901",
            brand_family="TESTBRAND",
            manufacturer="TestMfr",
            gpi_class="0101",
            specialty_flag=False,
            package_size=30.0,
            effective_date_start=date(2026, 1, 1),
            effective_date_end=date(2023, 1, 1),  # before start
            launch_date=date(2023, 6, 1),
        )


def test_drug_record_no_end_date_allowed():
    """effective_date_end=None (open-ended) is valid."""
    record = DrugRecord(
        ndc11="12345678901",
        brand_family="TESTBRAND",
        manufacturer="TestMfr",
        gpi_class="0101",
        specialty_flag=True,
        package_size=1.0,
        effective_date_start=date(2023, 1, 1),
        effective_date_end=None,
        launch_date=date(2023, 6, 1),
    )
    assert record.effective_date_end is None


# ---------------------------------------------------------------------------
# ContractRecord
# ---------------------------------------------------------------------------


def test_contract_record_per_30_day_valid():
    """PER_30_DAY_SCRIPT contract with no minimum_guarantee is valid."""
    record = ContractRecord(
        manufacturer="TestMfr",
        brand_family="TESTBRAND",
        client_id="G001",
        effective_date_start=date(2024, 1, 1),
        effective_date_end=date(2025, 12, 31),
        rebate_basis="PER_30_DAY_SCRIPT",
        rebate_rate=2.50,
        minimum_guarantee=None,
    )
    assert record.rebate_basis == RebateBasisEnum.PER_30_DAY_SCRIPT


def test_contract_record_pmpm_requires_minimum_guarantee():
    """PMPM_GUARANTEE basis must have minimum_guarantee set."""
    with pytest.raises(ValidationError, match="minimum_guarantee"):
        ContractRecord(
            manufacturer="TestMfr",
            brand_family="TESTBRAND",
            client_id="G001",
            effective_date_start=date(2024, 1, 1),
            rebate_basis="PMPM_GUARANTEE",
            rebate_rate=0.0,
            minimum_guarantee=None,  # must be set for PMPM
        )


def test_contract_record_pmpm_with_guarantee_valid():
    """PMPM_GUARANTEE contract with minimum_guarantee > 0 is valid."""
    record = ContractRecord(
        manufacturer="TestMfr",
        brand_family="TESTBRAND",
        client_id="G001",
        effective_date_start=date(2024, 1, 1),
        rebate_basis="PMPM_GUARANTEE",
        rebate_rate=0.0,
        minimum_guarantee=50_000.0,
    )
    assert record.minimum_guarantee == 50_000.0


def test_contract_record_all_rebate_bases():
    """ContractRecord accepts all four RebateBasisEnum values."""
    for basis in ["PER_30_DAY_SCRIPT", "PERCENT_GROSS_COST", "PER_UNIT"]:
        record = ContractRecord(
            manufacturer="TestMfr",
            brand_family="TESTBRAND",
            client_id="G001",
            effective_date_start=date(2024, 1, 1),
            rebate_basis=basis,
            rebate_rate=1.0,
        )
        assert record.rebate_basis.value == basis


# ---------------------------------------------------------------------------
# InvoiceRecord
# ---------------------------------------------------------------------------


def test_invoice_record_valid():
    """A correctly formed InvoiceRecord should instantiate without error."""
    record = InvoiceRecord(
        invoice_quarter="2024-Q1",
        manufacturer="TestMfr",
        ndc11="12345678901",
        client_id="G001",
        invoiced_utilization=100.0,
        expected_rebate=250.00,
        actual_rebate=245.00,
        disputed_rebate=0.00,
        paid_rebate=245.00,
    )
    assert record.invoice_quarter == "2024-Q1"


def test_invoice_record_quarter_format_invalid():
    """Invoice quarter not matching YYYY-QN format must raise ValidationError."""
    with pytest.raises(ValidationError):
        InvoiceRecord(
            invoice_quarter="Q1-2024",  # wrong format
            manufacturer="TestMfr",
            ndc11="12345678901",
            client_id="G001",
            invoiced_utilization=100.0,
            expected_rebate=250.00,
            actual_rebate=245.00,
            disputed_rebate=0.00,
            paid_rebate=245.00,
        )


def test_invoice_record_paid_exceeds_actual_raises():
    """paid_rebate > actual_rebate must raise ValidationError."""
    with pytest.raises(ValidationError, match="paid_rebate"):
        InvoiceRecord(
            invoice_quarter="2024-Q1",
            manufacturer="TestMfr",
            ndc11="12345678901",
            client_id="G001",
            invoiced_utilization=100.0,
            expected_rebate=250.00,
            actual_rebate=200.00,
            disputed_rebate=0.00,
            paid_rebate=300.00,  # exceeds actual
        )


def test_invoice_record_disputed_exceeds_actual_raises():
    """disputed_rebate > actual_rebate must raise ValidationError."""
    with pytest.raises(ValidationError, match="disputed_rebate"):
        InvoiceRecord(
            invoice_quarter="2024-Q1",
            manufacturer="TestMfr",
            ndc11="12345678901",
            client_id="G001",
            invoiced_utilization=100.0,
            expected_rebate=250.00,
            actual_rebate=200.00,
            disputed_rebate=300.00,  # exceeds actual
            paid_rebate=0.00,
        )


def test_invoice_record_all_valid_quarters():
    """All four quarter suffixes (Q1–Q4) are accepted."""
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        record = InvoiceRecord(
            invoice_quarter=f"2024-{q}",
            manufacturer="TestMfr",
            ndc11="12345678901",
            client_id="G001",
            invoiced_utilization=100.0,
            expected_rebate=250.00,
            actual_rebate=245.00,
            disputed_rebate=0.00,
            paid_rebate=245.00,
        )
        assert record.invoice_quarter == f"2024-{q}"


# ---------------------------------------------------------------------------
# FormularyRecord
# ---------------------------------------------------------------------------


def test_formulary_record_valid():
    """A correctly formed FormularyRecord should instantiate without error."""
    record = FormularyRecord(
        client_id="G001",
        ndc11="12345678901",
        brand_family="TESTBRAND",
        tier=3,
        preferred_flag=False,
        pa_required=True,
        st_required=False,
        ql_required=False,
        effective_date_start=date(2024, 1, 1),
        effective_date_end=date(2025, 12, 31),
    )
    assert record.tier == 3
    assert record.pa_required is True


def test_formulary_record_tier_out_of_range_raises():
    """Tier value outside [1, 6] must raise ValidationError."""
    with pytest.raises(ValidationError):
        FormularyRecord(
            client_id="G001",
            ndc11="12345678901",
            brand_family="TESTBRAND",
            tier=7,  # out of range
            preferred_flag=False,
            pa_required=False,
            st_required=False,
            ql_required=False,
            effective_date_start=date(2024, 1, 1),
        )


# ---------------------------------------------------------------------------
# AnomalyLabel
# ---------------------------------------------------------------------------


def test_anomaly_label_valid():
    """A correctly formed AnomalyLabel should instantiate without error."""
    label = AnomalyLabel(
        entity_type="ndc_group_quarter",
        ndc11="12345678901",
        client_id="G001",
        quarter="2024-Q3",
        anomaly_type="MISSING_REBATE",
        recoverable=True,
        estimated_impact=5_000.00,
        root_cause="Manufacturer did not submit rebate invoice",
    )
    assert label.anomaly_type == AnomalyTypeEnum.MISSING_REBATE
    assert label.recoverable is True


def test_anomaly_label_quarter_format_invalid():
    """AnomalyLabel with invalid quarter format must raise ValidationError."""
    with pytest.raises(ValidationError):
        AnomalyLabel(
            entity_type="ndc_group_quarter",
            ndc11="12345678901",
            client_id="G001",
            quarter="2024Q3",  # missing hyphen
            anomaly_type="MISSING_REBATE",
            recoverable=True,
            estimated_impact=5_000.00,
            root_cause="Test",
        )


def test_anomaly_label_all_anomaly_types():
    """AnomalyLabel accepts all seven AnomalyTypeEnum values."""
    anomaly_types = [
        "MISSING_REBATE",
        "UNMAPPED_NDC",
        "REBATE_YIELD_COLLAPSE",
        "SPECIALTY_CHANNEL_OMISSION",
        "UNIT_CONVERSION_ERROR",
        "DISPUTE_SPIKE",
        "GUARANTEE_TRUE_UP_MISSING",
    ]
    for atype in anomaly_types:
        label = AnomalyLabel(
            entity_type="ndc_group_quarter",
            quarter="2024-Q1",
            anomaly_type=atype,
            recoverable=True,
            estimated_impact=0.0,
            root_cause="Test",
        )
        assert label.anomaly_type.value == atype


def test_anomaly_label_ndc_none_allowed():
    """AnomalyLabel with ndc11=None (non-NDC anomaly) is valid."""
    label = AnomalyLabel(
        entity_type="group_quarter",
        ndc11=None,
        client_id="G001",
        quarter="2024-Q1",
        anomaly_type="DISPUTE_SPIKE",
        recoverable=True,
        estimated_impact=10_000.0,
        root_cause="Dispute spike at manufacturer brand level",
    )
    assert label.ndc11 is None


def test_anomaly_label_all_entity_types():
    """AnomalyLabel accepts all EntityTypeEnum values."""
    for etype in ["ndc_group_quarter", "ndc_quarter", "group_quarter", "contract"]:
        label = AnomalyLabel(
            entity_type=etype,
            quarter="2024-Q1",
            anomaly_type="MISSING_REBATE",
            recoverable=True,
            estimated_impact=0.0,
            root_cause="Test",
        )
        assert label.entity_type == EntityTypeEnum(etype)
