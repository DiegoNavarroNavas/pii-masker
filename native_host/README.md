# Native Host Tooling Notes

## Playwright usage

This folder contains Playwright-based helper scripts for validating the Chrome extension + native host integration on Windows.

### Install

From repository root:

```powershell
cd native_host
npm ci
```

### Run

Run from repository root (required because scripts resolve paths from the repo root):

```powershell
npm --prefix native_host run playwright:diagnose-extension
npm --prefix native_host run playwright:test-upload
npm --prefix native_host run puppeteer:diagnose-extension
```

### Script behavior

- `playwright:diagnose-extension`
  - Launches Edge with the unpacked extension.
  - Detects the runtime extension ID.
  - Registers the native host manifest for that ID via `native_host/install_chrome_host.ps1`.
  - Opens popup UI and runs "Diagnose Native Host".

- `playwright:test-upload`
  - Launches Edge with the unpacked extension.
  - Configures extension settings in service worker storage.
  - Loads `tests/upload_test.html` and selects `document.txt`.
  - Triggers redaction through the content script and checks that the selected filename becomes redacted.

- `puppeteer:diagnose-extension`
  - Linux-oriented diagnostic helper.
  - Launches Puppeteer's managed Chrome, or a Flatpak browser wrapper when available.
  - Detects runtime extension ID and registers manifest via `scripts/release/linux/install_native_host.sh`.
  - Opens popup UI and runs "Diagnose Native Host".
  - Set `BROWSER_TARGET=chrome|chromium|brave` to force Flatpak browser target.
  - Set `EXTENSION_ID=<id>` to skip service-worker ID detection when needed.
  - Set `USE_INSTALLED_EXTENSION=1` to diagnose a store-installed extension in your existing browser profile.

For Flatpak browsers, runtime dependencies for `pii_masker.py` should be installed with:

```bash
bash ./scripts/release/linux/setup_flatpak_runtime.sh chrome auto
```

### Preconditions

- Edge installed (scripts launch Playwright with `channel: "msedge"`).
- `secret.key` exists at repository root.
- `document.txt` exists at repository root.
- Native host build/register scripts available under `native_host/`.
