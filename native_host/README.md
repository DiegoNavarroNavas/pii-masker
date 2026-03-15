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

### Preconditions

- Edge installed (scripts launch Playwright with `channel: "msedge"`).
- `secret.key` exists at repository root.
- `document.txt` exists at repository root.
- Native host build/register scripts available under `native_host/`.
