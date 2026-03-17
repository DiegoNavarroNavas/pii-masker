"""Synthetic benchmark dataset generation.

This package provides tools for generating synthetic PII benchmark data
from templates using Faker.

Usage:
    # Generate a dataset
    python -m benchmark.synthetic.generate_dataset \\
        --templates ./benchmark/synthetic/templates/ \\
        --output ./benchmark/synthetic/generated/swiss_benchmark.jsonl \\
        --seed 42

    # Run benchmark with synthetic dataset
    python pii_masker.py benchmark --dataset synthetic -c gliner
"""

from benchmark.synthetic.generator import (
    EntitySpan,
    FilledTemplate,
    TemplateFiller,
)

__all__ = [
    "EntitySpan",
    "FilledTemplate",
    "TemplateFiller",
]
