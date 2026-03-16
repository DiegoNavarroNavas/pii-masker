#!/usr/bin/env python3
"""PII Masker - Anonymize and deanonymize text with unique placeholders."""
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TORCH_DEVICE_BACKEND_AUTOLOAD", "0")

import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_KEY_FILE = "pii.key"
DEFAULT_CONFIG_FILE = "pii_masker.yaml"

SPACY_MODELS = {
    "en": "en_core_web_lg", "es": "es_core_news_lg", "fr": "fr_core_news_lg",
    "de": "de_core_news_lg", "it": "it_core_news_lg", "pt": "pt_core_news_lg",
    "zh": "zh_core_web_lg", "ja": "ja_core_news_lg", "ko": "ko_core_news_lg",
}
SPACY_SMALL = {
    "en": "en_core_web_sm", "es": "es_core_news_sm", "fr": "fr_core_news_sm",
    "de": "de_core_news_sm", "it": "it_core_news_sm", "pt": "pt_core_news_sm",
    "zh": "zh_core_web_sm", "ja": "ja_core_news_sm", "ko": "ko_core_news_sm",
}
DEFAULT_TRANSFORMER = "FacebookAI/xlm-roberta-large-finetuned-conll03-english"
DEFAULT_LOCAL_MULTIHEAD_MODEL = "local_models/multihead_model.pt"
DEFAULT_LOCAL_ENCODER_MODEL = "answerdotai/ModernBERT-base"

# Exit codes for JSON mode
EXIT_SUCCESS = 0
EXIT_INVALID_REQUEST = 2
EXIT_KEY_FILE_ERROR = 3
EXIT_INPUT_ERROR = 4
EXIT_PROCESSING_ERROR = 5
EXIT_DEPENDENCY_ERROR = 6


def status(msg: str):
    """Print status message, return lambda to mark complete."""
    print(f"  {msg}...", file=sys.stderr, end="", flush=True)
    return lambda: print(" done", file=sys.stderr)


def load_config(name: str | None) -> dict:
    """Load config from file path."""
    if not name:
        local = Path.cwd() / DEFAULT_CONFIG_FILE
        if local.exists():
            name = str(local)
        else:
            sys.exit(f"Error: No config specified. Use -c CONFIG_PATH or create {DEFAULT_CONFIG_FILE}")
    path = Path(name)
    if not path.exists():
        sys.exit(f"Error: Config file not found: {path}")
    try:
        return yaml.safe_load(open(path)) or {}
    except yaml.YAMLError as e:
        sys.exit(f"Error: Invalid YAML in config: {e}")


def create_analyzer(config: dict):
    """Create analyzer from config."""
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    engine = config.get("engine", "spacy").lower()
    lang = config.get("language", "en")

    # Local multihead bypasses Presidio analyzer entirely
    if engine == "local_multihead":
        return None

    nlp_config = config.get("nlp_configuration")

    done = status("Loading NLP engine")
    try:
        nlp_engine = (
            NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
            if nlp_config
            else _build_nlp_engine_simple(config)
        )
        nlp_engine.load()
    except ImportError as e:
        engine = config.get("engine", "spacy")
        sys.exit(f"Error: Missing dependencies for '{engine}' engine: {e}\nInstall with: pip install presidio-analyzer[{engine}]")
    done()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(languages=[lang], nlp_engine=nlp_engine)

    # Load custom recognizers from YAML file
    if yaml_path := config.get("recognizers_yaml"):
        done = status(f"Loading recognizers from {yaml_path}")
        try:
            registry.add_recognizers_from_yaml(yaml_path)
        except Exception as e:
            sys.exit(f"Error loading recognizers YAML: {e}")
        done()

    # Load inline recognizers (GLiNER, patterns)
    # Filter out string references (e.g., "spacy") - already loaded via load_predefined_recognizers
    inline_recognizers = [r for r in config.get("recognizers", []) if isinstance(r, dict)]
    if inline_recognizers:
        done = status(f"Loading {len(inline_recognizers)} custom recognizer(s)")
        for rec in inline_recognizers:
            if (r := _create_recognizer(rec, lang)):
                registry.add_recognizer(r)
        done()

    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)


