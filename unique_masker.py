from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine, DeanonymizeEngine
from presidio_anonymizer.entities import OperatorConfig, OperatorResult
from collections import defaultdict


def anonymize_with_unique_masks(text, encryption_key, language="en"):
    """
    Replaces PII with unique indexed placeholders like <PERSON_1>, <PERSON_2>.
    Identical strings get identical indices (e.g., both "John" become <PERSON_1>).
    The mapping stores encrypted values for secure deanonymization.
    """
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    results = analyzer.analyze(text=text, language=language)

    if not results:
        return text, {}

    # Create unique mapping: (entity_type, value) -> (placeholder, encrypted_value)
    entity_counters = defaultdict(int)
    entity_map = {}

    sorted_results = sorted(results, key=lambda x: x.start)

    # First pass: encrypt each unique value and build mapping
    for result in sorted_results:
        original_value = text[result.start:result.end]
        key = (result.entity_type, original_value)

        if key not in entity_map:
            entity_counters[result.entity_type] += 1
            placeholder = f"<{result.entity_type}_{entity_counters[result.entity_type]}>"

            # Encrypt the original value (adjust positions to match extracted text)
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
        original_value = text[result.start:result.end]
        key = (result.entity_type, original_value)
        placeholder = entity_map[key][0]

        anonymized_text = (
            anonymized_text[:result.start] + placeholder + anonymized_text[result.end:]
        )

    # Return simplified mapping for deanonymization: placeholder -> (entity_type, encrypted)
    decrypt_map = {v[0]: (k[0], v[1]) for k, v in entity_map.items()}
    return anonymized_text, decrypt_map


def deanonymize_unique_masks(anonymized_text, decrypt_map, encryption_key):
    """Reverses the unique mask anonymization using the encryption key."""
    engine = DeanonymizeEngine()
    result_text = anonymized_text

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


if __name__ == "__main__":
    # Usage
    encryption_key = "a1b2c3d4e5f6g7h8"
    text = "John gave Mary a present, which John had previously received from Sally."

    masked_text, mapping = anonymize_with_unique_masks(text, encryption_key)

    print(f"Original: {text}")
    print(f"Masked:   {masked_text}")
    print(f"Mapping:  {mapping}")

    # Deanonymize
    restored = deanonymize_unique_masks(masked_text, mapping, encryption_key)
    print(f"Restored: {restored}")
