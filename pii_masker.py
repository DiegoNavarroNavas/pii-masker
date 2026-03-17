#!/usr/bin/env python3
"""
PII Masker CLI - Anonymize and deanonymize text with unique placeholders.

Usage:
    python pii_masker.py --generate-key --key-file key.key
    python pii_masker.py --input text.txt --output result --key-file key.key
    python pii_masker.py --mode deanonymize --input masked.txt --mapping mapping.json --key-file key.key --output restored.txt
"""

# Disable GPU/CUDA loading for CPU-only systems (MUST be before any imports)
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TORCH_DEVICE_BACKEND_AUTOLOAD", "0")

import argparse
import json
import sys
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pii_masker_local import DEFAULT_LOCAL_ENCODER_MODEL, detect_pii_with_local_multihead, resolve_local_multihead_checkpoint

@contextmanager
def pulse(message: str):
    """Show animated status with elapsed time while operation runs."""
    stop = threading.Event()
    start = time.time()

    def animate():
        while not stop.is_set():
            elapsed = time.time() - start
            line = f"⏳ {message} ({elapsed:.1f}s)"
            sys.stderr.write(f"\r{line:<60}")
            sys.stderr.flush()
            time.sleep(0.1)

    thread = threading.Thread(target=animate)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        elapsed = time.time() - start
        line = f"✓ {message} ({elapsed:.1f}s)"
        sys.stderr.write(f"\r{line:<60}\n")
        sys.stderr.flush()

# Supported languages in Presidio
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"]

# Supported NLP engines
SUPPORTED_ENGINES = ["spacy", "stanza", "transformers", "local_multihead"]

# Language-specific spacy models (large versions for better accuracy)
SPACY_MODELS = {
    "en": "en_core_web_lg",
    "es": "es_core_news_lg",
    "fr": "fr_core_news_lg",
    "de": "de_core_news_lg",
    "it": "it_core_news_lg",
    "pt": "pt_core_news_lg",
    "zh": "zh_core_web_lg",
    "ja": "ja_core_news_lg",
    "ko": "ko_core_news_lg",
}

# Small spacy models for transformers engine (only used for tokenization)
SPACY_SMALL_MODELS = {
    "en": "en_core_web_sm",
    "es": "es_core_news_sm",
    "fr": "fr_core_news_sm",
    "de": "de_core_news_sm",
    "it": "it_core_news_sm",
    "pt": "pt_core_news_sm",
    "zh": "zh_core_web_sm",
    "ja": "ja_core_news_sm",
    "ko": "ko_core_news_sm",
}

# Default transformer model (multilingual NER)
DEFAULT_TRANSFORMER_MODEL = "Babelscape/wikineural-multilingual-ner"

# Deterministic exit codes for automation/native messaging integration.
EXIT_SUCCESS = 0
EXIT_INVALID_REQUEST = 2
EXIT_KEY_FILE_ERROR = 3
EXIT_INPUT_ERROR = 4
EXIT_PROCESSING_ERROR = 5
EXIT_DEPENDENCY_ERROR = 6