def _build_nlp_engine_simple(config: dict):
    """Build NLP engine from simple config."""
    engine = config.get("engine", "spacy").lower()
    lang = config.get("language", "en")
    model = config.get("model")

    if engine == "local_multihead":
        # Local multihead bypasses Presidio NLP engine entirely
        return None
    if engine == "spacy":
        from presidio_analyzer.nlp_engine import SpacyNlpEngine
        model_name = model or SPACY_MODELS.get(lang, SPACY_MODELS["en"])
        return SpacyNlpEngine(models=[{"lang_code": lang, "model_name": model_name}])
    elif engine == "stanza":
        from presidio_analyzer.nlp_engine import StanzaNlpEngine
        return StanzaNlpEngine(models=[{"lang_code": lang, "model_name": model or lang}])
    elif engine == "transformers":
        from presidio_analyzer.nlp_engine import TransformersNlpEngine
        spacy_model = SPACY_SMALL.get(lang, SPACY_SMALL["en"])
        transformer = model or DEFAULT_TRANSFORMER
        if ":" in transformer:
            spacy_model, transformer = transformer.split(":", 1)
        return TransformersNlpEngine(
            models=[{"lang_code": lang, "model_name": {"spacy": spacy_model, "transformers": transformer}}]
        )
    raise ValueError(f"Unknown engine: {engine}. Choose: spacy, stanza, transformers, local_multihead")


def _create_recognizer(rec_config: dict, lang: str):
    """Create recognizer from inline config."""
    from presidio_analyzer import PatternRecognizer

    name = rec_config.get("name", "")
    if name == "GLiNERRecognizer":
        from presidio_analyzer.predefined_recognizers import GLiNERRecognizer
        conf = {**rec_config, "supported_language": rec_config.get("supported_language", lang)}

        # Support both 'labels' (List[str]) and 'entity_mapping' (Dict[str, str]) formats
        # If 'labels' is provided, convert to entity_mapping where each label maps to itself
        if "labels" in conf and "entity_mapping" not in conf:
            labels = conf.pop("labels")
            conf["entity_mapping"] = {label: label for label in labels}

        return GLiNERRecognizer(**{k: v for k, v in conf.items() if k != "name"})
    if rec_config.get("patterns") or rec_config.get("deny_list"):
        return PatternRecognizer.from_dict(rec_config)

    return None


def anonymize(text: str, encryption_key: str, config: dict) -> tuple[str, dict]:
    """Anonymize text with unique encrypted placeholders."""
    from presidio_analyzer import RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import ConflictResolutionStrategy, OperatorConfig

    lang = config.get("language", "en")
    engine = config.get("engine", "spacy").lower()

    # Handle local_multihead engine separately (bypasses Presidio)
    if engine == "local_multihead":
        from pii_masker_local import detect_pii_with_local_multihead, resolve_local_multihead_checkpoint

        checkpoint_path = resolve_local_multihead_checkpoint(config.get("model", DEFAULT_LOCAL_MULTIHEAD_MODEL))
        done = status("Analyzing text with local multihead model")
        detections = detect_pii_with_local_multihead(
            text, checkpoint_path, config.get("local_encoder_model", DEFAULT_LOCAL_ENCODER_MODEL)
        )
        done()

        if not detections:
            print("No PII found", file=sys.stderr)
            return text, {}

        results = [
            RecognizerResult(d["entity_type"], d["start"], d["end"], d["score"])
            for d in detections
        ]
    else:
        analyzer = create_analyzer(config)

        done = status("Analyzing text for PII")
        results = analyzer.analyze(
            text=text,
            language=lang,
            score_threshold=config.get("score_threshold"),
        )
        done()

    if not results:
        print("No PII found", file=sys.stderr)
        return text, {}

    # Get conflict resolution strategy from config
    strategy_name = config.get("conflict_resolution", "remove_intersections")
    strategy_map = {
        "remove_intersections": ConflictResolutionStrategy.REMOVE_INTERSECTIONS,
        "merge_similar_or_contained": ConflictResolutionStrategy.MERGE_SIMILAR_OR_CONTAINED,
    }
    conflict_strategy = strategy_map.get(strategy_name.lower(), ConflictResolutionStrategy.REMOVE_INTERSECTIONS)

    # Resolve overlapping detections: when two spans overlap, keep the one with the
    # highest score (ties broken by longest span).  Without this, applying both
    # replacements back-to-front corrupts the text because the second replacement
    # slices into already-modified characters left by the first.
    def _resolve_overlaps(raw_results):
        candidates = sorted(raw_results, key=lambda r: (r.score, r.end - r.start), reverse=True)
        kept = []
        for candidate in candidates:
            if not any(candidate.start < k.end and candidate.end > k.start for k in kept):
                kept.append(candidate)
        return sorted(kept, key=lambda r: r.start)

    sorted_results = _resolve_overlaps(results)

    # Build placeholder mapping with encrypted values
    counters: dict[str, int] = {}
    value_to_idx: dict[tuple[str, str], int] = {}
    mapping: dict[str, tuple[str, str]] = {}
    anonymizer = AnonymizerEngine()

    def get_placeholder(val: str, entity: str) -> str:
        cache_key = (entity, val)
        if cache_key not in value_to_idx:
            counters[entity] = counters.get(entity, 0) + 1
            value_to_idx[cache_key] = counters[entity]
            encrypted = anonymizer.anonymize(
                text=val,
                analyzer_results=[RecognizerResult(entity, 0, len(val), 0.9)],
                operators={"DEFAULT": OperatorConfig("encrypt", {"key": encryption_key})},
            ).text
            mapping[f"<{entity}_{counters[entity]}>"] = (entity, encrypted)
        return f"<{entity}_{value_to_idx[cache_key]}>"

    # Build operators for each entity type
    operators = {
        et: OperatorConfig("custom", {"lambda": lambda v, e=et: get_placeholder(v, e)})
        for et in {r.entity_type for r in sorted_results}
    }

    done = status(f"Anonymizing {len(sorted_results)} entity occurrences")
    result = anonymizer.anonymize(
        text=text,
        analyzer_results=sorted_results,
        operators=operators,
        conflict_resolution=conflict_strategy,
    )
    done()

    return result.text, mapping


