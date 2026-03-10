# PyInstaller Packaging Guide for PII Masker

This document summarizes the key changes and solutions required to successfully package the PII Masker application as a standalone executable using PyInstaller.

## Overview

**Goal**: Create a standalone executable that bundles Python, all dependencies, and the spaCy NLP model.

**Final Result**:
- Executable: `dist/pii-masker`
- Size: ~478MB
- Platform: Linux x86_64

---

## Dependencies

### Required Packages

```toml
[project]
dependencies = [
    "presidio-analyzer>=2.2.361",
    "presidio-anonymizer>=2.2.361",
]

[project.optional-dependencies]
dev = [
    "pyinstaller>=6.19.0",
]
```

### spaCy Model Download

The spaCy model must be downloaded before building:

```bash
uv run python -m spacy download en_core_web_lg
```

---

## Key Challenges and Solutions

### Challenge 1: Presidio Config File Paths

**Problem**: Presidio looks for configuration files using relative paths from `__file__`. In a PyInstaller bundle, `__file__` points to a temporary extraction directory, and the config files aren't found.

**Error**:
```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/_MEIxxx/presidio_analyzer/nlp_engine/../conf/default.yaml'
```

**Solution**: Avoid config file loading entirely by:
1. Creating `SpacyNlpEngine` with explicit model configuration
2. Creating `RecognizerRegistry` and adding recognizers manually instead of using `load_predefined_recognizers()`

```python
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
)

# Create NLP engine explicitly
nlp_engine = SpacyNlpEngine(models=[{"lang_code": "en", "model_name": "en_core_web_lg"}])

# Create registry with manual recognizer registration
registry = RecognizerRegistry()
registry.add_recognizer(PhoneRecognizer())
registry.add_recognizer(EmailRecognizer())
registry.add_recognizer(CreditCardRecognizer())
registry.add_recognizer(SpacyRecognizer())

# Create analyzer with explicit components
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
```

### Challenge 2: spaCy Model Bundling

**Problem**: The spaCy model is installed as a package with a nested directory structure. Simply bundling the package path doesn't include the actual model data.

**Model Structure**:
```
site-packages/en_core_web_lg/
├── __init__.py
├── meta.json
└── en_core_web_lg-3.8.0/    # <-- Actual model data is here
    ├── config.cfg
    ├── vocab/
    ├── ner/
    └── ...
```

**Solution**: Bundle the inner directory containing the actual model data:

```python
# In pii_masker.spec
import en_core_web_lg
from pathlib import Path

model_pkg_path = Path(en_core_web_lg.__path__[0])
model_path = model_pkg_path / "en_core_web_lg-3.8.0"  # Inner directory

datas = [
    (str(model_path), 'en_core_web_lg'),  # Bundle as 'en_core_web_lg'
]
```

### Challenge 3: Loading Bundled Model at Runtime

**Problem**: In the frozen environment, spaCy can't find the model by name because it's not installed as a package.

**Solution**: Detect frozen environment and load model from the bundled path:

```python
import sys
from pathlib import Path

def get_bundled_model_path():
    """Get the path to the bundled spaCy model in frozen environment."""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
        return base_path / "en_core_web_lg"
    return None

def create_nlp_engine():
    bundled_path = get_bundled_model_path()

    if bundled_path and bundled_path.exists():
        # Load from bundled path in frozen environment
        import spacy
        nlp = spacy.load(str(bundled_path))
        engine = SpacyNlpEngine()
        engine.nlp = {"en": nlp}
        return engine
    else:
        # Normal environment - use model name
        return SpacyNlpEngine(models=[{"lang_code": "en", "model_name": "en_core_web_lg"}])
```

---

## Final Configuration Files

### pii_masker.spec

```python
# pii_masker.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

# Find spaCy model location
import en_core_web_lg
import presidio_analyzer
model_pkg_path = Path(en_core_web_lg.__path__[0])
model_path = model_pkg_path / "en_core_web_lg-3.8.0"
presidio_path = Path(presidio_analyzer.__file__).parent

a = Analysis(
    ['getting_started.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle spaCy model
        (str(model_path), 'en_core_web_lg'),
        # Bundle presidio config files (optional, for reference)
        (str(presidio_path / 'conf'), 'presidio_analyzer/conf'),
        # Required metadata
        *copy_metadata('presidio-analyzer'),
        *copy_metadata('presidio-anonymizer'),
    ],
    hiddenimports=[
        'spacy',
        'en_core_web_lg',
        'presidio_analyzer',
        'presidio_anonymizer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='pii-masker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    onefile=True,
)
```

### build.sh

