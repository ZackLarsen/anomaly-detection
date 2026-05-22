"""
Command-line entry point for the synthetic Rx rebate data generator.

Invoked as:
    python -m synthetic_data_gen generate [options]

Use ``python -m synthetic_data_gen --help`` for full usage.
"""

from __future__ import annotations

import argparse
import sys

from .runner import generate_and_save


def main() -> int:
    """
    Parse CLI arguments and dispatch to generate_and_save.

    Returns:
        0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        prog="synthetic_data_gen",
        description="Generate synthetic Rx rebate data with anomaly injection",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ------------------------------------------------------------------
    # Subcommand: generate
    # ------------------------------------------------------------------
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate synthetic dataset",
        description=(
            "Generate a full synthetic Rx rebate dataset including claims, "
            "drugs, formulary, contracts, invoices, and optionally injected "
            "anomaly labels.  Outputs are written as parquet files."
        ),
    )

    generate_parser.add_argument(
        "--config",
        default="configs/base.yaml",
        metavar="PATH",
        help="Path to base configuration YAML (default: configs/base.yaml)",
    )
    generate_parser.add_argument(
        "--anomalies",
        default="configs/anomaly_scenarios.yaml",
        metavar="PATH",
        help=(
            "Path to anomaly scenarios YAML "
            "(default: configs/anomaly_scenarios.yaml)"
        ),
    )
    generate_parser.add_argument(
        "--output",
        default="data/synthetic",
        metavar="DIR",
        help="Output directory for parquet files (default: data/synthetic)",
    )
    generate_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        metavar="INT",
        help="Random seed for reproducibility (default: 42)",
    )
    generate_parser.add_argument(
        "--no-anomalies",
        action="store_true",
        help="Skip anomaly injection and generate a clean baseline dataset",
    )
    generate_parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Skip validation checks (faster, useful for large-scale testing)",
    )
    generate_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed progress messages during generation",
    )

    args = parser.parse_args()

    if args.command == "generate":
        try:
            results = generate_and_save(
                config_path=args.config,
                anomaly_config_path=args.anomalies,
                output_dir=args.output,
                seed=args.seed,
                inject_anomalies=not args.no_anomalies,
                run_validation=not args.no_validation,
                verbose=args.verbose,
            )
            print("\nDataset generation complete!")
            print(f"Output directory: {args.output}")
            print(f"  claims   : {results['claims_count']:>12,} rows")
            print(f"  drugs    : {results['drugs_count']:>12,} rows")
            print(f"  formulary: {results['formulary_count']:>12,} rows")
            print(f"  contracts: {results['contracts_count']:>12,} rows")
            print(f"  invoices : {results['invoices_count']:>12,} rows")
            print(f"  labels   : {results['labels_count']:>12,} rows")
            print(
                f"  recoverable $ : "
                f"${results['estimated_recoverable_dollars']:>12,.2f}"
            )
            print(
                f"  time (s)      : "
                f"{results['generation_time_seconds']:>12.1f}s"
            )
            return 0
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            print(
                "Check that --config and --anomalies paths exist.",
                file=sys.stderr,
            )
            return 1
        except OSError as exc:
            print(f"Error creating output directory: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
