# PII Masker

A privacy-first tool for anonymizing and deanonymizing text using Microsoft Presidio with unique, encrypted placeholders.

## Overview

PII Masker replaces personally identifiable information (PII) in text with unique placeholders like `<PERSON_1>`, `<LOCATION_2>`, while maintaining a secure mapping for later restoration. The mapping uses AES encryption, ensuring that only holders of the encryption key can restore the original text.

### Features

- **Multi-language support**: English, Spanish, French, German, Italian, Portuguese, Chinese, Japanese, Korean
- **Multiple NLP engines**: spaCy, Stanza, Transformers, SimpleNlpEngine (tokenization only)
- **GLiNER support**: Zero-shot multilingual PII detection without downloading ML models
- **Local Multihead engine**: Custom ModernBERT-based span classifier for offline PII detection
- **Chrome extension**: Browser-based file upload PII redaction via native messaging
- **Reversible anonymization**: Encrypted mappings allow secure restoration
- **Consistent placeholders**: Same entity gets the same placeholder throughout the document
- **Custom recognizers**: Add your own pattern recognizers via YAML
- **Built-in presets**: Quick start with optimized configurations for common use cases
- **Config file support**: Fine-tune Presidio parameters via YAML configuration

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pii_masker.git
cd pii_masker

# Install dependencies with uv
uv sync
```

### spaCy Models (optional)

For spaCy-based presets, download the required models:

```bash
# English (large)
uv run spacy download en_core_web_lg

# Additional languages
uv run spacy download de_core_news_lg  # German
uv run spacy download it_core_news_lg  # Italian
uv run spacy download fr_core_news_lg  # French
```

## Quick Start

```bash
# Generate an encryption key (creates pii.key by default)
pii_masker generate-key

# Anonymize with a preset
pii_masker anonymize -c english-fast -i document.txt -o result

# Deanonymize using the mapping file
pii_masker deanonymize -i result_masked.txt -m result_mapping.json -o restored.txt
```

## Usage

### Generate an Encryption Key

```bash
# Generate to default location (pii.key)
pii_masker generate-key

# Generate to custom location
pii_masker generate-key -k custom.key
```

### Anonymize Text

```bash
# Using a built-in preset
pii_masker anonymize -c english-fast -i document.txt -o result

# Using GLiNER (zero-shot, no model download)
pii_masker anonymize -c gliner -i document.txt -o result

# Using a custom config file
pii_masker anonymize -c legal.yaml -i document.txt -o result

# With explicit key file
pii_masker anonymize -c german -i document.txt -o result -k custom.key

# Piped input/output
cat document.txt | pii_masker anonymize -c english-fast > masked.txt
```

### Deanonymize Text

```bash
# Deanonymize (mapping file is required)
pii_masker deanonymize -i masked.txt -m mapping.json -o restored.txt

