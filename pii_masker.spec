# pii_masker.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

# Find spaCy model location
import en_core_web_lg
import presidio_analyzer
model_pkg_path = Path(en_core_web_lg.__path__[0])
# The actual model data is in en_core_web_lg-3.8.0 subdirectory
model_path = model_pkg_path / "en_core_web_lg-3.8.0"
presidio_path = Path(presidio_analyzer.__file__).parent

a = Analysis(
    ['pii_masker.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle spaCy model
        (str(model_path), 'en_core_web_lg'),
        # Bundle presidio config files
        (str(presidio_path / 'conf'), 'presidio_analyzer/conf'),
        # Required metadata for some packages
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
    upx=True,  # Compress with UPX if available
    console=True,
    onefile=True,
)
