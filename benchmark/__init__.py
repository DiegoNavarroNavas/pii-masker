"""PII Masker Benchmark Module.

Benchmark pii_masker against standard datasets using presidio-evaluator.
"""

__all__ = ["run_benchmark", "BenchmarkResult"]

from benchmark.results import BenchmarkResult
from benchmark.evaluators.presidio_eval import run_benchmark
