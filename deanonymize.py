from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine, DeanonymizeEngine
from presidio_anonymizer.entities import OperatorConfig, OperatorResult

# 1. Detect PII
analyzer = AnalyzerEngine()
text = "My name is John Doe"
analyzer_results = analyzer.analyze(text=text, entities=["PERSON"], language="en")

# 2. Anonymize using encryption (reversible)
anonymizer = AnonymizerEngine()
encryption_key = "a1b2c3d4e5f6g7h8"

anonymized_result = anonymizer.anonymize(
    text=text,
    analyzer_results=analyzer_results,
    operators={"PERSON": OperatorConfig("encrypt", {"key": encryption_key})},
)

print(anonymized_result.text)  # Output: My name is <encrypted_string>

# 3. Deanonymize (recover original)
engine = DeanonymizeEngine()

# Extract entity positions from anonymization result
entities = []
for item in anonymized_result.items:
    entities.append(OperatorResult(
        start=item.start, 
        end=item.end, 
        entity_type=item.entity_type
    ))

# Decrypt back to original
result = engine.deanonymize(
    text=anonymized_result.text,
    entities=entities,
    operators={"DEFAULT": OperatorConfig("decrypt", {"key": encryption_key})},
)

print(result.text)  # Output: My name is John Doe