def emit_json(payload: dict) -> None:
    """Write a compact JSON payload to stdout."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def generate_key_file(path: Path) -> None:
    """Generate a new 256-bit encryption key and save to file."""
    import secrets

    # Generate 32 bytes (256 bits) as a URL-safe base64 string
    # token_urlsafe(24) produces ~32 characters
    key = secrets.token_urlsafe(24)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key)
    # Set restrictive permissions (owner read/write only)
    path.chmod(0o600)
    print(f"Generated encryption key: {path}")
    print("WARNING: Keep this file secure! If lost, encrypted data cannot be recovered.")


def load_key_file(path: Path) -> str:
    """Load encryption key from file as string."""
    if not path.exists():
        raise FileNotFoundError(f"Key file not found: {path}")
    return path.read_text().strip()


def create_nlp_engine(
    engine: str,
    model: str | None,
    spacy_model: str | None,
    transformer_model: str | None,
    ner_config: dict | None,
    language: str,
):
    """
    Create an NLP engine with flexible model configuration.

    Args:
        engine: Engine type (spacy, stanza, transformers)
        model: Model name (string or "spacy:transformer" format for transformers)
        spacy_model: Spacy model for tokenization (transformers engine only)
        transformer_model: Transformer NER model (transformers engine only)
        ner_config: NerModelConfiguration options as dict
        language: Language code for analysis

    Returns:
        NLP engine instance
    """
    from presidio_analyzer.nlp_engine import NerModelConfiguration

    engine = engine.lower()

    # Check if requested engine is available
    if engine == "stanza":
        from presidio_analyzer.nlp_engine import StanzaNlpEngine
        if not StanzaNlpEngine.is_available:
            raise ImportError("stanza package is not installed")
    elif engine == "transformers":
        from presidio_analyzer.nlp_engine import TransformersNlpEngine
        if not TransformersNlpEngine.is_available:
            raise ImportError("transformers package is not installed")

    # Parse model string for transformers if in "spacy:transformer" format
    if engine == "transformers" and model and ":" in model:
        parts = model.split(":", 1)
        spacy_model = spacy_model or parts[0]
        transformer_model = transformer_model or parts[1]

    # Build NerModelConfiguration if provided
    ner_model_config = None
    if ner_config:
        ner_model_config = NerModelConfiguration(**ner_config)

    if engine == "spacy":
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        model_name = model or SPACY_MODELS.get(language, SPACY_MODELS["en"])
        return SpacyNlpEngine(
            models=[{"lang_code": language, "model_name": model_name}],
            ner_model_configuration=ner_model_config,
        )

    elif engine == "stanza":
        from presidio_analyzer.nlp_engine import StanzaNlpEngine

        model_name = model or language
        return StanzaNlpEngine(
            models=[{"lang_code": language, "model_name": model_name}],
            ner_model_configuration=ner_model_config,
        )

    elif engine == "transformers":
        from presidio_analyzer.nlp_engine import TransformersNlpEngine

        spacy = spacy_model or SPACY_SMALL_MODELS.get(language, SPACY_SMALL_MODELS["en"])
        transformer = transformer_model or model or DEFAULT_TRANSFORMER_MODEL

        return TransformersNlpEngine(
            models=[{
                "lang_code": language,
                "model_name": {
                    "spacy": spacy,
                    "transformers": transformer,
                }
            }],
            ner_model_configuration=ner_model_config,
        )

    else:
        raise ValueError(f"Unsupported engine: {engine}. Choose from: {SUPPORTED_ENGINES}")


def create_analyzer(
    engine: str,
    model: str | None,
    spacy_model: str | None,
    transformer_model: str | None,
    ner_config: dict | None,
    language: str,
    recognizers_yaml: Path | None,
    recognizers_json: list[str] | None,
):
    """
    Create an analyzer with custom recognizers.

    Args:
        engine: NLP engine type
        model: Model name (string or "spacy:transformer" format)
        spacy_model: Spacy model for tokenization (transformers only)
        transformer_model: Transformer NER model (transformers only)
        ner_config: NerModelConfiguration options
        language: Language code
        recognizers_yaml: Path to YAML file with custom recognizers
        recognizers_json: List of JSON strings defining custom recognizers

    Returns:
        Configured AnalyzerEngine instance
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

    with pulse(f"Loading {engine} NLP engine"):
        try:
            nlp_engine = create_nlp_engine(
                engine, model, spacy_model, transformer_model, ner_config, language
            )
            # NLP engine must be loaded before passing to registry
            nlp_engine.load()
        except ImportError as e:
            print(f"Error: Missing dependencies for engine '{engine}': {e}", file=sys.stderr)
            print(f"Install with: pip install presidio-analyzer[{engine}]", file=sys.stderr)
            sys.exit(1)
        except (NameError, ModuleNotFoundError) as e:
            # Handle cases where engine module imports fail (e.g., stanza not installed)
            print(f"Error: Missing dependencies for engine '{engine}': {e}", file=sys.stderr)
            print(f"Install with: pip install presidio-analyzer[{engine}]", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error creating NLP engine: {e}", file=sys.stderr)
            sys.exit(1)

    # Create registry and load predefined recognizers
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(languages=[language], nlp_engine=nlp_engine)

    # Load custom recognizers from YAML
    if recognizers_yaml:
        with pulse(f"Loading recognizers from {recognizers_yaml}"):
            try:
                registry.add_recognizers_from_yaml(recognizers_yaml)
            except Exception as e:
                print(f"Error loading recognizers from YAML: {e}", file=sys.stderr)
                sys.exit(1)

    # Add custom recognizers from JSON strings
    if recognizers_json:
        for recognizer_json in recognizers_json:
            try:
                recognizer_dict = json.loads(recognizer_json)
                registry.add_pattern_recognizer_from_dict(recognizer_dict)
            except json.JSONDecodeError as e:
                print(f"Error parsing recognizer JSON: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error adding recognizer: {e}", file=sys.stderr)
                sys.exit(1)

    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)


