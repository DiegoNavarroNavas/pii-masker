#!/usr/bin/env python3
"""
Benchmark candidate models on presidio-research generated datasets.

This script measures:
- model load time
- analysis latency (warm runs)
- detection counts
- exact and partial mention recall/precision/F1/F2 against a gold set

Usage:
    python tests/benchmark_transformer_models.py
    python tests/benchmark_transformer_models.py --dataset large --runs 2
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pii_masker import (  # noqa: E402
    SPACY_SMALL_MODELS,
    create_analyzer,
    detect_pii_with_local_multihead,
    load_local_multihead_runtime,
    resolve_local_multihead_checkpoint,
)

PRESIDIO_RESEARCH_ROOT = REPO_ROOT / "presidio-research"
DATA_DIR = PRESIDIO_RESEARCH_ROOT / "tests" / "data"
DATASET_BY_SIZE = {
    "small": DATA_DIR / "generated_small.json",
    "large": DATA_DIR / "generated_large.json",
}
BENCHMARK_ROOT = REPO_ROOT / "benchmarks"


@dataclass(frozen=True)
class ExpectedMention:
    text: str
    entity_type: str


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    language: str
    text: str
    expected: tuple[ExpectedMention, ...]


@dataclass(frozen=True)
class BenchmarkTarget:
    id: str
    engine: str
    model_name: str
    spacy_model: str | None = None
    transformer_model: str | None = None
    local_encoder_model: str | None = None


BENCHMARK_TRANSFORMER_MODELS: tuple[str, ...] = (
    "Babelscape/wikineural-multilingual-ner",
    "Davlan/xlm-roberta-large-ner-hrl",
    "dbmdz/bert-large-cased-finetuned-conll03-german",
    "Davlan/xlm-roberta-base-ner-hrl",
    "Jean-Baptiste/roberta-large-ner-english",
    "dslim/bert-base-NER",
)


def load_raw_rows(dataset_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Dataset JSON must be a list of objects")
    rows = [row for row in raw if isinstance(row, dict)]
    if len(rows) != len(raw):
        raise ValueError("Dataset contains non-object rows")
    return rows


def rows_to_cases(rows: list[dict[str, Any]], default_language: str = "en") -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for idx, row in enumerate(rows):
        text = row.get("full_text")
        if not isinstance(text, str) or not text.strip():
            continue
        spans = row.get("spans", [])
        expected_items: list[ExpectedMention] = []
        if isinstance(spans, list):
            for span in spans:
                if not isinstance(span, dict):
                    continue
                value = span.get("entity_value")
                etype = span.get("entity_type")
                if isinstance(value, str) and isinstance(etype, str) and value.strip() and etype.strip():
                    expected_items.append(ExpectedMention(value, etype))
        case_id = f"row_{idx}_template_{row.get('template_id', 'na')}"
        language = default_language
        metadata = row.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("language"), str):
            language = metadata["language"]
        cases.append(
            BenchmarkCase(
                case_id=case_id,
                language=language,
                text=text,
                expected=tuple(expected_items),
            )
        )
    return cases


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_partial_match(a: str, b: str) -> bool:
    na = normalize(a)
    nb = normalize(b)
    return bool(na and nb and (na in nb or nb in na))


def to_ascii_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")


def score_mentions(
    detections: list[dict[str, Any]],
    expected: tuple[ExpectedMention, ...],
) -> dict[str, float | int]:
    def f_beta(precision: float, recall: float, beta: float) -> float:
        beta_sq = beta * beta
        denom = beta_sq * precision + recall
        if denom == 0.0:
            return 0.0
        return (1 + beta_sq) * precision * recall / denom

    if not expected and not detections:
        return {
            "expected_count": 0,
            "detected_count": 0,
            "exact_matched_expected": 0,
            "partial_matched_expected": 0,
            "precision_exact": 1.0,
            "recall_exact": 1.0,
            "f1_exact": 1.0,
            "f2_exact": 1.0,
            "precision_partial": 1.0,
            "recall_partial": 1.0,
            "f1_partial": 1.0,
            "f2_partial": 1.0,
        }

    expected_count = len(expected)
    detected_count = len(detections)

    exact_expected_hits = 0
    partial_expected_hits = 0
    exact_detection_hits = 0
    partial_detection_hits = 0

    for mention in expected:
        exact_hit = any(
            normalize(det["text"]) == normalize(mention.text)
            and det["entity_type"] == mention.entity_type
            for det in detections
        )
        partial_hit = any(
            is_partial_match(det["text"], mention.text)
            and det["entity_type"] == mention.entity_type
            for det in detections
        )
        exact_expected_hits += int(exact_hit)
        partial_expected_hits += int(partial_hit)

    for det in detections:
        exact_hit = any(
            normalize(det["text"]) == normalize(mention.text)
            and det["entity_type"] == mention.entity_type
            for mention in expected
        )
        partial_hit = any(
            is_partial_match(det["text"], mention.text)
            and det["entity_type"] == mention.entity_type
            for mention in expected
        )
        exact_detection_hits += int(exact_hit)
        partial_detection_hits += int(partial_hit)

    precision_exact = (exact_detection_hits / detected_count) if detected_count else 0.0
    recall_exact = (exact_expected_hits / expected_count) if expected_count else 0.0
    f1_exact = f_beta(precision_exact, recall_exact, beta=1.0)
    f2_exact = f_beta(precision_exact, recall_exact, beta=2.0)

    precision_partial = (partial_detection_hits / detected_count) if detected_count else 0.0
    recall_partial = (partial_expected_hits / expected_count) if expected_count else 0.0
    f1_partial = f_beta(precision_partial, recall_partial, beta=1.0)
    f2_partial = f_beta(precision_partial, recall_partial, beta=2.0)

    return {
        "expected_count": expected_count,
        "detected_count": detected_count,
        "exact_matched_expected": exact_expected_hits,
        "partial_matched_expected": partial_expected_hits,
        "precision_exact": precision_exact,
        "recall_exact": recall_exact,
        "f1_exact": f1_exact,
        "f2_exact": f2_exact,
        "precision_partial": precision_partial,
        "recall_partial": recall_partial,
        "f1_partial": f1_partial,
        "f2_partial": f2_partial,
    }


def run_case(
    *,
    target: BenchmarkTarget,
    case: BenchmarkCase,
    runs: int,
    runtime: Any,
    load_seconds: float,
) -> dict[str, Any]:
    spacy_model = target.spacy_model or SPACY_SMALL_MODELS.get(case.language, SPACY_SMALL_MODELS["en"])

    latencies: list[float] = []
    detections: list[dict[str, Any]] = []

    for idx in range(runs):
        analyze_start = time.perf_counter()
        if target.engine == "transformers":
            results = runtime.analyze(text=case.text, language=case.language)
        else:
            results = detect_pii_with_local_multihead(
                text=case.text,
                checkpoint_path=runtime,
                encoder_model=target.local_encoder_model,
            )
        latencies.append(time.perf_counter() - analyze_start)

        if idx == runs - 1:
            seen = set()
            if target.engine == "transformers":
                for result in sorted(results, key=lambda item: (item.start, item.end, item.entity_type)):
                    key = (result.start, result.end, result.entity_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    detections.append(
                        {
                            "start": result.start,
                            "end": result.end,
                            "entity_type": result.entity_type,
                            "score": float(result.score),
                            "text": case.text[result.start : result.end],
                        }
                    )
            else:
                for result in sorted(results, key=lambda item: (item["start"], item["end"], item["entity_type"])):
                    key = (result["start"], result["end"], result["entity_type"])
                    if key in seen:
                        continue
                    seen.add(key)
                    detections.append(
                        {
                            "start": result["start"],
                            "end": result["end"],
                            "entity_type": result["entity_type"],
                            "score": float(result["score"]),
                            "text": case.text[result["start"] : result["end"]],
                        }
                    )

    scoring = score_mentions(detections=detections, expected=case.expected)
    entity_counts: dict[str, int] = {}
    for det in detections:
        entity_counts[det["entity_type"]] = entity_counts.get(det["entity_type"], 0) + 1

    return {
        "case_id": case.case_id,
        "language": case.language,
        "engine": target.engine,
        "model_id": target.id,
        "spacy_model": spacy_model,
        "load_seconds": load_seconds,
        "latency_seconds": {
            "runs": runs,
            "first_run": latencies[0],
            "mean": statistics.fmean(latencies),
            "median": statistics.median(latencies),
            "min": min(latencies),
            "max": max(latencies),
        },
        "score": scoring,
        "entity_counts": entity_counts,
        "detections": detections,
    }


def aggregate_model(model_results: list[dict[str, Any]]) -> dict[str, float]:
    def mean_of(path: tuple[str, ...]) -> float:
        values: list[float] = []
        for case_result in model_results:
            value: Any = case_result
            for key in path:
                value = value[key]
            values.append(float(value))
        return statistics.fmean(values) if values else 0.0

    return {
        "avg_load_seconds": mean_of(("load_seconds",)),
        "avg_latency_mean_seconds": mean_of(("latency_seconds", "mean")),
        "avg_precision_exact": mean_of(("score", "precision_exact")),
        "avg_recall_exact": mean_of(("score", "recall_exact")),
        "avg_f1_exact": mean_of(("score", "f1_exact")),
        "avg_f2_exact": mean_of(("score", "f2_exact")),
        "avg_precision_partial": mean_of(("score", "precision_partial")),
        "avg_recall_partial": mean_of(("score", "recall_partial")),
        "avg_f1_partial": mean_of(("score", "f1_partial")),
        "avg_f2_partial": mean_of(("score", "f2_partial")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark models on presidio-research generated datasets.")
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of analyze runs per case/model (default: 3).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output JSON file path (default: benchmarks/results/transformers/generated/<dataset>.json).",
    )
    parser.add_argument(
        "--dataset",
        choices=["small", "large"],
        default="small",
        help="Dataset preset. small=generated_small.json, large=generated_large.json.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of rows/cases after split.",
    )
    parser.add_argument(
        "--default-language",
        type=str,
        default="en",
        help="Default language when dataset rows do not include metadata.language.",
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="*",
        default=list(BENCHMARK_TRANSFORMER_MODELS),
        help="Optional model override list.",
    )
    parser.add_argument(
        "--local-multihead-checkpoint",
        type=str,
        default=None,
        help="Optional local multihead .pt checkpoint path to include in the benchmark.",
    )
    parser.add_argument(
        "--local-multihead-encoder-model",
        type=str,
        default=None,
        help="Optional encoder/tokenizer id for local_multihead benchmark target.",
    )
    parser.add_argument(
        "--generate-dashboard",
        action="store_true",
        help="Generate HTML error dashboard after benchmark JSON is written.",
    )
    parser.add_argument(
        "--dashboard-output",
        type=str,
        default=str(BENCHMARK_ROOT / "error" / "dashboard.html"),
        help="Output path for HTML dashboard when --generate-dashboard is set.",
    )
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be >= 1")
    dataset_path = DATASET_BY_SIZE[args.dataset]
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    out_path = (
        Path(args.out)
        if args.out
        else BENCHMARK_ROOT / "results" / "transformers" / "generated" / f"{args.dataset}.json"
    )

    rows = load_raw_rows(dataset_path)
    if args.limit is not None:
        rows = rows[: args.limit]
    benchmark_cases = rows_to_cases(rows, default_language=args.default_language)

    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    full_results: dict[str, Any] = {
        "started_at_utc": started_at,
        "dataset_path": str(dataset_path),
        "dataset": args.dataset,
        "runs_per_case": args.runs,
        "cases": [
            {
                "case_id": case.case_id,
                "language": case.language,
                "expected": [
                    {"text": mention.text, "entity_type": mention.entity_type}
                    for mention in case.expected
                ],
            }
            for case in benchmark_cases
        ],
        "models": {},
    }

    benchmark_targets: list[BenchmarkTarget] = [
        BenchmarkTarget(
            id=model_name,
            engine="transformers",
            model_name=model_name,
            transformer_model=model_name,
        )
        for model_name in args.models
    ]
    if args.local_multihead_checkpoint:
        benchmark_targets.append(
            BenchmarkTarget(
                id=f"local_multihead:{args.local_multihead_checkpoint}",
                engine="local_multihead",
                model_name=args.local_multihead_checkpoint,
                local_encoder_model=args.local_multihead_encoder_model,
            )
        )

    for target in benchmark_targets:
        print(f"[benchmark] target={target.id} engine={target.engine}", flush=True)
        per_case: list[dict[str, Any]] = []
        model_error: str | None = None
        runtime_by_language: dict[str, Any] = {}
        load_seconds_by_language: dict[str, float] = {}
        checkpoint_runtime: Any | None = None
        checkpoint_load_seconds = 0.0

        if target.engine == "local_multihead":
            checkpoint_path = resolve_local_multihead_checkpoint(target.model_name)
            load_start = time.perf_counter()
            load_local_multihead_runtime(
                checkpoint_path=checkpoint_path,
                encoder_model=target.local_encoder_model,
            )
            checkpoint_load_seconds = time.perf_counter() - load_start
            checkpoint_runtime = checkpoint_path

        for case in benchmark_cases:
            print(f"  - case={case.case_id} language={case.language}", flush=True)
            try:
                if target.engine == "transformers":
                    runtime = runtime_by_language.get(case.language)
                    case_load_seconds = load_seconds_by_language.get(case.language, 0.0)
                    if runtime is None:
                        spacy_model = target.spacy_model or SPACY_SMALL_MODELS.get(case.language, SPACY_SMALL_MODELS["en"])
                        load_start = time.perf_counter()
                        load_stderr = io.StringIO()
                        try:
                            with contextlib.redirect_stderr(load_stderr):
                                runtime = create_analyzer(
                                    engine="transformers",
                                    model=None,
                                    spacy_model=spacy_model,
                                    transformer_model=target.transformer_model or target.model_name,
                                    ner_config=None,
                                    language=case.language,
                                    recognizers_yaml=None,
                                    recognizers_json=None,
                                )
                        except SystemExit as exc:
                            detail = load_stderr.getvalue().strip()
                            detail_ascii = to_ascii_safe(detail)
                            raise RuntimeError(
                                f"create_analyzer exited code={exc.code}; stderr_tail={detail_ascii[-400:]}"
                            ) from exc
                        case_load_seconds = time.perf_counter() - load_start
                        runtime_by_language[case.language] = runtime
                        load_seconds_by_language[case.language] = case_load_seconds
                else:
                    runtime = checkpoint_runtime
                    case_load_seconds = checkpoint_load_seconds

                case_result = run_case(
                    target=target,
                    case=case,
                    runs=args.runs,
                    runtime=runtime,
                    load_seconds=case_load_seconds,
                )
                per_case.append(case_result)
                print(
                    "    load={:.2f}s mean_latency={:.2f}s exact_f1={:.3f} exact_f2={:.3f} partial_f1={:.3f} partial_f2={:.3f}".format(
                        case_result["load_seconds"],
                        case_result["latency_seconds"]["mean"],
                        case_result["score"]["f1_exact"],
                        case_result["score"]["f2_exact"],
                        case_result["score"]["f1_partial"],
                        case_result["score"]["f2_partial"],
                    ),
                    flush=True,
                )
            except Exception as exc:
                model_error = str(exc)
                print(f"    ERROR: {model_error}", flush=True)
                break

        if model_error:
            full_results["models"][target.id] = {
                "ok": False,
                "error": model_error,
                "results_by_case": per_case,
            }
            continue

        summary = aggregate_model(per_case)
        full_results["models"][target.id] = {
            "ok": True,
            "engine": target.engine,
            "summary": summary,
            "results_by_case": per_case,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(full_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[benchmark] wrote {out_path}")

    if args.generate_dashboard:
        dashboard_script = REPO_ROOT / "tests" / "generate_benchmark_error_dashboard.py"
        dashboard_output = Path(args.dashboard_output)
        dashboard_output.parent.mkdir(parents=True, exist_ok=True)
        if not dashboard_script.exists():
            raise FileNotFoundError(f"Dashboard generator script not found: {dashboard_script}")
        cmd = [
            sys.executable,
            str(dashboard_script),
            "--input",
            str(out_path),
            "--output",
            str(dashboard_output),
        ]
        subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)
        print(f"[benchmark] wrote dashboard {dashboard_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
