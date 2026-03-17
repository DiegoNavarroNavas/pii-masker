"""CLI interface for benchmarking PII detection."""

import argparse
import json
import sys
from pathlib import Path

from benchmark.evaluators.presidio_eval import run_benchmark
from benchmark.loaders.base import FilterSpec
from benchmark.loaders.synthetic import SyntheticDatasetLoader


DATASET_LOADERS = {
    "synthetic": SyntheticDatasetLoader,
}


def parse_filter_value(filter_str: str) -> tuple[str, str]:
    """Parse a filter string like 'language=de' into (key, value)."""
    if "=" not in filter_str:
        sys.exit(f"Error: Invalid filter format '{filter_str}'. Use format: field=value")
    key, value = filter_str.split("=", 1)
    return key.strip(), value.strip()


def list_dataset_fields(dataset: str) -> None:
    """Print available fields for a dataset."""
    loader_class = DATASET_LOADERS[dataset]
    loader = loader_class()
    info = loader.list_fields()

    print(f"\nDataset: {dataset}")
    if "error" in info and info["error"]:
        print(f"Error: {info['error']}")
        return

    if "dataset" in info:
        print(f"Source: {info['dataset']}")

    print(f"\nAvailable fields:")
    for field in info.get("fields", []):
        print(f"  - {field}")

    if "sample" in info and info["sample"]:
        print(f"\nSample record:")
        for k, v in info["sample"].items():
            print(f"  {k}: {v}")


def run(args):
    """Run benchmark with parsed arguments.

    Args:
        args: Parsed arguments from argparse (must have dataset, config,
              max_samples, output, and split attributes).
    """
    # Handle --list-fields
    if args.list_fields:
        list_dataset_fields(args.dataset)
        return

    # Build filter specification
    custom_filters = {}
    if args.filter:
        for f in args.filter:
            key, value = parse_filter_value(f)
            custom_filters[key] = value

    filters = FilterSpec(
        locale=args.locale,
        domain=args.domain,
        custom_filters=custom_filters,
    )

    # Load dataset with filters
    loader_class = DATASET_LOADERS[args.dataset]
    loader = loader_class(split=args.split, filters=filters)
    samples = loader.load(max_samples=args.max_samples)

    if not samples:
        sys.exit("Error: No samples loaded from dataset (check your filter criteria)")

    # Parse configs (can be comma-separated for comparison)
    configs = [c.strip() for c in args.config.split(",")]

    results = []
    for config_path in configs:
        print(f"\nBenchmarking with config: {config_path}", file=sys.stderr)
        result = run_benchmark(
            config_path=config_path,
            samples=samples,
            dataset_name=args.dataset,
            evaluation_mode=args.evaluation_mode,
        )
        results.append(result)
        print(result)

    # Save results if output specified
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # If multiple configs, save as list; otherwise single result
        output_data = [r.to_dict() for r in results] if len(results) > 1 else results[0].to_dict()
        output_path.write_text(json.dumps(output_data, indent=2))
        print(f"\nResults saved to: {args.output}", file=sys.stderr)


def main():
    """Standalone entry point for benchmark CLI."""
    parser = argparse.ArgumentParser(
        prog="pii_masker benchmark",
        description="Benchmark PII detection against standard datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available fields in a dataset
  python -m pii_masker benchmark --dataset <dataset_name> --list-fields

  # Benchmark with a preset
  python -m pii_masker benchmark --dataset <dataset_name> -c gliner

  # Benchmark German locale only
  python -m pii_masker benchmark --dataset <dataset_name> -c german --locale de

  # Benchmark with domain filter
  python -m pii_masker benchmark --dataset <dataset_name> -c gliner --domain finance

  # Custom field filtering
  python -m pii_masker benchmark --dataset <dataset_name> -c gliner --filter language=de

  # Quick test with limited samples
  python -m pii_masker benchmark --dataset <dataset_name> -c gliner --max-samples 100

  # Compare multiple configs
  python -m pii_masker benchmark --dataset <dataset_name> -c gliner,english-fast

  # Save results to file
  python -m pii_masker benchmark --dataset <dataset_name> -c gliner --output results.json

Run with --help to see available datasets.
""",
    )

    parser.add_argument(
        "--dataset",
        "-d",
        required=True,
        choices=list(DATASET_LOADERS.keys()),
        help="Dataset to benchmark against",
    )
    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help="Config preset name or path to YAML config file. "
        "Multiple configs can be comma-separated.",
    )
    parser.add_argument(
        "--max-samples",
        "-n",
        type=int,
        default=None,
        help="Maximum number of samples to evaluate (default: all)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path for JSON results",
    )
    parser.add_argument(
        "--split",
        "-s",
        type=str,
        default="train",
        help="Dataset split to use (default: train)",
    )
    parser.add_argument(
        "--locale",
        "-l",
        type=str,
        default=None,
        help="Filter by locale/language (e.g., 'de', 'en', 'en-US')",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter by domain (e.g., 'finance', 'medical', 'code')",
    )
    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        action="append",
        default=None,
        help="Custom filter as field=value (can be used multiple times)",
    )
    parser.add_argument(
        "--list-fields",
        action="store_true",
        help="List available fields in the dataset for filtering",
    )
    parser.add_argument(
        "--evaluation-mode",
        "-e",
        choices=["coarse", "granular"],
        default="coarse",
        help="Evaluation mode: 'coarse' normalizes entity types for fair comparison, "
             "'granular' uses exact matching (default: coarse)",
    )

    args = parser.parse_args()

    # Validate that --config is provided unless --list-fields
    if not args.list_fields and not args.config:
        parser.error("--config is required unless using --list-fields")

    run(args)


if __name__ == "__main__":
    main()
