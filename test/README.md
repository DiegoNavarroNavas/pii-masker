# PII Masker Test Infrastructure

This directory contains the test infrastructure for validating the PII Masker's anonymization and deanonymization pipeline across different NLP engines and recognizers.

## Directory Structure

```
test/
├── README.md                      # This file
├── data/
│   ├── input/                     # Generated test texts (gitignored)
│   │   ├── en_sample.txt          # ~100KB English
│   │   ├── de_sample.txt          # ~100KB German
│   │   ├── fr_sample.txt          # ~100KB French
│   │   ├── it_sample.txt          # ~100KB Italian
│   │   └── es_sample.txt          # ~100KB Spanish
│   └── pii_templates/             # PII data for generation
│       ├── names.json             # Names by language
│       ├── locations.json         # Cities, streets, countries
│       ├── contacts.json          # Emails, phones
│       ├── addresses.json         # Full postal addresses
│       ├── companies.json         # Company names by country
│       ├── credentials.json       # Usernames, IDs, SSNs
│       ├── financial.json         # Credit cards, IBANs
│       ├── dates.json             # Date formats by locale
│       └── medical.json           # Medical record numbers
│
├── output/                        # Test outputs (gitignored)
│   └── <timestamp>/
│       ├── summary.json
│       └── <lang>_<preset>/
│           ├── masked.txt
│           ├── masked_mapping.json
│           ├── restored.txt
│           └── metrics.json
│
├── scripts/
│   ├── generate_test_data.py      # Create multilingual test texts
│   └── run_tests.py               # Run all test combinations
│
└── config/
    └── test_matrix.yaml           # Defines test combinations

# All configs (built-in and test) are in the configs/ directory
# See configs/ for the full list of available configurations
```

## Quick Start

```bash
# 1. Generate test data (~100KB per language)
python test/scripts/generate_test_data.py

# 2. Run quick tests (fast models only)
python test/scripts/run_tests.py --quick

# 3. Run full test suite
python test/scripts/run_tests.py
```

## Test Data Generation

The `generate_test_data.py` script creates synthetic text with embedded PII:

```bash
# Generate all languages (default ~100KB each)
python test/scripts/generate_test_data.py

# Generate specific languages
python test/scripts/generate_test_data.py --languages en de

# Generate smaller files for quick testing
python test/scripts/generate_test_data.py --size 50000

# Reproducible generation
python test/scripts/generate_test_data.py --seed 42
```

### PII Types Embedded

Each test file contains realistic PII patterns:

- **Names**: First/last names appropriate to each language
- **Emails**: Various formats with language-appropriate domains
- **Phone numbers**: Country-specific formats
- **Addresses**: Full postal addresses with postal codes
- **Companies**: Company names with appropriate suffixes (Inc., GmbH, SARL, etc.)
- **Credit cards**: Visa, MasterCard, Amex, Discover numbers
- **IBANs**: Country-specific IBAN formats
- **SSNs/Tax IDs**: Country-specific formats
- **Passport numbers**: Country-specific formats
- **Medical record numbers**: Format varies by country
- **Dates**: Locale-specific date formats

## Running Tests

### Basic Usage

```bash
# Run all tests
python test/scripts/run_tests.py

# Quick mode (skip slow transformer/GLiNER models)
python test/scripts/run_tests.py --quick

# Test specific presets
python test/scripts/run_tests.py --presets spacy_sm_en stanza_en

# Test specific languages
python test/scripts/run_tests.py --languages en de
```

### Test Results

Results are saved to `test/output/<timestamp>/`:

- `summary.json` - Aggregate results for all tests
- `<lang>_<preset>/` - Per-test directories containing:
  - `masked.txt` - Anonymized output
  - `masked_mapping.json` - Entity mapping
  - `restored.txt` - Deanonymized output
  - `metrics.json` - Timing and entity counts

### Success Criteria

A test passes if:
1. Anonymization completes without error
2. Deanonymization completes without error
3. Roundtrip verification: `original == restored` (byte-for-byte)

## Test Presets

All configs are stored in the `configs/` directory at the project root:

**Built-in presets** (for production use):
- `english-fast`, `english-accurate`, `german`, `multilingual`, `gliner`

**Test presets** (for benchmarking/engine comparison):

| Engine | Presets | Languages |
|--------|---------|-----------|
| spaCy | `spacy_sm_en` | en |
| Stanza | `stanza_en`, `stanza_de`, `stanza_fr`, `stanza_it`, `stanza_es` | all |
| XLM-RoBERTa | `xlmr_en`, `xlmr_de`, `xlmr_fr`, `xlmr_it`, `xlmr_es` | all |
| GLiNER | `gliner_en`, ... (5 total) | all |

### Test Matrix

| Language | spaCy | Stanza | XLM-R | GLiNER |
|----------|-------|--------|-------|--------|
| en       | X     | X      | X     | X      |
| de       | -     | X      | X     | X      |
| fr       | -     | X      | X     | X      |
| it       | -     | X      | X     | X      |
| es       | -     | X      | X     | X      |

**Total: 16 test combinations**

## Configuration

### test_matrix.yaml

Controls which preset/language combinations are tested:

```yaml
test_matrix:
  spacy_sm_en: [en]
  stanza_de: [de]
  # ... etc

settings:
  key_file: pii.key          # Uses project root pii.key
  output_dir: test/output
  timeout_seconds: 300
  verify_roundtrip: true
```

## Manual Testing

```bash
# Generate test data
python test/scripts/generate_test_data.py

# Run single test
python pii_masker.py anonymize -c configs/spacy_sm_en.yaml \
    -i test/data/input/en_sample.txt -o test/output/manual_test -k pii.key

# Verify roundtrip
python pii_masker.py deanonymize \
    -i test/output/manual_test_masked.txt \
    -m test/output/manual_test_mapping.json \
    -o test/output/manual_test_restored -k pii.key

# Compare
diff test/data/input/en_sample.txt test/output/manual_test_restored.txt
```

## Adding New Tests

1. Create a new config in `configs/`
2. Add to `test_matrix.yaml`
3. If new language, add to `languages` section and create PII templates
4. Regenerate test data if needed

## Dependencies

Test scripts require:
- `pyyaml` for config parsing
- Standard library only for core functionality

Install with:
```bash
pip install pyyaml
```

## Notes

- All tests use `pii.key` from project root
- Test outputs and generated input files are gitignored
- Slow models (transformers, GLiNER) can be skipped with `--quick`
- Random seed can be set for reproducible test data generation
