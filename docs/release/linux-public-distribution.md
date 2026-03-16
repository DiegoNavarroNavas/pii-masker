# Linux Public Installation

This guide is for end users installing the public extension + companion host on Linux.

## What users install

1. Browser extension from a store listing.
2. Companion package from GitHub Releases (`.deb`/`.rpm` preferred, `.tar.gz` portable fallback).

## Install steps (recommended package flow)

1. Install extension from store.
2. Install companion package from release.
3. Open extension popup and run **Diagnose Native Host**.
4. Set `Key file path` (for example `~/.pii-masker/secret.key`).
5. If key file does not exist, generate it:

```bash
./scripts/release/linux/generate_key.sh "$HOME/.pii-masker/secret.key"
```

6. Save settings and test with a `.txt` upload first.

## Portable/manual flow (no system package)

1. Extract companion archive to a stable path, for example:
   `~/.local/share/pii-masker/`
2. Get extension ID from browser extension details.
3. Register native host:

```bash
./helpers/install_native_host.sh \
  "$HOME/.local/share/pii-masker/bin/host" \
  "<store_extension_id>" \
  chrome
```

Use `chromium` or `edge` for non-Chrome browsers.
4. Generate key from package helper (if missing):

```bash
./helpers/generate_key.sh "$HOME/.pii-masker/secret.key"
```

## Build/package commands (maintainers)

```bash
./scripts/release/linux/build_host.sh
./scripts/release/linux/package_portable.sh
```

## Verification checklist

- Popup diagnose succeeds.
- `.txt` and `.pdf` redaction work.
- Upgrading companion package keeps native host registration valid.

## Troubleshooting

- Host not found
  - Re-run `install_native_host.sh` with the correct host path and extension ID.
- Host outdated
  - Install latest companion release.
- Key file missing
  - Generate key and set the same path in extension settings.
