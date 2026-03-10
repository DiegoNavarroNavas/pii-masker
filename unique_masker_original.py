from presidio_analyzer import AnalyzerEngine
from collections import defaultdict

def anonymize_with_unique_masks(text, language="en"):
    """
    Replaces PII with unique indexed placeholders like <PERSON_1>, <PERSON_2>.
    Identical strings get identical indices (e.g., both "John" become <PERSON_1>).
    """
    # Step 1: Analyze only
    analyzer = AnalyzerEngine()
    results = analyzer.analyze(text=text, language=language)
    
    if not results:
        return text, {}
    
    # Step 2: Create unique mapping (entity_type, value) -> placeholder
    entity_counters = defaultdict(int)
    entity_map = {}  # Key: (entity_type, original_text), Value: <TYPE_N>
    
    # Sort results by position (start) to assign numbers in order of appearance
    sorted_results = sorted(results, key=lambda x: x.start)
    
    for result in sorted_results:
        original_value = text[result.start:result.end]
        key = (result.entity_type, original_value)
        
        if key not in entity_map:
            entity_counters[result.entity_type] += 1
            entity_map[key] = f"<{result.entity_type}_{entity_counters[result.entity_type]}>"
    
    # Step 3: Replace from end to start (so positions don't shift)
    anonymized_text = text
    for result in sorted(sorted_results, key=lambda x: x.start, reverse=True):
        original_value = text[result.start:result.end]
        key = (result.entity_type, original_value)
        placeholder = entity_map[key]
        
        anonymized_text = (
            anonymized_text[:result.start] + 
            placeholder + 
            anonymized_text[result.end:]
        )
    
    return anonymized_text, entity_map

# Usage
text = "John gave Mary a present, which John had previously received from Sally."
masked_text, mapping = anonymize_with_unique_masks(text)

print(f"Original: {text}")
print(f"Masked:   {masked_text}")
# Output: John gave Mary a present, which John had previously received from Sally.
# Masked:   <PERSON_1> gave <PERSON_2> a present, which <PERSON_1> had previously received from <PERSON_3>.

print(f"Mapping:  {mapping}")
# {('PERSON', 'John'): '<PERSON_1>', ('PERSON', 'Mary'): '<PERSON_2>', ('PERSON', 'Sally'): '<PERSON_3>'}