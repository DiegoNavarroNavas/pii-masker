# PII Masker

A privacy-first tool for anonymizing and deanonymizing text using Microsoft Presidio with unique, encrypted placeholders.

## Overview

PII Masker replaces personally identifiable information (PII) in text with unique placeholders like `<PERSON_1>`, `<LOCATION_2>`, while maintaining a secure mapping for later restoration. The mapping uses AES encryption, ensuring that only holders of the encryption key can restore the original text.

### Features

- **Multi-language support**: English, Spanish, French, German, Italian, Portuguese, Chinese, Japanese, Korean
- **Multiple NLP engines**: spaCy, Stanza, Transformers
- **Reversible anonymization**: Encrypted mappings allow secure restoration
- **Consistent placeholders**: Same entity gets the same placeholder throughout the document
- **Custom recognizers**: Add your own pattern recognizers via YAML or CLI

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pii_masker.git
cd pii_masker

# Install dependencies with uv
uv sync
```

### spaCy Models

```bash
# English (large)
uv run spacy download en_core_web_lg

# Additional languages
uv run spacy download de_core_news_lg  # German
uv run spacy download it_core_news_lg  # Italian
uv run spacy download fr_core_news_lg  # French
```

## Usage

### Generate an Encryption Key

```bash
python pii_masker.py --generate-key --key-file secret.key
```

### Anonymize Text

```bash
# Basic usage
python pii_masker.py --input document.txt --output result --key-file secret.key

# With German text
python pii_masker.py --input german.txt --output result --key-file secret.key --language de

# Using transformers engine for better accuracy
python pii_masker.py --input text.txt --output result --key-file secret.key --engine transformers
```

### Deanonymize Text

```bash
python pii_masker.py --mode deanonymize \
    --input result_masked.txt \
    --mapping result_mapping.json \
    --key-file secret.key \
    --output restored.txt
```

### Custom Recognizers

Add custom pattern recognizers for domain-specific PII:

```bash
# Via JSON string
python pii_masker.py --input text.txt --output out --key-file secret.key \
    --recognizer '{"name": "ZipCode", "supported_entity": "ZIP", "supported_language": "en", "patterns": [{"name": "zip", "regex": "\\\\d{5}", "score": 0.8}]}'

# Via YAML file
python pii_masker.py --input text.txt --output out --key-file secret.key \
    --recognizers-yaml custom_recognizers.yaml
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--mode` | `anonymize` or `deanonymize` (default: anonymize) |
| `--generate-key` | Generate a new encryption key file |
| `--key-file` | Path to encryption key file (required) |
| `--input` | Input text file (reads from stdin if not specified) |
| `--output` | Output file prefix (anonymize) or path (deanonymize) |
| `--mapping` | Mapping JSON file (required for deanonymize) |
| `--language` | Language code: en, es, fr, de, it, pt, zh, ja, ko (default: en) |
| `--engine` | NLP engine: spacy, stanza, transformers (default: spacy) |
| `--model` | Model name (for transformers: `spacy_model:transformer_model`) |
| `--spacy-model` | spaCy model for tokenization (transformers only) |
| `--transformer-model` | Transformer NER model (transformers only) |
| `--ner-config` | JSON string with NER configuration |
| `--recognizers-yaml` | YAML file with custom recognizers |
| `--recognizer` | JSON string defining a custom recognizer (can repeat) |
| `--json-mode` | Read request JSON from stdin and return response JSON on stdout |

### JSON API Mode (for Native Integrations)

`--json-mode` enables machine-readable stdin/stdout integration for callers like a browser native host.

Example request:

```bash
echo '{"action":"anonymize","text":"John lives in Berlin","language":"en","engine":"spacy","key_file":"secret.key"}' \
  | python pii_masker.py --json-mode
```

Example success response:

```json
{
  "ok": true,
  "action": "anonymize",
  "masked_text": "<PERSON_1> lives in <LOCATION_1>",
  "mapping": {
    "<PERSON_1>": ["PERSON", "<encrypted>"],
    "<LOCATION_1>": ["LOCATION", "<encrypted>"]
  },
  "language": "en"
}
```

## Chrome Extension + Native Host (Local)

This repository includes a v1 Chrome extension and native host bridge for **manual redact-before-upload** flows.

- Extension path: `chrome_extension/`
- Native host path: `native_host/`
- Protocol spec: `native_host/PROTOCOL.md`

### Supported v1 file types

- PDF (`.pdf`)
- Text formats (`.txt`, `.md`, `.csv`, `.json`)

### Important behavior

- Data stays local: Chrome extension -> native host -> local `pii_masker.py`.
- v1 PDF output is a clean re-rendered PDF from extracted text (layout is not preserved).
- Non-UTF-8 text files are rejected with an explicit error.

### Setup Steps (Windows + Chrome)

1. Install dependencies and models (same as CLI setup).
2. Load extension:
   - Open `chrome://extensions`
   - Enable Developer mode
   - Click "Load unpacked"
   - Select the `chrome_extension` directory
3. Register native host:
   - Copy extension ID from `chrome://extensions`
   - Run:

```powershell
.\native_host\install_chrome_host.ps1 -ExtensionId "<your_extension_id>"
```

4. In extension popup, set:
   - `Key file path` (for example `C:\Users\franc\Documents\GitHub\pii-masker\secret.key`)
   - `Language` and `Engine`
5. On a webpage upload field:
   - Click the file input and choose a file
   - Open the extension popup
   - Click **Redact Selected Upload**

### Native Host command

By default, native host executes:

```bash
uv run python pii_masker.py --json-mode
```

Override with environment variable `PII_MASKER_CMD` if needed.

### Running tests

```bash
python -m unittest discover -s tests -p "test_*.py"
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

## License

MIT License

## Acknowledgments

- [Microsoft Presidio](https://github.com/microsoft/presidio) - PII detection and anonymization
- [spaCy](https://spacy.io/) - Industrial-strength NLP