# With custom key file
pii_masker deanonymize -i masked.txt -m mapping.json -k custom.key -o restored.txt
```

## CLI Commands

### `generate-key`

Generate a new 256-bit encryption key file.

```bash
pii_masker generate-key [-k <key_file>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-k, --key-file` | `pii.key` | Path for the new encryption key file |

### `anonymize`

Anonymize text by replacing PII with placeholders.

```bash
pii_masker anonymize [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-c, --config` | auto-discover | Config file path or built-in preset name |
| `-i, --input` | stdin | Input file |
| `-o, --output` | stdout | Output file prefix |
| `-k, --key-file` | `pii.key` | Path to encryption key file |

### `deanonymize`

Restore anonymized text using the mapping file.

```bash
pii_masker deanonymize [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-i, --input` | stdin | Input file |
| `-m, --mapping` | required | Mapping JSON file |
| `-k, --key-file` | `pii.key` | Path to encryption key file |
| `-o, --output` | stdout | Output file path |

### `benchmark`

Benchmark PII detection against standard datasets.

```bash
pii_masker benchmark --dataset <name> -c <config> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--dataset, -d` | required | Dataset to benchmark |
| `-c, --config` | required | Config preset or path (comma-separated for comparison) |
| `--max-samples, -n` | all | Maximum samples to evaluate |
| `--locale, -l` | all | Filter by locale/language (e.g., `de`, `en`) |
| `--domain` | all | Filter by domain (e.g., `finance`, `code`) |
| `--filter, -f` | none | Custom filter as `field=value` (repeatable) |
| `--output, -o` | stdout | Output file for JSON results |
| `--split, -s` | train | Dataset split to use |
| `--list-fields` | - | List available fields in dataset |

#### Benchmark Examples

```bash
# List available fields in a dataset
pii_masker benchmark --dataset <dataset_name> --list-fields

# Quick test with limited samples
pii_masker benchmark --dataset <dataset_name> -c gliner --max-samples 100

# Benchmark German locale only
pii_masker benchmark --dataset <dataset_name> -c german --locale de

# Compare multiple configs
pii_masker benchmark --dataset <dataset_name> -c gliner,english-fast --max-samples 500

# Save results to JSON
pii_masker benchmark --dataset <dataset_name> -c gliner --output results.json
```

#### Benchmark Output

```
============================================================
Benchmark Results: <dataset_name>
Config: gliner
============================================================
Samples: 500

Overall Metrics:
  Precision: 0.8523
  Recall:    0.7891
  F1 Score:  0.8196

Per-Entity Metrics:
  Entity                Precision     Recall         F1  Support
  ------------------------------------------------------------
  PERSON                   0.9123     0.8845     0.8982      245
  EMAIL_ADDRESS            0.9891     0.9756     0.9823      128
  PHONE_NUMBER             0.7823     0.6542     0.7128       89
  ...
============================================================
```

## Built-in Presets

| Name | Engine | Description |
|------|--------|-------------|
| `english-fast` | spaCy | Quick English processing with en_core_web_lg |
| `english-accurate` | transformers | High-accuracy English with XLM-RoBERTa |
| `german` | transformers | German text with XLM-RoBERTa |
| `multilingual` | transformers | Multi-language documents |
| `gliner` | simple + GLiNER | Zero-shot multilingual PII detection |
| `local_multihead_en` | local_multihead | ModernBERT-based span classifier for English |

```bash
# Use built-in preset
pii_masker anonymize -c gliner -i input.txt -o result
```

## Local Multihead Engine

The `local_multihead` engine uses a custom ModernBERT-based span classifier for offline PII detection. This bypasses Presidio entirely and provides a self-contained inference pipeline.

### Entity Types

The local multihead model detects the following entity types:
- `PERSON`, `ORG`, `ADDRESS`, `EMAIL`, `PHONE`
- `USERNAME`, `PASSWORD`, `IP_ADDRESS`, `IBAN`
- `CREDIT_CARD`, `ID_NUMBER`, `ACCOUNT_NUMBER`, `OTHER`

### Usage

```bash
# Ensure model is available (Git LFS)
git lfs pull

# Anonymize with local multihead
pii_masker anonymize -c configs/local_multihead_en.yaml -i document.txt -o result
```

### Configuration

```yaml
# configs/local_multihead_en.yaml
name: local_multihead_en
description: Local ModernBERT multihead span classifier
engine: local_multihead
model: local_models/multihead_model.pt
local_encoder_model: answerdotai/ModernBERT-base
language: en
```

## Chrome Extension

PII Masker includes a Chrome extension for browser-based file redaction via native messaging.

### Installation

1. **Build the native host executable** (Windows):
   ```powershell
   cd native_host
   ./build_host_exe.ps1
   ./install_chrome_host.ps1
   ```

2. **Load the extension**:
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" and select the `chrome_extension/` folder

### Usage

1. Click the extension icon in Chrome
2. Select a file (supports `.txt`, `.md`, `.csv`, `.json`, `.pdf`)
3. Choose the PII detection engine
4. Click "Redact File" to process
5. The redacted file downloads automatically

### Supported File Types

| Type | Extensions | MIME Types |
|------|------------|------------|
| Text | `.txt`, `.md`, `.csv`, `.json` | `text/*`, `application/json` |
| PDF | `.pdf` | `application/pdf` |

### Native Host Protocol

See [native_host/PROTOCOL.md](native_host/PROTOCOL.md) for the native messaging protocol specification.

## JSON Mode (Native Host Integration)

PII Masker supports a JSON mode for programmatic integration with the Chrome extension and other tools.

### Usage

```bash
# Anonymize via JSON mode
echo '{"action":"anonymize","text":"John Smith","engine":"spacy","key_file":"pii.key"}' | \
  pii_masker anonymize --json

# Deanonymize via JSON mode
echo '{"action":"deanonymize","text":"<PERSON_1>","mapping":{"<PERSON_1>":{"entity_type":"PERSON","encrypted":"..."}},"key_file":"pii.key"}' | \
  pii_masker anonymize --json
```

### Request Format

```json
{
  "action": "anonymize",
  "text": "John Smith lives in Berlin",
  "language": "en",
  "engine": "spacy",
  "key_file": "pii.key"
}
```

### Response Format

**Success:**
```json
{
  "ok": true,
  "action": "anonymize",
  "masked_text": "<PERSON_1> lives in <LOCATION_1>",
  "mapping": {
    "<PERSON_1>": {"entity_type": "PERSON", "encrypted": "..."},
    "<LOCATION_1>": {"entity_type": "LOCATION", "encrypted": "..."}
  },
  "language": "en"
}
```

**Error:**
```json
{
  "ok": false,
  "error": {
    "code": "KEY_FILE_NOT_FOUND",
    "message": "Key file not found: pii.key"
  }
}
```

### Exit Codes

| Code | Constant | Description |
|------|----------|-------------|
| 0 | `EXIT_SUCCESS` | Success |
| 2 | `EXIT_INVALID_REQUEST` | Invalid JSON or missing required fields |
| 3 | `EXIT_KEY_FILE_ERROR` | Key file not found or unreadable |
| 4 | `EXIT_INPUT_ERROR` | Invalid input text or mapping |
| 5 | `EXIT_PROCESSING_ERROR` | Anonymization/deanonymization failed |
| 6 | `EXIT_DEPENDENCY_ERROR` | Missing dependencies or model initialization failed |

## Configuration Files

For fine-grained control, create a YAML configuration file. If `pii_masker.yaml` exists in the current directory, it will be automatically used.

### Minimal Config with GLiNER

```yaml
# pii_masker.yaml
language: en

nlp_configuration:
  nlp_engine_name: simple

recognizers:
  - name: GLiNERRecognizer
    model_path: knowledgator/gliner-pii-edge-v1.0
    map_location: cpu
    default_score: 0.7
```

### Full Config with Transformers

```yaml
# pii_masker.yaml
language: en

nlp_configuration:
  nlp_engine_name: transformers
  models:
    - lang_code: en
      model_name:
        spacy: en_core_web_sm
        transformers: FacebookAI/xlm-roberta-large-finetuned-conll03-english
  ner_model_configuration:
    aggregation_strategy: max
    alignment_mode: expand
    default_score: 0.85
```

### Auto-Discovery

If `pii_masker.yaml` exists in the current directory, it will be automatically loaded:

```bash
# Auto-loads ./pii_masker.yaml if present
pii_masker anonymize -i input.txt -o result
```

## Custom Recognizers

Add custom pattern recognizers for domain-specific PII directly in your config file:

```yaml
# pii_masker.yaml
language: en

nlp_configuration:
  nlp_engine_name: spacy
  models:
    - lang_code: en
      model_name: en_core_web_lg

recognizers:
  - name: CaseNumber
    supported_entity: CASE_ID
    supported_language: en
    patterns:
      - name: case_pattern
        regex: "\\d{4}-\\d{4}"
        score: 0.9

  - name: MedicalRecord
    supported_entity: MRN
    supported_language: en
    patterns:
      - name: mrn_pattern
        regex: "MRN-\\d{8}"
        score: 0.95
```

## Example Output

### English

![English Example](Example_Output_English.png)

### German

![German Example](Example_Output_German.png)

## Building a Standalone Executable

Use the included PyInstaller configuration:

```bash
./build.sh
```

This creates a standalone `pii-masker` executable with the spaCy model bundled.

## Tests

The project includes a comprehensive test suite that validates anonymization/deanonymization roundtrip across 24 preset/language combinations.

### Running Tests

```bash
# Generate test data (~100KB per language)
python test/scripts/generate_test_data.py

# Quick tests (fast models only)
python test/scripts/run_tests.py --quick

# Full test suite
python test/scripts/run_tests.py
```

### Latest Test Results (2026-03-14)

All 24 tests passed with perfect roundtrip verification.

#### Performance by Model Family (Total Time in seconds)

| Model | en | de | fr | it | es |
|-------|-----|-----|-----|-----|-----|
| **spaCy** (lg/sm) | 49.2 / 46.5 | - | - | - | - |
| **Stanza** | 169.8 | 142.7 | 127.9 | 147.8 | 131.6 |
| **XLM-RoBERTa** | 270.1 | 192.5 | 174.0 | 221.3 | 147.5 |
| **GLiNER** | 431.8 | 329.3 | 276.3 | 285.0 | 293.9 |

#### Entities Detected by Model

| Model | en | de | fr | it | es |
|-------|------|------|------|------|------|
| **spaCy lg** | 1650 | - | - | - | - |
| **spaCy sm** | 1778 | - | - | - | - |
| **Stanza** | 1547 | 428 | 331 | 291 | 166 |
| **XLM-RoBERTa** | 1201 | 1122 | 862 | 837 | 696 |
| **GLiNER** | 1871 | 1533 | 1357 | 1442 | 1397 |

### Key Findings

**Speed:**
- **Fastest:** spaCy (46-49s for English only) and Stanza (127-170s)
- **Slowest:** GLiNER (276-432s) and XLM-RoBERTa (147-270s)

**Entity Detection:**
- **Most entities:** GLiNER finds the most PII across all languages (1357-1871)
- **Least entities:** Stanza finds significantly fewer entities in non-English (166-428)
- **Best balance:** XLM-RoBERTa - good entity count (696-1201) with moderate multilingual speed

### Recommendations

| Use Case | Recommended Model | Rationale |
|----------|-------------------|-----------|
| English-only, speed priority | spaCy sm | 46.5s, 1778 entities |
| English-only, accuracy priority | GLiNER | 431.8s, 1871 entities |
| Multilingual, speed priority | Stanza | 127-170s, 166-1547 entities |
| Multilingual, accuracy priority | GLiNER | 276-329s, 1357-1533 entities |

See [test/README.md](test/README.md) for detailed test infrastructure documentation.

## Adding Benchmark Datasets

To add a new benchmarking dataset:

### 1. Create a Loader

Create `benchmark/loaders/my_dataset.py`:

```python
from benchmark.loaders.base import BenchmarkSample, DatasetLoader, FilterSpec

class MyDatasetLoader(DatasetLoader):
    def __init__(self, split: str = "train", filters: FilterSpec | None = None):
        super().__init__(filters)
        self.split = split

    def name(self) -> str:
        return "my_dataset"

    def load(self, max_samples: int | None = None) -> list[BenchmarkSample]:
        # Load from HuggingFace, local files, etc.
        # Return list of BenchmarkSample(text=..., ground_truth=[{entity_type, start, end}, ...])
        pass

    def list_fields(self) -> dict[str, list[str] | str]:
        # Return available fields for filtering
        pass
```

### 2. Register the Loader

Edit `benchmark/cli.py`:

```python
from benchmark.loaders.my_dataset import MyDatasetLoader

DATASET_LOADERS = {
    "my_dataset": MyDatasetLoader,
}
```

### 3. Add Entity Mappings (Optional)

If the dataset uses custom entity types, add mappings to `benchmark/entity_normalizer.py`:

```python
MY_DATASET_TO_COARSE = {
    "person_name": "PERSON",
    "email": "EMAIL_ADDRESS",
    # ...
}
```

### 4. Test

```bash
python pii_masker.py benchmark --dataset my_dataset --list-fields
python pii_masker.py benchmark --dataset my_dataset -c configs/gliner_en.yaml
```

## License

MIT License

## Acknowledgments

- [Microsoft Presidio](https://github.com/microsoft/presidio) - PII detection and anonymization
- [spaCy](https://spacy.io/) - Industrial-strength NLP
- [GLiNER](https://github.com/urchade/GLiNER) - Zero-shot NER for PII detection
