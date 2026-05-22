"""
Synthetic Rx rebate data generator.

Run this script to generate a full synthetic dataset using the default
configuration.  Alternatively, use the CLI:

    python -m synthetic_data_gen generate

For all available options:

    python -m synthetic_data_gen generate --help
"""

from synthetic_data_gen.runner import generate_and_save


def main() -> None:
    """Generate synthetic dataset using default configuration."""
    print("Generating synthetic Rx rebate dataset...")
    results = generate_and_save(
        config_path="configs/base.yaml",
        anomaly_config_path="configs/anomaly_scenarios.yaml",
        output_dir="data/synthetic",
        seed=42,
        inject_anomalies=True,
        run_validation=True,
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("Dataset Generation Summary")
    print("=" * 60)
    for key, value in results.items():
        if key == "validation_results":
            n_checks = len(value)
            n_passed = sum(1 for v in value.values() if v["passed"])
            print(f"{'validation_results':30s}: {n_passed}/{n_checks} checks passed")
        elif not key.endswith("_path"):
            print(f"{key:30s}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()