def anonymize_with_unique_masks(
    text: str,
    encryption_key: str,
    language: str = "en",
    engine: str = "spacy",
    model: str | None = None,
    spacy_model: str | None = None,
    transformer_model: str | None = None,
    local_encoder_model: str | None = None,
    ner_config: dict | None = None,
    recognizers_yaml: Path | None = None,
    recognizers_json: list[str] | None = None,
) -> tuple[str, dict]:
    """
    Replaces PII with unique indexed placeholders like <PERSON_1>, <PERSON_2>.
    Identical strings get identical indices (e.g., both "John" become <PERSON_1>).
    The mapping stores encrypted values for secure deanonymization.

    Args:
        text: Input text to anonymize
        encryption_key: Encryption key string
        language: Language code for analysis
        engine: NLP engine to use
        model: Model name/path ("spacy:transformer" format for transformers; .pt path for local_multihead)
        spacy_model: Spacy model for tokenization (transformers only)
        transformer_model: Transformer NER model (transformers only)
        local_encoder_model: Encoder/tokenizer id for local_multihead
        ner_config: NerModelConfiguration options
        recognizers_yaml: Path to YAML file with custom recognizers
        recognizers_json: List of JSON strings defining custom recognizers

    Returns:
        Tuple of (anonymized_text, decrypt_mapping)
    """
    from presidio_analyzer import RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    anonymizer = AnonymizerEngine()

    if engine == "local_multihead":
        checkpoint_path = resolve_local_multihead_checkpoint(model)
        with pulse(f"Loading local multihead checkpoint: {checkpoint_path.name}"):
            detections = detect_pii_with_local_multihead(
                text=text,
                checkpoint_path=checkpoint_path,
                encoder_model=local_encoder_model,
            )
        results = [
            RecognizerResult(
                entity_type=d["entity_type"],
                start=d["start"],
                end=d["end"],
                score=d["score"],
            )
            for d in detections
        ]
    else:
        analyzer = create_analyzer(
            engine=engine,
            model=model,
            spacy_model=spacy_model,
            transformer_model=transformer_model,
            ner_config=ner_config,
            language=language,
            recognizers_yaml=recognizers_yaml,
            recognizers_json=recognizers_json,
        )
        with pulse("Analyzing text for PII"):
            results = analyzer.analyze(text=text, language=language)

    if not results:
        return text, {}

    # Create unique mapping: (entity_type, value) -> (placeholder, encrypted_value)
    entity_counters = defaultdict(int)
    entity_map: dict[tuple[str, str], tuple[str, str]] = {}

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

    # First pass: encrypt each unique value and build mapping
    with pulse(f"Encrypting {len(sorted_results)} entities"):
        for result in sorted_results:
            original_value = text[result.start : result.end]
            key = (result.entity_type, original_value)

            if key not in entity_map:
                entity_counters[result.entity_type] += 1
                placeholder = f"<{result.entity_type}_{entity_counters[result.entity_type]}>"

                # Encrypt the original value
                adjusted_result = RecognizerResult(
                    entity_type=result.entity_type,
                    start=0,
                    end=len(original_value),
                    score=result.score,
                )
                encrypted = anonymizer.anonymize(
                    text=original_value,
                    analyzer_results=[adjusted_result],
                    operators={"DEFAULT": OperatorConfig("encrypt", {"key": encryption_key})},
                )
                entity_map[key] = (placeholder, encrypted.text)

    # Second pass: replace with placeholders (end to start so positions don't shift)
    anonymized_text = text
    for result in sorted(sorted_results, key=lambda x: x.start, reverse=True):
        original_value = text[result.start : result.end]
        key = (result.entity_type, original_value)
        placeholder = entity_map[key][0]

        anonymized_text = (
            anonymized_text[: result.start] + placeholder + anonymized_text[result.end :]
        )

    # Return simplified mapping for deanonymization: placeholder -> (entity_type, encrypted)
    decrypt_map = {v[0]: (k[0], v[1]) for k, v in entity_map.items()}
    return anonymized_text, decrypt_map


