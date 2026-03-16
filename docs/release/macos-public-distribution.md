# macOS Public Installation

This guide is for end users installing the public extension + companion host on macOS.

## What users install

1. Browser extension from a store listing.
2. Companion package from GitHub Releases (`.pkg` preferred, `.tar.gz` portable fallback).

## Install steps (recommended pkg flow)

1. Install extension from store.
2. Install companion `.pkg` from release.
3. Open extension popup and run **Diagnose Native Host**.
4. Set `Key file path` in popup (for example `~/.pii-masker/secret.key`).
5. If key file does not exist, generate it:

```bash
./scripts/release/macos/generate_key.sh "$HOME/.pii-masker/secret.key"
```

6. Save settings and test with a `.txt` upload first.

## Portable/manual flow (no pkg)

1. Extract companion archive to a stable path, for example:
   `~/Applications/pii-masker/`
2. Get extension ID from browser extension details.
3. Register native host manifest:

```bash
./helpers/install_native_host.sh \
  "$HOME/Applications/pii-masker/bin/host" \
  "<store_extension_id>" \
  chrome
```

Use `edge` or `chromium` instead of `chrome` when needed.
4. Generate key from package helper (if missing):

```bash
./helpers/generate_key.sh "$HOME/.pii-masker/secret.key"
```

## Build/package commands (maintainers)

```bash
./scripts/release/macos/build_host.sh
./scripts/release/macos/package_portable.sh
```

## Verification checklist

- Diagnose succeeds from popup.
- `.txt` and `.pdf` redaction complete successfully.
- Upgrade to newer companion package preserves working diagnose status.

## Troubleshooting

- Host not found
  - Re-run `install_native_host.sh` and confirm extension ID.
- Host outdated
  - Install latest companion release package.
- Key file missing
  - Generate key and ensure popup points to correct path.
