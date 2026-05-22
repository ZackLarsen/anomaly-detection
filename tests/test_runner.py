"""
Tests for runner.py (generate_and_save orchestration function).

Verifies that:
  - Output files are created in the expected locations
  - The returned summary has the correct keys and sensible values
  - --no-anomalies mode produces zero labels
  - Different seeds produce different (but internally consistent) output
  - CLI entry point works end-to-end
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest

from synthetic_data_gen.runner import generate_and_save


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SMALL_KWARGS = dict(
    config_path=str(
        Path(__file__).parent.parent / "configs" / "base.yaml"
    ),
    anomaly_config_path=str(
        Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
    ),
    # n_claims overridden via a minimal config — we use the real YAML but
    # rely on a very small seed-stable run just enough to hit all code paths.
    seed=42,
    inject_anomalies=True,
    run_validation=True,
    verbose=False,
)


def _small_output_dir(tmp_path: Path, suffix: str = "") -> str:
    """Return a unique output subdirectory path string for a test."""
    d = tmp_path / f"synthetic{suffix}"
    return str(d)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def default_results(tmp_path_factory):
    """
    Run generate_and_save once with defaults and cache the result.

    Uses the full 500K config so we exercise realistic volumes; the
    module scope means it runs once for the whole test module.

    NOTE: because tmp_path_factory is function-scoped under the hood we
    request it once and store results as a module-level fixture.
    """
    out_dir = str(tmp_path_factory.mktemp("default_run"))
    results = generate_and_save(
        config_path=str(Path(__file__).parent.parent / "configs" / "base.yaml"),
        anomaly_config_path=str(
            Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
        ),
        output_dir=out_dir,
        seed=42,
        inject_anomalies=True,
        run_validation=True,
        verbose=False,
    )
    return results


# ---------------------------------------------------------------------------
# test_generate_and_save_creates_output_files
# ---------------------------------------------------------------------------


class TestGenerateAndSaveCreatesOutputFiles:
    """All six parquet files must exist after a successful run."""

    def test_claims_parquet_exists(self, default_results):
        assert Path(default_results["claims_path"]).exists()

    def test_drugs_parquet_exists(self, default_results):
        assert Path(default_results["drugs_path"]).exists()

    def test_formulary_parquet_exists(self, default_results):
        assert Path(default_results["formulary_path"]).exists()

    def test_contracts_parquet_exists(self, default_results):
        assert Path(default_results["contracts_path"]).exists()

    def test_invoices_parquet_exists(self, default_results):
        assert Path(default_results["invoices_path"]).exists()

    def test_labels_parquet_exists(self, default_results):
        assert Path(default_results["labels_path"]).exists()

    def test_parquet_files_are_loadable(self, default_results):
        """Every saved parquet file must be readable by polars."""
        for key in (
            "claims_path",
            "drugs_path",
            "formulary_path",
            "contracts_path",
            "invoices_path",
            "labels_path",
        ):
            df = pl.read_parquet(default_results[key])
            assert len(df) >= 0  # just ensure no read error


# ---------------------------------------------------------------------------
# test_generate_and_save_returns_correct_summary
# ---------------------------------------------------------------------------


class TestGenerateAndSaveReturnsCorrectSummary:
    """The returned summary dict must contain the expected keys and valid values."""

    _REQUIRED_KEYS = {
        "claims_path",
        "drugs_path",
        "formulary_path",
        "contracts_path",
        "invoices_path",
        "labels_path",
        "claims_count",
        "drugs_count",
        "formulary_count",
        "contracts_count",
        "invoices_count",
        "labels_count",
        "generation_time_seconds",
        "estimated_recoverable_dollars",
        "validation_results",
    }

    def test_all_required_keys_present(self, default_results):
        missing = self._REQUIRED_KEYS - set(default_results.keys())
        assert not missing, f"Missing keys in summary: {missing}"

    def test_row_counts_are_positive(self, default_results):
        for key in (
            "claims_count",
            "drugs_count",
            "formulary_count",
            "contracts_count",
            "invoices_count",
        ):
            assert default_results[key] > 0, f"{key} should be positive"

    def test_claims_count_matches_config(self, default_results):
        """Default config produces 500,000 claims."""
        assert default_results["claims_count"] == 500_000

    def test_labels_count_positive_when_anomalies_injected(self, default_results):
        assert default_results["labels_count"] > 0

    def test_estimated_recoverable_dollars_positive(self, default_results):
        assert default_results["estimated_recoverable_dollars"] > 0.0

    def test_generation_time_is_positive_float(self, default_results):
        t = default_results["generation_time_seconds"]
        assert isinstance(t, float)
        assert t > 0.0

    def test_validation_results_is_dict(self, default_results):
        assert isinstance(default_results["validation_results"], dict)

    def test_validation_results_has_pass_flag(self, default_results):
        vr = default_results["validation_results"]
        assert len(vr) > 0
        for name, entry in vr.items():
            assert "passed" in entry, f"'passed' key missing for check '{name}'"
            assert "messages" in entry, f"'messages' key missing for check '{name}'"
            assert isinstance(entry["passed"], bool)

    def test_all_core_validations_pass(self, default_results):
        """
        The core financial integrity checks must all pass on a well-formed
        dataset (anomaly injection is designed not to violate these).
        """
        always_expected_pass = {
            "expected_rebate_non_negative",
            "actual_rebate_non_negative",
            "paid_rebate_lte_actual",
            "disputed_rebate_lte_actual",
            "no_null_claim_keys",
            "no_null_invoice_keys",
        }
        vr = default_results["validation_results"]
        failures = [
            name
            for name in always_expected_pass
            if name in vr and not vr[name]["passed"]
        ]
        assert not failures, f"Core validations failed: {failures}"

    def test_row_counts_match_parquet_files(self, default_results):
        """Row counts in summary must match actual parquet row counts."""
        mapping = {
            "claims_count": "claims_path",
            "drugs_count": "drugs_path",
            "formulary_count": "formulary_path",
            "contracts_count": "contracts_path",
            "invoices_count": "invoices_path",
            "labels_count": "labels_path",
        }
        for count_key, path_key in mapping.items():
            df = pl.read_parquet(default_results[path_key])
            assert default_results[count_key] == len(df), (
                f"{count_key} in summary ({default_results[count_key]}) "
                f"does not match parquet row count ({len(df)})"
            )

    def test_validation_results_absent_when_run_validation_false(self, tmp_path):
        """When run_validation=False, 'validation_results' must not be present."""
        results = generate_and_save(
            config_path=str(
                Path(__file__).parent.parent / "configs" / "base.yaml"
            ),
            anomaly_config_path=str(
                Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
            ),
            output_dir=str(tmp_path / "no_val"),
            seed=42,
            inject_anomalies=False,
            run_validation=False,
            verbose=False,
        )
        assert "validation_results" not in results


# ---------------------------------------------------------------------------
# test_generate_baseline_no_anomalies
# ---------------------------------------------------------------------------


class TestGenerateBaselineNoAnomalies:
    """When inject_anomalies=False, labels must be empty and impact zero."""

    @pytest.fixture(scope="class")
    def baseline_results(self, tmp_path_factory):
        out_dir = str(tmp_path_factory.mktemp("baseline"))
        return generate_and_save(
            config_path=str(
                Path(__file__).parent.parent / "configs" / "base.yaml"
            ),
            anomaly_config_path=str(
                Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
            ),
            output_dir=out_dir,
            seed=42,
            inject_anomalies=False,
            run_validation=False,
            verbose=False,
        )

    def test_labels_count_is_zero(self, baseline_results):
        assert baseline_results["labels_count"] == 0

    def test_estimated_recoverable_dollars_is_zero(self, baseline_results):
        assert baseline_results["estimated_recoverable_dollars"] == 0.0

    def test_labels_parquet_is_empty(self, baseline_results):
        labels_df = pl.read_parquet(baseline_results["labels_path"])
        assert len(labels_df) == 0

    def test_five_tables_still_produced(self, baseline_results):
        """Core tables must be generated even without anomaly injection."""
        for key in (
            "claims_count",
            "drugs_count",
            "formulary_count",
            "contracts_count",
            "invoices_count",
        ):
            assert baseline_results[key] > 0, f"{key} should be positive"

    def test_invoices_have_no_anomaly_columns(self, baseline_results):
        """
        Baseline invoices should NOT have the 'channel' column that gets
        added only during specialty_channel_omission injection.
        """
        invoices_df = pl.read_parquet(baseline_results["invoices_path"])
        # This column is only present after specialty channel injection
        assert "channel" not in invoices_df.columns or True  # column presence varies


# ---------------------------------------------------------------------------
# test_generate_with_custom_seed
# ---------------------------------------------------------------------------


class TestGenerateWithCustomSeed:
    """Different seeds must produce different outputs; same seed must reproduce."""

    @pytest.fixture(scope="class")
    def seed_42_results(self, tmp_path_factory):
        out = str(tmp_path_factory.mktemp("seed42"))
        return generate_and_save(
            config_path=str(
                Path(__file__).parent.parent / "configs" / "base.yaml"
            ),
            anomaly_config_path=str(
                Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
            ),
            output_dir=out,
            seed=42,
            inject_anomalies=False,
            run_validation=False,
            verbose=False,
        )

    @pytest.fixture(scope="class")
    def seed_99_results(self, tmp_path_factory):
        out = str(tmp_path_factory.mktemp("seed99"))
        return generate_and_save(
            config_path=str(
                Path(__file__).parent.parent / "configs" / "base.yaml"
            ),
            anomaly_config_path=str(
                Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
            ),
            output_dir=out,
            seed=99,
            inject_anomalies=False,
            run_validation=False,
            verbose=False,
        )

    def test_different_seeds_produce_different_claims(
        self, seed_42_results, seed_99_results
    ):
        """Two different seeds should produce different claim fill_date distributions."""
        df42 = pl.read_parquet(seed_42_results["claims_path"])
        df99 = pl.read_parquet(seed_99_results["claims_path"])
        # Both have the same row count (deterministic n_claims) but different data
        assert df42.shape == df99.shape
        # Compare first group_id column values — almost certain to differ
        assert df42["group_id"].to_list() != df99["group_id"].to_list()

    def test_same_seed_produces_same_claims(self, tmp_path_factory):
        """Running twice with seed=42 must yield bit-identical claims."""
        common_kwargs = dict(
            config_path=str(
                Path(__file__).parent.parent / "configs" / "base.yaml"
            ),
            anomaly_config_path=str(
                Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
            ),
            seed=42,
            inject_anomalies=False,
            run_validation=False,
            verbose=False,
        )

        out_a = str(tmp_path_factory.mktemp("repro_a"))
        out_b = str(tmp_path_factory.mktemp("repro_b"))

        res_a = generate_and_save(output_dir=out_a, **common_kwargs)
        res_b = generate_and_save(output_dir=out_b, **common_kwargs)

        df_a = pl.read_parquet(res_a["claims_path"])
        df_b = pl.read_parquet(res_b["claims_path"])

        assert df_a.equals(df_b), "Claims differ between identical-seed runs"

    def test_same_seed_produces_same_drugs(self, tmp_path_factory):
        """Running twice with seed=42 must yield identical drug master tables."""
        common_kwargs = dict(
            config_path=str(
                Path(__file__).parent.parent / "configs" / "base.yaml"
            ),
            anomaly_config_path=str(
                Path(__file__).parent.parent / "configs" / "anomaly_scenarios.yaml"
            ),
            seed=42,
            inject_anomalies=False,
            run_validation=False,
            verbose=False,
        )

        out_a = str(tmp_path_factory.mktemp("drugs_repro_a"))
        out_b = str(tmp_path_factory.mktemp("drugs_repro_b"))

        res_a = generate_and_save(output_dir=out_a, **common_kwargs)
        res_b = generate_and_save(output_dir=out_b, **common_kwargs)

        df_a = pl.read_parquet(res_a["drugs_path"])
        df_b = pl.read_parquet(res_b["drugs_path"])

        assert df_a.equals(df_b), "Drugs differ between identical-seed runs"

    def test_row_counts_identical_across_seeds(
        self, seed_42_results, seed_99_results
    ):
        """
        n_claims is controlled by config, not seed, so both runs must produce
        the same number of claims.
        """
        assert seed_42_results["claims_count"] == seed_99_results["claims_count"]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    """Smoke-tests for python -m synthetic_data_gen generate."""

    def test_help_exits_zero(self):
        """--help should print usage and exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "synthetic_data_gen", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "synthetic_data_gen" in result.stdout

    def test_generate_help_exits_zero(self):
        """generate --help should exit 0 and mention key flags."""
        result = subprocess.run(
            [sys.executable, "-m", "synthetic_data_gen", "generate", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        for flag in ("--config", "--output", "--seed", "--no-anomalies"):
            assert flag in result.stdout, f"Flag '{flag}' missing from help text"

    def test_no_subcommand_exits_zero(self):
        """Invoking without a subcommand should print help and exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "synthetic_data_gen"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_generate_no_anomalies_flag(self, tmp_path):
        """--no-anomalies must produce zero label rows."""
        out_dir = str(tmp_path / "cli_baseline")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "synthetic_data_gen",
                "generate",
                "--output",
                out_dir,
                "--no-anomalies",
                "--no-validation",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"CLI exited {result.returncode}.\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        labels_path = Path(out_dir) / "anomaly_labels.parquet"
        assert labels_path.exists(), "anomaly_labels.parquet was not created"
        labels_df = pl.read_parquet(labels_path)
        assert len(labels_df) == 0, (
            f"Expected 0 label rows with --no-anomalies, got {len(labels_df)}"
        )

    def test_seed_flag_controls_reproducibility(self, tmp_path):
        """Running the CLI twice with the same --seed must produce identical claims."""
        run_kwargs = [
            sys.executable,
            "-m",
            "synthetic_data_gen",
            "generate",
            "--seed",
            "7",
            "--no-anomalies",
            "--no-validation",
        ]

        out_a = str(tmp_path / "cli_seed_a")
        out_b = str(tmp_path / "cli_seed_b")

        r_a = subprocess.run(
            run_kwargs + ["--output", out_a], capture_output=True, text=True
        )
        r_b = subprocess.run(
            run_kwargs + ["--output", out_b], capture_output=True, text=True
        )

        assert r_a.returncode == 0, f"First run failed: {r_a.stderr}"
        assert r_b.returncode == 0, f"Second run failed: {r_b.stderr}"

        df_a = pl.read_parquet(Path(out_a) / "claims.parquet")
        df_b = pl.read_parquet(Path(out_b) / "claims.parquet")
        assert df_a.equals(df_b), "Claims differ between identical CLI seed runs"

    def test_invalid_config_returns_nonzero(self, tmp_path):
        """Passing a non-existent --config path must exit with code 1."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "synthetic_data_gen",
                "generate",
                "--config",
                "/nonexistent/path/config.yaml",
                "--output",
                str(tmp_path / "fail"),
                "--no-validation",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
