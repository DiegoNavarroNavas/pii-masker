"""Benchmark result formatting and reporting."""

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class EntityMetrics:
    """Metrics for a single entity type."""

    entity_type: str
    precision: float
    recall: float
    f1: float
    support: int  # Number of ground truth instances


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    dataset: str
    config_name: str
    total_samples: int
    overall_precision: float
    overall_recall: float
    overall_f1: float
    total_time_seconds: float = 0.0
    entity_metrics: list[EntityMetrics] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def __str__(self) -> str:
        """Format results as a readable report."""
        lines = [
            f"\n{'=' * 60}",
            f"Benchmark Results: {self.dataset}",
            f"Config: {self.config_name}",
            f"{'=' * 60}",
            f"Samples: {self.total_samples}",
            f"Total Time: {self.total_time_seconds:.1f}s ({self.total_time_seconds/60:.1f} min)",
            f"Avg Time/Sample: {self.total_time_seconds/self.total_samples*1000:.1f}ms" if self.total_samples > 0 else "Avg Time/Sample: N/A",
            f"",
            f"Overall Metrics:",
            f"  Precision: {self.overall_precision:.4f}",
            f"  Recall:    {self.overall_recall:.4f}",
            f"  F1 Score:  {self.overall_f1:.4f}",
        ]

        if self.entity_metrics:
            lines.append("")
            lines.append("Per-Entity Metrics:")
            lines.append(f"  {'Entity':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>8}")
            lines.append(f"  {'-' * 60}")
            for em in sorted(self.entity_metrics, key=lambda x: x.support, reverse=True):
                lines.append(
                    f"  {em.entity_type:<20} {em.precision:>10.4f} {em.recall:>10.4f} "
                    f"{em.f1:>10.4f} {em.support:>8}"
                )

        if self.errors:
            lines.append("")
            lines.append(f"Errors ({len(self.errors)}):")
            for err in self.errors[:5]:  # Show first 5 errors
                lines.append(f"  - {err}")
            if len(self.errors) > 5:
                lines.append(f"  ... and {len(self.errors) - 5} more")

        lines.append(f"{'=' * 60}")
        return "\n".join(lines)
