"""Presidio evaluator wrapper for benchmarking PII detection."""

import sys
from collections import defaultdict

from benchmark.entity_normalizer import normalize_entities
from benchmark.loaders.base import BenchmarkSample
from benchmark.results import BenchmarkResult, EntityMetrics


def get_conflict_strategy(strategy_name: str):
    """Convert strategy name to ConflictResolutionStrategy enum.

    Args:
        strategy_name: "remove_intersections", "merge_similar_or_contained", or "none"

    Returns:
        ConflictResolutionStrategy enum or None for "none"
    """
    from presidio_anonymizer.entities import ConflictResolutionStrategy

    strategies = {
        "remove_intersections": ConflictResolutionStrategy.REMOVE_INTERSECTIONS,
        "merge_similar_or_contained": ConflictResolutionStrategy.MERGE_SIMILAR_OR_CONTAINED,
        "none": None,
    }
    return strategies.get(strategy_name.lower(), ConflictResolutionStrategy.REMOVE_INTERSECTIONS)


def resolve_conflicts_with_anonymizer(
    text: str,
    results: list,
    strategy,
) -> list[dict]:
    """Use AnonymizerEngine to resolve overlapping entities.

    The anonymizer already has conflict resolution logic. We use a 'keep'
    operator to get conflict resolution without modifying text.

    Args:
        text: Original text (needed for anonymizer)
        results: List of RecognizerResult from analyzer
        strategy: ConflictResolutionStrategy enum or None to skip resolution

    Returns:
        List of resolved entities with (entity_type, start, end)
    """
    if not results:
        return []

    # If strategy is None, return results without conflict resolution
    if strategy is None:
        return [
            {"entity_type": r.entity_type, "start": r.start, "end": r.end}
            for r in results
        ]

    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import (
        OperatorConfig,
        RecognizerResult as AnonRecognizerResult,
    )

    # Convert analyzer results to anonymizer format
    anon_results = [
        AnonRecognizerResult(
            entity_type=r.entity_type,
            start=r.start,
            end=r.end,
            score=r.score,
        )
        for r in results
    ]

    # Use anonymizer with 'keep' operator to resolve conflicts
    engine = AnonymizerEngine()
    result = engine.anonymize(
        text=text,
        analyzer_results=anon_results,
        operators={"DEFAULT": OperatorConfig("keep", {})},
        conflict_resolution=strategy,
    )

    # Return resolved entities
    return [
        {"entity_type": item.entity_type, "start": item.start, "end": item.end}
        for item in result.items
    ]


