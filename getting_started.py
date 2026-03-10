#!/usr/bin/env python3
"""PII Masker - Detect and anonymize PII in text files."""

import argparse
import sys
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
)
from presidio_anonymizer import AnonymizerEngine


def get_bundled_model_path():
    """Get the path to the bundled spaCy model in frozen environment."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
        return base_path / "en_core_web_lg"
    return None


def create_nlp_engine():
    """Create NLP engine, handling frozen environment."""
    bundled_path = get_bundled_model_path()

    if bundled_path and bundled_path.exists():
        # Load from bundled path
        import spacy
        nlp = spacy.load(str(bundled_path))
        # Create engine with pre-loaded model
        engine = SpacyNlpEngine()
        engine.nlp = {"en": nlp}
        return engine
    else:
        # Normal environment - use model name
        return SpacyNlpEngine(models=[{"lang_code": "en", "model_name": "en_core_web_lg"}])


def create_registry():
    """Create registry with predefined recognizers (avoids config file issues)."""
    registry = RecognizerRegistry()
    registry.add_recognizer(PhoneRecognizer())
    registry.add_recognizer(EmailRecognizer())
    registry.add_recognizer(CreditCardRecognizer())
    registry.add_recognizer(SpacyRecognizer())
    return registry


def main():
    parser = argparse.ArgumentParser(description="Detect and anonymize PII in text files")
    parser.add_argument("input_file", type=Path, help="Path to input text file")
    parser.add_argument("-o", "--output", type=Path, help="Output file (default: stdout)")
    parser.add_argument("-e", "--entities", nargs="+",
                        default=["PHONE_NUMBER", "EMAIL_ADDRESS", "PERSON", "CREDIT_CARD"],
                        help="PII entities to detect (default: common types)")
    args = parser.parse_args()

    # Read input file
    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    text = args.input_file.read_text()

    # Create NLP engine (handles bundled model in frozen environment)
    nlp_engine = create_nlp_engine()

    # Create registry with predefined recognizers
    registry = create_registry()

    # Analyze for PII
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
    results = analyzer.analyze(text=text, entities=args.entities, language='en')

    print(f"Found {len(results)} PII entities:", file=sys.stderr)
    for r in results:
        print(f"  - {r.entity_type}: '{text[r.start:r.end]}'", file=sys.stderr)

    # Anonymize
    anonymizer = AnonymizerEngine()
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)

    # Output result
    if args.output:
        args.output.write_text(anonymized.text)
        print(f"Anonymized text written to: {args.output}", file=sys.stderr)
    else:
        print(anonymized.text)


if __name__ == "__main__":
    main()