```bash
#!/bin/bash
set -e

echo "Building pii-masker executable..."
uv run pyinstaller pii_masker.spec --clean

echo "Build complete: dist/pii-masker"
ls -lh dist/pii-masker
```

---

## Build and Test Commands

```bash
# 1. Add PyInstaller dependency
uv add --dev pyinstaller

# 2. Download spaCy model
uv run python -m spacy download en_core_web_lg

# 3. Build
chmod +x build.sh
./build.sh

# 4. Test
./dist/pii-masker --help
./dist/pii-masker input.txt
./dist/pii-masker input.txt -o output.txt
./dist/pii-masker input.txt -e PHONE_NUMBER EMAIL_ADDRESS
```

---

## Lessons Learned

1. **Avoid runtime config file loading**: Libraries that load config files via `__file__` paths will fail in frozen environments. Use explicit configuration instead.

2. **Check model directory structure**: spaCy models have a nested structure. The actual model data is in a versioned subdirectory, not the package root.

3. **Use `sys.frozen` and `sys._MEIPASS`**: These are the standard ways to detect and locate resources in PyInstaller bundles.

4. **Manual recognizer registration**: For Presidio, manually adding recognizers avoids the need for config file discovery.

5. **Test incrementally**: Build and test frequently during development to catch bundling issues early.

---

## Troubleshooting

### Error: `Could not read config.cfg`

The model path is incorrect. Ensure you're bundling the inner `en_core_web_lg-X.X.X` directory, not the outer package directory.

### Error: `No such file or directory: .../conf/default.yaml`

Presidio can't find its config files. Use manual recognizer registration instead of `load_predefined_recognizers()`.

### Error: `cannot import name 'PersonRecognizer'`

Use `SpacyRecognizer` for person/entity detection via NER, not a dedicated `PersonRecognizer`.

### Large executable size

This is expected. The bundle includes:
- Python runtime (~50MB)
- NumPy, spaCy, Thinc, and ML dependencies (~200MB)
- spaCy model `en_core_web_lg` (~400MB)

Total: ~478MB (compressed in executable)

---

## Building for Windows via GitHub Actions

PyInstaller does **not support cross-compilation**. You cannot build a Windows `.exe` from Linux. The executable bundles platform-specific binaries (Python interpreter, DLLs, compiled extensions) that must be built on Windows.

The solution is to use GitHub Actions, which provides free Windows runners.

### Step 1: Create the Workflow File

Create `.github/workflows/build.yml`:

```yaml
name: Build Executables

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: |
          uv sync --dev
          uv run python -m spacy download en_core_web_lg

      - name: Build
        run: uv run pyinstaller pii_masker.spec --clean

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: pii-masker-linux
          path: dist/pii-masker

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: |
          uv sync --dev
          uv run python -m spacy download en_core_web_lg

      - name: Build
        run: uv run pyinstaller pii_masker.spec --clean

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: pii-masker-windows
          path: dist/pii-masker.exe
```

### Step 2: Push to GitHub

```bash
git add .github/workflows/build.yml
git commit -m "Add cross-platform build workflow"
git push
```

### Step 3: Trigger the Build

**Option A: Create a version tag**
```bash
git tag v1.0.0
git push --tags
```

**Option B: Manual trigger**
1. Go to your repository on GitHub
2. Click **Actions** tab
3. Select **Build Executables** workflow
4. Click **Run workflow**

### Step 4: Download Artifacts

After the build completes:
1. Go to **Actions** → Select the completed run
2. Scroll to **Artifacts** section
3. Download `pii-masker-linux` and/or `pii-masker-windows`

### Workflow Explanation

| Section | Purpose |
|---------|---------|
| `on: push: tags: - 'v*'` | Triggers on version tags (e.g., `v1.0.0`) |
| `on: workflow_dispatch` | Allows manual triggering from GitHub UI |
| `runs-on: ubuntu-latest` | Linux runner (free) |
| `runs-on: windows-latest` | Windows runner (free) |
| `actions/setup-python@v5` | Installs Python 3.13 |
| `astral-sh/setup-uv@v5` | Installs uv package manager |
| `actions/upload-artifact@v4` | Uploads built executables for download |

### GitHub Actions Free Tier Limits

| Resource | Limit |
|----------|-------|
| Minutes/month (free) | 2,000 minutes |
| Storage | 500MB |
| Windows minutes | 2x billing (1000 actual minutes) |

The Windows build takes ~3-5 minutes, so you can do ~200 Windows builds per month for free.

### Alternative CI/CD Services

| Service | Free Windows Minutes |
|---------|---------------------|
| GitHub Actions | 2,000 min/month |
| GitLab CI | 400 min/month |
| Azure Pipelines | 1,800 min/month |
| CircleCI | Limited free tier |