def deanonymize_unique_masks(
    anonymized_text: str,
    decrypt_map: dict,
    encryption_key: str,
) -> str:
    """Reverses the unique mask anonymization using the encryption key."""
    from presidio_anonymizer import DeanonymizeEngine
    from presidio_anonymizer.entities import OperatorConfig, OperatorResult

    engine = DeanonymizeEngine()
    result_text = anonymized_text

    with pulse(f"Decrypting {len(decrypt_map)} entities"):
        # Find and decrypt each placeholder
        for placeholder, (entity_type, encrypted_value) in decrypt_map.items():
            decrypted = engine.deanonymize(
                text=encrypted_value,
                entities=[
                    OperatorResult(start=0, end=len(encrypted_value), entity_type=entity_type)
                ],
                operators={"DEFAULT": OperatorConfig("decrypt", {"key": encryption_key})},
            )
            result_text = result_text.replace(placeholder, decrypted.text)

    return result_text


def save_mapping(mapping: dict, path: Path, language: str) -> None:
    """Save the mapping to a JSON file with metadata."""
    # Convert tuple keys to strings for JSON serialization
    serializable_mappings = {}
    for placeholder, (entity_type, encrypted) in mapping.items():
        serializable_mappings[placeholder] = {
            "entity_type": entity_type,
            "encrypted": encrypted,
        }

    data = {
        "version": "1.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "mappings": serializable_mappings,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_mapping(path: Path) -> dict:
    """Load mapping from JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    data = json.loads(path.read_text())

    # Convert back to the expected format: placeholder -> (entity_type, encrypted)
    mapping = {}
    for placeholder, info in data["mappings"].items():
        mapping[placeholder] = (info["entity_type"], info["encrypted"])

    return mapping


def parse_ner_config(config_str: str | None, parser: argparse.ArgumentParser) -> dict | None:
    """Parse NER configuration from JSON string."""
    if not config_str:
        return None
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        parser.error(f"Invalid --ner-config JSON: {e}")


def run_anonymize(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Run anonymization mode."""
    # Load input
    if args.input:
        input_text = Path(args.input).read_text()
    else:
        # Read from stdin
        input_text = sys.stdin.read()

    # Load encryption key
    encryption_key = load_key_file(Path(args.key_file))

    # Parse NER config
    ner_config = parse_ner_config(args.ner_config, parser)

    # Convert recognizers_yaml to Path if provided
    recognizers_yaml = Path(args.recognizers_yaml) if args.recognizers_yaml else None

    # Anonymize
    masked_text, mapping = anonymize_with_unique_masks(
        text=input_text,
        encryption_key=encryption_key,
        language=args.language,
        engine=args.engine,
        model=args.model,
        spacy_model=args.spacy_model,
        transformer_model=args.transformer_model,
        local_encoder_model=args.local_encoder_model,
        ner_config=ner_config,
        recognizers_yaml=recognizers_yaml,
        recognizers_json=args.recognizer,
    )

    # Output results
    if args.output:
        output_path = Path(args.output)
        masked_file = output_path.parent / f"{output_path.name}_masked.txt"
        mapping_file = output_path.parent / f"{output_path.name}_mapping.json"

        with pulse("Writing output files"):
            masked_file.write_text(masked_text)
            save_mapping(mapping, mapping_file, args.language)

        print(f"Masked text: {masked_file}")
        print(f"Mapping:     {mapping_file}")
    else:
        # Output to stdout
        print("\n--- Masked Text ---", file=sys.stderr)
        print(masked_text)
        print("\n--- Mapping (JSON) ---", file=sys.stderr)
        print(json.dumps(mapping, indent=2), file=sys.stderr)


def run_deanonymize(args: argparse.Namespace) -> None:
    """Run deanonymization mode."""
    # Load masked text
    if args.input:
        masked_text = Path(args.input).read_text()
    else:
        masked_text = sys.stdin.read()

    # Load mapping
    mapping = load_mapping(Path(args.mapping))

    # Load encryption key
    encryption_key = load_key_file(Path(args.key_file))

    # Deanonymize
    restored_text = deanonymize_unique_masks(
        anonymized_text=masked_text,
        decrypt_map=mapping,
        encryption_key=encryption_key,
    )

    # Output results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with pulse("Writing restored text"):
            output_path.write_text(restored_text)
        print(f"Restored text: {output_path}")
    else:
        print(restored_text)


def run_json_mode(args: argparse.Namespace) -> int:
    """
    Machine-readable mode for programmatic integrations.

    Reads one JSON document from stdin and writes one JSON document to stdout.
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            emit_json(
                {
                    "ok": False,
                    "error": {
                        "code": "EMPTY_REQUEST",
                        "message": "No JSON payload received on stdin.",
                    },
                }
            )
            return EXIT_INVALID_REQUEST
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        emit_json(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_JSON",
                    "message": f"Failed to parse request JSON: {e}",
                },
            }
        )
        return EXIT_INVALID_REQUEST

    action = payload.get("action", "anonymize")
    if action not in {"anonymize", "deanonymize"}:
        emit_json(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_ACTION",
                    "message": "action must be 'anonymize' or 'deanonymize'.",
                },
            }
        )
        return EXIT_INVALID_REQUEST

    key_file = payload.get("key_file") or args.key_file
    if not key_file:
        emit_json(
            {
                "ok": False,
                "error": {
                    "code": "MISSING_KEY_FILE",
                    "message": "key_file is required.",
                },
            }
        )
        return EXIT_INVALID_REQUEST

    try:
        encryption_key = load_key_file(Path(key_file))
    except FileNotFoundError as e:
        emit_json(
            {
                "ok": False,
                "error": {"code": "KEY_FILE_NOT_FOUND", "message": str(e)},
            }
        )
        return EXIT_KEY_FILE_ERROR
    except Exception as e:
        emit_json(
            {
                "ok": False,
                "error": {"code": "KEY_FILE_READ_FAILED", "message": str(e)},
            }
        )
        return EXIT_KEY_FILE_ERROR

    if action == "anonymize":
        text = payload.get("text")
        if not isinstance(text, str):
            emit_json(
                {
                    "ok": False,
                    "error": {
                        "code": "INVALID_INPUT_TEXT",
                        "message": "text must be a string for anonymize action.",
                    },
                }
            )
            return EXIT_INPUT_ERROR

        language = payload.get("language", args.language)
        if language not in SUPPORTED_LANGUAGES:
            emit_json(
                {
                    "ok": False,
                    "error": {
                        "code": "UNSUPPORTED_LANGUAGE",
                        "message": f"Unsupported language: {language}",
                    },
                }
            )
            return EXIT_INVALID_REQUEST

        engine = payload.get("engine", args.engine)
        if engine not in SUPPORTED_ENGINES:
            emit_json(
                {
                    "ok": False,
                    "error": {
                        "code": "UNSUPPORTED_ENGINE",
                        "message": f"Unsupported engine: {engine}",
                    },
                }
            )
            return EXIT_INVALID_REQUEST

        recognizers_yaml = payload.get("recognizers_yaml")
        recognizers_json = payload.get("recognizers")
        if recognizers_json is not None and not isinstance(recognizers_json, list):
            emit_json(
                {
                    "ok": False,
                    "error": {
                        "code": "INVALID_RECOGNIZERS",
                        "message": "recognizers must be an array of recognizer JSON strings.",
                    },
                }
            )
            return EXIT_INVALID_REQUEST

        try:
            masked_text, mapping = anonymize_with_unique_masks(
                text=text,
                encryption_key=encryption_key,
                language=language,
                engine=engine,
                model=payload.get("model", args.model),
                spacy_model=payload.get("spacy_model", args.spacy_model),
                transformer_model=payload.get("transformer_model", args.transformer_model),
                local_encoder_model=payload.get("local_encoder_model", args.local_encoder_model),
                ner_config=payload.get("ner_config"),
                recognizers_yaml=Path(recognizers_yaml) if recognizers_yaml else None,
                recognizers_json=recognizers_json,
            )
        except SystemExit:
            emit_json(
                {
                    "ok": False,
                    "error": {
                        "code": "DEPENDENCY_OR_ENGINE_ERROR",
                        "message": "NLP engine initialization failed. Check dependencies/models.",
                    },
                }
            )
            return EXIT_DEPENDENCY_ERROR
        except Exception as e:
            emit_json(
                {
                    "ok": False,
                    "error": {"code": "ANONYMIZE_FAILED", "message": str(e)},
                }
            )
            return EXIT_PROCESSING_ERROR

        emit_json(
            {
                "ok": True,
                "action": "anonymize",
                "masked_text": masked_text,
                "mapping": mapping,
                "language": language,
            }
        )
        return EXIT_SUCCESS

    # action == "deanonymize"
    text = payload.get("text")
    mapping = payload.get("mapping")
    if not isinstance(text, str):
        emit_json(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_INPUT_TEXT",
                    "message": "text must be a string for deanonymize action.",
                },
            }
        )
        return EXIT_INPUT_ERROR
    if not isinstance(mapping, dict):
        emit_json(
            {
                "ok": False,
                "error": {
                    "code": "INVALID_MAPPING",
                    "message": "mapping must be an object for deanonymize action.",
                },
            }
        )
        return EXIT_INPUT_ERROR

    try:
        normalized_mapping = {}
        for placeholder, info in mapping.items():
            if isinstance(info, dict):
                normalized_mapping[placeholder] = (info["entity_type"], info["encrypted"])
            elif isinstance(info, (list, tuple)) and len(info) == 2:
                normalized_mapping[placeholder] = (info[0], info[1])
            else:
                raise ValueError(f"Invalid mapping entry for {placeholder!r}")

        restored_text = deanonymize_unique_masks(
            anonymized_text=text,
            decrypt_map=normalized_mapping,
            encryption_key=encryption_key,
        )
    except Exception as e:
        emit_json(
            {
                "ok": False,
                "error": {"code": "DEANONYMIZE_FAILED", "message": str(e)},
            }
        )
        return EXIT_PROCESSING_ERROR

    emit_json({"ok": True, "action": "deanonymize", "text": restored_text})
    return EXIT_SUCCESS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PII Masker - Anonymize and deanonymize text with unique placeholders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a new encryption key
  %(prog)s --generate-key --key-file secret.key

  # Anonymize a file (default: spacy with English model)
  %(prog)s --input document.txt --output result --key-file secret.key

  # Anonymize with different language
  %(prog)s --input spanish.txt --output result --key-file secret.key --language es

  # Use custom spacy model
  %(prog)s --input text.txt --output out --key-file secret.key --engine spacy --model de_core_news_lg

  # Use Stanza engine for better multilingual support
  %(prog)s --input text.txt --output out --key-file secret.key --engine stanza --language de

  # Use transformers with custom models (simple syntax)
  %(prog)s --input text.txt --output out --key-file secret.key --engine transformers --language de --model "de_core_news_md:dslim/bert-base-NER"

  # Use transformers with explicit flags
  %(prog)s --input text.txt --output out --key-file secret.key --engine transformers --spacy-model de_core_news_md --transformer-model dslim/bert-base-NER

  # Advanced: Custom NER configuration
  %(prog)s --input text.txt --output out --key-file secret.key --engine transformers --model "en_core_web_sm:dslim/bert-base-NER" --ner-config '{"aggregation_strategy": "average", "default_score": 0.9}'

  # Use local .pt multihead model (ModernBERT encoder by default)
  %(prog)s --input text.txt --output out --key-file secret.key --engine local_multihead --model local_models/multihead_model.pt

  # Load custom recognizers from YAML
  %(prog)s --input text.txt --output out --key-file secret.key --recognizers-yaml custom_recognizers.yaml

  # Add a single custom recognizer via CLI
  %(prog)s --input text.txt --output out --key-file secret.key --recognizer '{"name": "Zip", "supported_entity": "ZIP", "supported_language": "en", "patterns": [{"name": "zip", "regex": "\\\\d{5}", "score": 0.8}]}'

  # Deanonymize a file
  %(prog)s --mode deanonymize --input result_masked.txt --mapping result_mapping.json --key-file secret.key --output restored.txt
""",
    )

    # Mode selection
    parser.add_argument(
        "--mode",
        choices=["anonymize", "deanonymize"],
        default="anonymize",
        help="Operation mode (default: anonymize)",
    )

    # Key management
    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="Generate a new encryption key file and exit",
    )
    parser.add_argument(
        "--key-file",
        type=str,
        help="Path to encryption key file (required for anonymize/deanonymize)",
    )

    # Input/Output
    parser.add_argument(
        "--input",
        type=str,
        help="Input text file (reads from stdin if not specified)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file prefix for anonymize mode, or full path for deanonymize mode",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        help="Mapping JSON file (required for deanonymize mode)",
    )

    # Language and Engine
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        choices=SUPPORTED_LANGUAGES,
        help="Language code for analysis (default: en)",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="spacy",
        choices=SUPPORTED_ENGINES,
        help="NLP engine to use (default: spacy)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name or path. For transformers: 'spacy_model:transformer_model'; for local_multihead: path to .pt",
    )
    parser.add_argument(
        "--spacy-model",
        type=str,
        help="Spacy model for tokenization (transformers engine only)",
    )
    parser.add_argument(
        "--transformer-model",
        type=str,
        help="Transformer NER model (transformers engine only)",
    )
    parser.add_argument(
        "--local-encoder-model",
        type=str,
        default=DEFAULT_LOCAL_ENCODER_MODEL,
        help=(
            "Base encoder/tokenizer for local_multihead checkpoints "
            f"(default: {DEFAULT_LOCAL_ENCODER_MODEL})"
        ),
    )
    parser.add_argument(
        "--ner-config",
        type=str,
        help="JSON string with NER configuration options (e.g., '{\"aggregation_strategy\": \"max\"}')",
    )

    # Custom recognizers
    parser.add_argument(
        "--recognizers-yaml",
        type=str,
        help="Path to YAML file with custom recognizers",
    )
    parser.add_argument(
        "--recognizer",
        type=str,
        action="append",
        help="JSON string defining a custom recognizer (can be used multiple times)",
    )
    parser.add_argument(
        "--json-mode",
        action="store_true",
        help="Read request JSON from stdin and write response JSON to stdout",
    )

    args = parser.parse_args()
    start_time = time.time()

    if args.json_mode:
        exit_code = run_json_mode(args)
        sys.exit(exit_code)

    # Handle key generation
    if args.generate_key:
        if not args.key_file:
            parser.error("--key-file is required when using --generate-key")
        generate_key_file(Path(args.key_file))
        return

    # Validate required arguments for other modes
    if not args.key_file:
        parser.error("--key-file is required")

    if args.mode == "deanonymize":
        if not args.mapping:
            parser.error("--mapping is required for deanonymize mode")
        run_deanonymize(args)
    else:
        run_anonymize(args, parser)

    total_time = time.time() - start_time
    print(f"Total time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