def run_benchmark(
    config_path: str,
    samples: list[BenchmarkSample],
    dataset_name: str,
    evaluation_mode: str = "coarse",
) -> BenchmarkResult:
    """Run benchmark with a single analyzer instance.

    Args:
        config_path: Path to config file or preset name.
        samples: List of benchmark samples to evaluate.
        dataset_name: Name of the dataset being evaluated.
        evaluation_mode: "coarse" normalizes entity types, "granular" uses exact matching.

    Returns:
        BenchmarkResult with metrics.
    """
    # Import from pii_masker (assumes pii_masker is installed/available)
    try:
        from pii_masker import create_analyzer, load_config
    except ImportError:
        # Try relative import for development
        import importlib.util
        import pathlib
        spec = importlib.util.spec_from_file_location(
            "pii_masker",
            pathlib.Path(__file__).parent.parent.parent / "pii_masker.py"
        )
        pii_masker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pii_masker)
        create_analyzer = pii_masker.create_analyzer
        load_config = pii_masker.load_config

    print(f"Loading config: {config_path}", file=sys.stderr)
    config = load_config(config_path)

    # Create analyzer once (NLP engine loads once)
    analyzer = create_analyzer(config)
    lang = config.get("language", "en")

    # Get entity type mapping if configured
    entity_type_mapping = config.get("entity_type_mapping", {})

    print(f"Running benchmark on {len(samples)} samples...", file=sys.stderr)

    all_predictions: list[list[dict]] = []
    all_ground_truth: list[list[dict]] = []
    errors: list[str] = []

    for i, sample in enumerate(samples):
        try:
            # Get predictions from analyzer
            results = analyzer.analyze(
                sample.text,
                language=lang,
                score_threshold=config.get("score_threshold"),
            )

            # Apply entity type mapping if configured
            if entity_type_mapping:
                for r in results:
                    if r.entity_type in entity_type_mapping:
                        r.entity_type = entity_type_mapping[r.entity_type]

            # Apply conflict resolution using anonymizer
            conflict_strategy_name = config.get("conflict_resolution", "remove_intersections")
            conflict_strategy = get_conflict_strategy(conflict_strategy_name)
            predictions = resolve_conflicts_with_anonymizer(
                sample.text, results, conflict_strategy
            )

            # Normalize to coarse types if enabled
            if evaluation_mode == "coarse":
                predictions = normalize_entities(predictions)
                ground_truth = normalize_entities(sample.ground_truth)
            else:
                ground_truth = sample.ground_truth

            all_predictions.append(predictions)
            all_ground_truth.append(ground_truth)
        except Exception as e:
            errors.append(f"Sample {i}: {str(e)}")
            all_predictions.append([])
            all_ground_truth.append(sample.ground_truth)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(samples)} samples...", file=sys.stderr)

    print("Computing metrics...", file=sys.stderr)
    return _compute_metrics(
        predictions=all_predictions,
        ground_truth=all_ground_truth,
        dataset_name=dataset_name,
        config_name=config_path,
        total_samples=len(samples),
        errors=errors,
    )


def _compute_metrics(
    predictions: list[list[dict]],
    ground_truth: list[list[dict]],
    dataset_name: str,
    config_name: str,
    total_samples: int,
    errors: list[str],
) -> BenchmarkResult:
    """Compute precision, recall, and F1 metrics.

    Uses exact span matching for evaluation.
    """
    # Track true positives, false positives, false negatives per entity type
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)

    for preds, truths in zip(predictions, ground_truth, strict=True):
        # Convert to sets of (type, start, end) tuples for comparison
        pred_set = {(p["entity_type"], p["start"], p["end"]) for p in preds}
        truth_set = {(t["entity_type"], t["start"], t["end"]) for t in truths}

        # True positives: predictions that match ground truth
        for pred in pred_set:
            if pred in truth_set:
                tp[pred[0]] += 1
            else:
                fp[pred[0]] += 1

        # False negatives: ground truth not in predictions
        for truth in truth_set:
            if truth not in pred_set:
                fn[truth[0]] += 1

    # Compute per-entity metrics
    entity_metrics: list[EntityMetrics] = []
    all_entity_types = set(tp.keys()) | set(fp.keys()) | set(fn.keys())

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for entity_type in all_entity_types:
        e_tp = tp[entity_type]
        e_fp = fp[entity_type]
        e_fn = fn[entity_type]

        total_tp += e_tp
        total_fp += e_fp
        total_fn += e_fn

        precision = e_tp / (e_tp + e_fp) if (e_tp + e_fp) > 0 else 0.0
        recall = e_tp / (e_tp + e_fn) if (e_tp + e_fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        support = e_tp + e_fn  # Total ground truth instances

        entity_metrics.append(EntityMetrics(
            entity_type=entity_type,
            precision=precision,
            recall=recall,
            f1=f1,
            support=support,
        ))

    # Compute overall metrics (micro-averaged)
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = (
        2 * overall_precision * overall_recall / (overall_precision + overall_recall)
        if (overall_precision + overall_recall) > 0
        else 0.0
    )

    return BenchmarkResult(
        dataset=dataset_name,
        config_name=config_name,
        total_samples=total_samples,
        overall_precision=overall_precision,
        overall_recall=overall_recall,
        overall_f1=overall_f1,
        entity_metrics=entity_metrics,
        errors=errors,
    )