def deanonymize(text: str, mapping: dict, encryption_key: str) -> str:
    """Restore anonymized text."""
    from presidio_anonymizer import DeanonymizeEngine
    from presidio_anonymizer.entities import OperatorConfig, OperatorResult

    engine = DeanonymizeEngine()
    done = status(f"Decrypting {len(mapping)} entities")
    for placeholder, (entity, encrypted) in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
        decrypted = engine.deanonymize(
            text=encrypted,
            entities=[OperatorResult(0, len(encrypted), entity)],
            operators={"DEFAULT": OperatorConfig("decrypt", {"key": encryption_key})},
        ).text
        text = text.replace(placeholder, decrypted)
    done()
    return text


def save_mapping(mapping: dict, path: Path, language: str) -> None:
    """Save mapping with metadata."""
    data = {
        "version": "1.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "mappings": {k: {"entity_type": et, "encrypted": enc} for k, (et, enc) in mapping.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_mapping(path: Path) -> dict:
    """Load mapping from JSON file."""
    if not path.exists():
        sys.exit(f"Error: Mapping file not found: {path}")
    data = json.loads(path.read_text())
    return {k: (v["entity_type"], v["encrypted"]) for k, v in data["mappings"].items()}


def emit_json(payload: dict) -> None:
    """Write JSON payload to stdout (for JSON mode)."""
    print(json.dumps(payload, ensure_ascii=False))


def run_json_mode(config: dict) -> int:
    """
    Machine-readable mode for programmatic integrations.

    Reads one JSON document from stdin and writes one JSON document to stdout.
    Returns exit code (0-6).
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            emit_json({
                "ok": False,
                "error": {"code": "EMPTY_REQUEST", "message": "No JSON payload received on stdin."},
            })
            return EXIT_INVALID_REQUEST
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        emit_json({
            "ok": False,
            "error": {"code": "INVALID_JSON", "message": f"Failed to parse request JSON: {e}"},
        })
        return EXIT_INVALID_REQUEST

    action = payload.get("action", "anonymize")
    if action not in {"anonymize", "deanonymize"}:
        emit_json({
            "ok": False,
            "error": {"code": "INVALID_ACTION", "message": "action must be 'anonymize' or 'deanonymize'."},
        })
        return EXIT_INVALID_REQUEST

    # Get key file from payload or config
    key_file = payload.get("key_file") or config.get("key_file", DEFAULT_KEY_FILE)
    if not key_file:
        emit_json({
            "ok": False,
            "error": {"code": "MISSING_KEY_FILE", "message": "key_file is required."},
        })
        return EXIT_INVALID_REQUEST

    try:
        key_path = Path(key_file)
        if not key_path.exists():
            raise FileNotFoundError(f"Key file not found: {key_path}")
        encryption_key = key_path.read_text().strip()
    except FileNotFoundError as e:
        emit_json({
            "ok": False,
            "error": {"code": "KEY_FILE_NOT_FOUND", "message": str(e)},
        })
        return EXIT_KEY_FILE_ERROR
    except Exception as e:
        emit_json({
            "ok": False,
            "error": {"code": "KEY_FILE_READ_FAILED", "message": str(e)},
        })
        return EXIT_KEY_FILE_ERROR

    if action == "anonymize":
        text = payload.get("text")
        if not isinstance(text, str):
            emit_json({
                "ok": False,
                "error": {"code": "INVALID_INPUT_TEXT", "message": "text must be a string for anonymize action."},
            })
            return EXIT_INPUT_ERROR

        # Build config from payload
        anon_config = {
            "language": payload.get("language", config.get("language", "en")),
            "engine": payload.get("engine", config.get("engine", "spacy")),
            "model": payload.get("model", config.get("model")),
            "local_encoder_model": payload.get("local_encoder_model", config.get("local_encoder_model")),
            "score_threshold": payload.get("score_threshold", config.get("score_threshold")),
        }

        try:
            masked_text, mapping = anonymize(text, encryption_key, anon_config)
        except SystemExit:
            emit_json({
                "ok": False,
                "error": {
                    "code": "DEPENDENCY_OR_ENGINE_ERROR",
                    "message": "NLP engine initialization failed. Check dependencies/models.",
                },
            })
            return EXIT_DEPENDENCY_ERROR
        except Exception as e:
            emit_json({
                "ok": False,
                "error": {"code": "ANONYMIZE_FAILED", "message": str(e)},
            })
            return EXIT_PROCESSING_ERROR

        # Convert internal mapping format to JSON-friendly format
        json_mapping = {
            placeholder: {"entity_type": entity_type, "encrypted": encrypted}
            for placeholder, (entity_type, encrypted) in mapping.items()
        }

        emit_json({
            "ok": True,
            "action": "anonymize",
            "masked_text": masked_text,
            "mapping": json_mapping,
            "language": anon_config["language"],
        })
        return EXIT_SUCCESS

    # action == "deanonymize"
    text = payload.get("text")
    mapping = payload.get("mapping")
    if not isinstance(text, str):
        emit_json({
            "ok": False,
            "error": {"code": "INVALID_INPUT_TEXT", "message": "text must be a string for deanonymize action."},
        })
        return EXIT_INPUT_ERROR
    if not isinstance(mapping, dict):
        emit_json({
            "ok": False,
            "error": {"code": "INVALID_MAPPING", "message": "mapping must be an object for deanonymize action."},
        })
        return EXIT_INPUT_ERROR

    try:
        # Convert mapping from JSON format to internal format
        internal_mapping = {k: (v["entity_type"], v["encrypted"]) for k, v in mapping.items()}
        restored_text = deanonymize(text, internal_mapping, encryption_key)
    except Exception as e:
        emit_json({
            "ok": False,
            "error": {"code": "DEANONYMIZE_FAILED", "message": str(e)},
        })
        return EXIT_PROCESSING_ERROR

    emit_json({
        "ok": True,
        "action": "deanonymize",
        "restored_text": restored_text,
    })
    return EXIT_SUCCESS


def main():
    parser = argparse.ArgumentParser(
        prog="pii_masker",
        description="Anonymize and deanonymize text with unique placeholders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  %(prog)s generate-key
  %(prog)s anonymize -c configs/english-fast.yaml -i input.txt -o result
  %(prog)s anonymize -c configs/gliner.yaml -i input.txt -o result
  cat doc.txt | %(prog)s anonymize -c configs/english-fast.yaml > masked.txt
  %(prog)s deanonymize -i masked.txt -m mapping.json -o restored.txt
""",
    )
    subs = parser.add_subparsers(dest="cmd", required=True)

    # Common args shared between subcommands
    common = [
        (["-i", "--input"], {"help": "Input file (stdin if omitted)"}),
        (["-o", "--output"], {"help": "Output prefix"}),
        (["-k", "--key-file"], {"default": DEFAULT_KEY_FILE, "help": "Key file"}),
    ]

    anonymize_parser = subs.add_parser("anonymize", help="Anonymize PII")
    anonymize_parser.add_argument("-c", "--config", help="Config file path")
    anonymize_parser.add_argument("--json", action="store_true", help="JSON mode for native host integration")
    for args, kw in common:
        anonymize_parser.add_argument(*args, **kw)

    deanonymize_parser = subs.add_parser("deanonymize", help="Restore anonymized text")
    deanonymize_parser.add_argument("-m", "--mapping", required=True, help="Mapping JSON file")
    for args, kw in common:
        deanonymize_parser.add_argument(*args, **kw)

    generate_key_parser = subs.add_parser("generate-key", help="Generate encryption key")
    generate_key_parser.add_argument("-k", "--key-file", default=DEFAULT_KEY_FILE, help="Output path")

    benchmark_parser = subs.add_parser("benchmark", help="Benchmark PII detection")
    benchmark_parser.add_argument("--dataset", "-d", required=True,
                                   help="Dataset to benchmark")
    benchmark_parser.add_argument("--config", "-c", default=None,
                                   help="Config preset or path (comma-separated for comparison)")
    benchmark_parser.add_argument("--max-samples", "-n", type=int, default=None,
                                   help="Maximum samples to evaluate")
    benchmark_parser.add_argument("--output", "-o", default=None,
                                   help="Output file for JSON results")
    benchmark_parser.add_argument("--split", "-s", default="train",
                                   help="Dataset split (default: train)")
    benchmark_parser.add_argument("--locale", "-l", default=None,
                                   help="Filter by locale/language (e.g., 'de', 'en')")
    benchmark_parser.add_argument("--domain", default=None,
                                   help="Filter by domain (e.g., 'finance', 'code')")
    benchmark_parser.add_argument("--filter", "-f", action="append", default=None,
                                   help="Custom filter as field=value (repeatable)")
    benchmark_parser.add_argument("--list-fields", action="store_true",
                                   help="List available fields in dataset")
    benchmark_parser.add_argument("--evaluation-mode", "-e",
                                   choices=["coarse", "granular"], default="coarse",
                                   help="Evaluation mode: 'coarse' normalizes entity types for fair comparison, "
                                        "'granular' uses exact matching (default: coarse)")

    args = parser.parse_args()
    start = time.time()

    match args.cmd:
        case "generate-key":
            key = secrets.token_urlsafe(24)
            Path(args.key_file).write_text(key)
            Path(args.key_file).chmod(0o600)
            print(f"Generated encryption key: {args.key_file}")
            print("WARNING: Keep this file secure! If lost, encrypted data cannot be recovered.")
        case "benchmark":
            from benchmark.cli import run as run_benchmark
            run_benchmark(args)
        case "anonymize":
            config = load_config(args.config)
            # Handle JSON mode for native host integration
            if args.json:
                sys.exit(run_json_mode(config))
            for k in ("input", "output", "key_file"):
                if getattr(args, k, None):
                    config[k] = getattr(args, k)
            text = Path(args.input).read_text() if args.input else sys.stdin.read()
            key_path = Path(config.get("key_file", DEFAULT_KEY_FILE))
            if not key_path.exists():
                sys.exit(f"Error: Key file not found: {key_path}\nGenerate one with: pii_masker generate-key")
            key = key_path.read_text().strip()
            masked, mapping = anonymize(text, key, config)

            if args.output:
                out = Path(args.output)
                out.parent.mkdir(parents=True, exist_ok=True)
                (out.parent / f"{out.name}_masked.txt").write_text(masked)
                save_mapping(mapping, out.parent / f"{out.name}_mapping.json", config.get("language", "en"))
                print(f"Masked text: {out.parent / out.name}_masked.txt")
                print(f"Mapping:     {out.parent / out.name}_mapping.json")
            else:
                print(masked)
        case "deanonymize":
            text = Path(args.input).read_text() if args.input else sys.stdin.read()
            mapping = load_mapping(Path(args.mapping))
            key_path = Path(args.key_file)
            if not key_path.exists():
                sys.exit(f"Error: Key file not found: {key_path}")
            key = key_path.read_text().strip()
            restored = deanonymize(text, mapping, key)

            if args.output:
                Path(args.output).write_text(restored)
                print(f"Restored text: {args.output}")
            else:
                print(restored)

    if args.cmd not in ("generate-key", "benchmark"):
        print(f"Total time: {time.time() - start:.1f}s")
    elif args.cmd == "benchmark" and not getattr(args, "list_fields", False):
        print(f"Total time: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
