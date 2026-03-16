"""CLI entry point for generating synthetic benchmark datasets.

Generates JSONL files with Faker-filled templates for benchmarking PII detection.
"""

import argparse
import json
import sys
from pathlib import Path

from benchmark.synthetic.generator import TemplateFiller


def load_templates(templates_dir: str) -> list[dict]:
    """Load all template JSON files from directory.

    Args:
        templates_dir: Path to templates directory.

    Returns:
        List of template dicts.
    """
    templates_path = Path(templates_dir)
    if not templates_path.exists():
        raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

    templates = []
    json_files = sorted(templates_path.glob("*.json"))

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                file_templates = json.load(f)
                templates.extend(file_templates)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse {json_file}: {e}", file=sys.stderr)

    return templates


def generate_samples(
    templates: list[dict],
    seed: int | None = None,
    locale_filter: str | None = None,
    max_samples: int | None = None,
) -> list[dict]:
    """Generate benchmark samples from templates.

    Args:
        templates: List of template dicts.
        seed: Random seed for reproducibility.
        locale_filter: Filter by locale (e.g., 'de_CH').
        max_samples: Maximum number of samples to generate.

    Returns:
        List of sample dicts ready for JSONL output.
    """
    # Filter by locale if specified
    if locale_filter:
        templates = [t for t in templates if t.get("locale") == locale_filter]

    if max_samples:
        templates = templates[:max_samples]

    # Group templates by locale for locale-aware generation
    by_locale: dict[str, list[dict]] = {}
    for template in templates:
        locale = template.get("locale", "de_CH")
        if locale not in by_locale:
            by_locale[locale] = []
        by_locale[locale].append(template)

    samples = []
    sample_id = 1

    for locale, locale_templates in by_locale.items():
        filler = TemplateFiller(locale=locale, seed=seed)

        for template in locale_templates:
            filled = filler.fill_template_dict(template)

            # Convert spans to output format
            ground_truth = [
                {
                    "entity_type": span.entity_type,
                    "start": span.start,
                    "end": span.end,
                    "value": span.value,
                }
                for span in filled.spans
            ]

            sample = {
                "id": f"synthetic_{sample_id:04d}",
                "text": filled.text,
                "ground_truth": ground_truth,
                "metadata": filled.metadata,
            }
            samples.append(sample)
            sample_id += 1

    return samples


def validate_samples(samples: list[dict]) -> list[dict]:
    """Validate generated samples.

    Checks that:
    - Spans point to correct text positions
    - Entity types are valid
    - No overlapping spans

    Args:
        samples: List of sample dicts.

    Returns:
        List of validation errors.
    """
    errors = []

    for sample in samples:
        sample_id = sample["id"]
        text = sample["text"]

        for i, span in enumerate(sample["ground_truth"]):
            start = span["start"]
            end = span["end"]
            value = span["value"]
            entity_type = span["entity_type"]

            # Check bounds
            if start < 0 or end > len(text):
                errors.append({
                    "sample_id": sample_id,
                    "span_index": i,
                    "error": f"Span [{start}:{end}] out of bounds (text length: {len(text)})",
                })
                continue

            # Check that span value matches text
            actual_value = text[start:end]
            if actual_value != value:
                errors.append({
                    "sample_id": sample_id,
                    "span_index": i,
                    "error": f"Span value mismatch: expected '{value}', got '{actual_value}'",
                })

    return errors


def write_jsonl(samples: list[dict], output_path: str) -> None:
    """Write samples to JSONL file.

    Args:
        samples: List of sample dicts.
        output_path: Path to output file.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")


def main():
    """Main entry point for dataset generation CLI."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic PII benchmark dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate dataset from all templates
  python -m benchmark.synthetic.generate_dataset \\
      --templates ./benchmark/synthetic/templates/ \\
      --output ./benchmark/synthetic/generated/swiss_benchmark.jsonl

  # Generate with specific seed for reproducibility
  python -m benchmark.synthetic.generate_dataset \\
      --templates ./benchmark/synthetic/templates/ \\
      --output ./benchmark/synthetic/generated/test.jsonl \\
      --seed 42

  # Generate only German (Swiss) templates
  python -m benchmark.synthetic.generate_dataset \\
      --templates ./benchmark/synthetic/templates/ \\
      --output ./benchmark/synthetic/generated/de_ch.jsonl \\
      --locale de_CH

  # Quick test with limited samples
  python -m benchmark.synthetic.generate_dataset \\
      --templates ./benchmark/synthetic/templates/ \\
      --output test.jsonl \\
      --seed 42 \\
      --max-samples 100 \\
      --validate
""",
    )

    parser.add_argument(
        "--templates",
        "-t",
        required=True,
        help="Path to templates directory",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--locale",
        "-l",
        type=str,
        default=None,
        help="Filter by locale (e.g., 'de_CH', 'fr_CH', 'it_CH')",
    )
    parser.add_argument(
        "--max-samples",
        "-n",
        type=int,
        default=None,
        help="Maximum number of samples to generate",
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Run validation checks on generated samples",
    )

    args = parser.parse_args()

    # Load templates
    print(f"Loading templates from: {args.templates}", file=sys.stderr)
    templates = load_templates(args.templates)
    print(f"Loaded {len(templates)} templates", file=sys.stderr)

    # Filter by locale if specified
    if args.locale:
        original_count = len(templates)
        templates = [t for t in templates if t.get("locale") == args.locale]
        print(f"Filtered to {len(templates)} templates for locale '{args.locale}'", file=sys.stderr)

    # Apply max samples limit
    if args.max_samples:
        templates = templates[:args.max_samples]
        print(f"Limited to {len(templates)} templates", file=sys.stderr)

    # Generate samples
    print("Generating samples...", file=sys.stderr)
    samples = generate_samples(
        templates=templates,
        seed=args.seed,
        locale_filter=None,  # Already filtered
        max_samples=None,  # Already limited
    )

    # Validate if requested
    if args.validate:
        print("Validating samples...", file=sys.stderr)
        errors = validate_samples(samples)
        if errors:
            print(f"Validation found {len(errors)} errors:", file=sys.stderr)
            for error in errors[:10]:  # Show first 10 errors
                print(f"  {error}", file=sys.stderr)
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more", file=sys.stderr)
        else:
            print("Validation passed!", file=sys.stderr)

    # Write output
    print(f"Writing {len(samples)} samples to: {args.output}", file=sys.stderr)
    write_jsonl(samples, args.output)

    # Print summary
    print(f"\nGenerated {len(samples)} samples", file=sys.stderr)

    # Count by locale
    by_locale: dict[str, int] = {}
    for sample in samples:
        locale = sample["metadata"].get("locale", "unknown")
        by_locale[locale] = by_locale.get(locale, 0) + 1

    print("By locale:", file=sys.stderr)
    for locale, count in sorted(by_locale.items()):
        print(f"  {locale}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
