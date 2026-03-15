#!/usr/bin/env python3
"""
Score transformer NER models against presidio-research labeled test data.

This uses:
- Dataset preset selected by --dataset (small/large)
- Evaluator: presidio_evaluator.Evaluator (token-level metrics)
- Model runtime path: this repo's create_analyzer(engine="transformers", ...)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESIDIO_RESEARCH_ROOT = REPO_ROOT / "presidio-research"
DATA_DIR = PRESIDIO_RESEARCH_ROOT / "tests" / "data"
DATASET_BY_SIZE = {
    "small": DATA_DIR / "generated_small.json",
    "large": DATA_DIR / "generated_large.json",
}
BENCHMARK_ROOT = REPO_ROOT / "benchmarks"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(PRESIDIO_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(PRESIDIO_RESEARCH_ROOT))

from pii_masker import create_analyzer  # noqa: E402
from presidio_evaluator import InputSample  # noqa: E402
from presidio_evaluator.evaluation import SpanEvaluator  # noqa: E402
from presidio_evaluator.models import PresidioAnalyzerWrapper  # noqa: E402

DEFAULT_MODELS: tuple[str, ...] = (
    "Babelscape/wikineural-multilingual-ner",
    "Davlan/xlm-roberta-large-ner-hrl",
    "dbmdz/bert-large-cased-finetuned-conll03-german",
    "Davlan/xlm-roberta-base-ner-hrl",
    "Jean-Baptiste/roberta-large-ner-english",
    "dslim/bert-base-NER",
)
DEFAULT_AGGREGATION_STRATEGIES: tuple[str, ...] = ("default",)

def load_aligned_dataset(dataset_path: Path, limit: int | None = None) -> list[InputSample]:
    dataset = InputSample.read_dataset_json(dataset_path, length=limit)
    aligned = SpanEvaluator.align_entity_types(
        dataset,
        entities_mapping=PresidioAnalyzerWrapper.presidio_entities_map,
        allow_missing_mappings=True,
    )
    return aligned


def score_model(
    model_name: str,
    dataset: list[InputSample],
    aggregation_strategy: str = "default",
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        ner_config = None
        if aggregation_strategy != "default":
            ner_config = {"aggregation_strategy": aggregation_strategy}
        analyzer = create_analyzer(
            engine="transformers",
            model=None,
            spacy_model="en_core_web_sm",
            transformer_model=model_name,
            ner_config=ner_config,
            language="en",
            recognizers_yaml=None,
            recognizers_json=None,
        )
    except SystemExit as exc:
        raise RuntimeError(f"create_analyzer exited with code={exc.code}") from exc
    load_seconds = time.perf_counter() - started

    eval_start = time.perf_counter()
    evaluator = SpanEvaluator(model=analyzer)
    evaluation_results = evaluator.evaluate_all(dataset)
    # Presidio evaluator defaults to beta=2 (recall-weighted). We also compute beta=1 (F1).
    score_f2 = evaluator.calculate_score(evaluation_results, beta=2.0)
    score_f1 = evaluator.calculate_score(evaluation_results, beta=1.0)
    eval_seconds = time.perf_counter() - eval_start

    top_entities = sorted(
        score_f1.entity_recall_dict.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    return {
        "ok": True,
        "aggregation_strategy": aggregation_strategy,
        "load_seconds": load_seconds,
        "eval_seconds": eval_seconds,
        "pii_precision": score_f1.pii_precision,
        "pii_recall": score_f1.pii_recall,
        "pii_f1": score_f1.pii_f,
        "pii_f2": score_f2.pii_f,
        # Keep legacy key for compatibility with existing output consumers.
        "pii_f": score_f2.pii_f,
        "entity_recall_top10": top_entities,
        "entity_precision": score_f1.entity_precision_dict,
        "n_tokens_scored": score_f1.n,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score models on presidio-research generated datasets.")
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
        help="Optional number of samples to evaluate.",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=list(DEFAULT_MODELS),
        help="Optional list of Hugging Face model ids.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output JSON file path (default: benchmarks/results/presidio/research/generated/<dataset>.json).",
    )
    parser.add_argument(
        "--aggregation-strategies",
        nargs="*",
        default=list(DEFAULT_AGGREGATION_STRATEGIES),
        help=(
            "Aggregation strategies to test. "
            "Use: default simple first average max none"
        ),
    )
    args = parser.parse_args()

    dataset_path = DATASET_BY_SIZE[args.dataset]
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    out_path = (
        Path(args.out)
        if args.out
        else BENCHMARK_ROOT / "results" / "presidio" / "research" / "generated" / f"{args.dataset}.json"
    )
    dataset = load_aligned_dataset(dataset_path, limit=args.limit)

    payload: dict[str, Any] = {
        "dataset_path": str(dataset_path),
        "dataset": args.dataset,
        "sample_count": len(dataset),
        "models": {},
    }

    for model_name in args.models:
        payload["models"][model_name] = {}
        print(f"[score] model={model_name}", flush=True)
        for strategy in args.aggregation_strategies:
            print(f"  - aggregation_strategy={strategy}", flush=True)
            try:
                result = score_model(
                    model_name=model_name,
                    dataset=dataset,
                    aggregation_strategy=strategy,
                )
                payload["models"][model_name][strategy] = result
                print(
                    "    pii_f1={:.4f} pii_f2={:.4f} precision={:.4f} recall={:.4f} load={:.2f}s eval={:.2f}s".format(
                        result["pii_f1"],
                        result["pii_f2"],
                        result["pii_precision"],
                        result["pii_recall"],
                        result["load_seconds"],
                        result["eval_seconds"],
                    ),
                    flush=True,
                )
            except Exception as exc:
                payload["models"][model_name][strategy] = {
                    "ok": False,
                    "aggregation_strategy": strategy,
                    "error": str(exc),
                }
                print(f"    ERROR: {exc}", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[score] wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
