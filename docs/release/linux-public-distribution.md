# Linux Public Installation

This guide is for end users installing the public extension + companion host on Linux.

The steps below were validated on a Linux host using the current release artifacts in this repository.

## What users install

1. Browser extension from a store listing.
2. Companion archive (`pii-masker-native-host-linux.tar.gz`), either from GitHub Releases or built locally, see below.

## Prerequisites

- `bash`
- `tar`
- `python3` (or `python`) for local build from source
- `node` + `npm` for Puppeteer-based extension diagnostic (optional)

## Transformers runtime mode (CPU or NVIDIA)

If you are running from a repository checkout and want Transformers support, install
runtime dependencies with an explicit mode:

```bash
bash ./scripts/release/linux/setup_runtime.sh auto
```

Modes:

- `auto`: uses NVIDIA mode when `nvidia-smi` is available; otherwise CPU mode.
- `cpu`: installs CPU-only PyTorch wheels (recommended for non-NVIDIA laptops, including AMD laptops without ROCm).
- `nvidia`: installs NVIDIA CUDA wheels.

The setup script recreates `.venv` using `venv --copies` (not symlinks) so
browser-launched native host processes can reliably execute the same interpreter.

## Install steps (portable archive flow)

1. Install extension from store.
2. Get the Linux companion archive (`pii-masker-native-host-linux.tar.gz`) using one of:
   - Download from GitHub Releases, or
   - Generate locally from source (see "Generate portable archive from source" below).
3. Extract the archive:

```bash
mkdir -p "$HOME/.local/share/pii-masker"
tar -xzf pii-masker-native-host-linux.tar.gz -C "$HOME/.local/share/pii-masker"
cd "$HOME/.local/share/pii-masker"
```

4. Get extension ID from browser extension details.
5. Register native host:

```bash
bash ./helpers/install_native_host.sh \
  "./bin/host" \
  "<store_extension_id>" \
  chrome
```

Use `chromium`, `edge`, or `brave` for non-Chrome browsers.
6. Generate key (if missing):

```bash
bash ./helpers/generate_key.sh "$HOME/.pii-masker/secret.key"
```

7. In the extension popup:
   - Run **Diagnose Native Host** (should succeed).
   - Set `Key file path` to the same path used above (for example `~/.pii-masker/secret.key`).
   - Save settings and test with a `.txt` upload first.

## Local install from source (no archive packaging)

Use this flow when you are installing on the same machine where you have the repository checkout.

```bash
bash ./scripts/release/linux/build_host.sh
bash ./scripts/release/linux/install_native_host.sh "./results/release/linux/bin/host" "<store_extension_id>" chrome
bash ./scripts/release/linux/generate_key.sh "$HOME/.pii-masker/secret.key"
```

Use `chromium`, `edge`, or `brave` for non-Chrome browsers.

Then in the extension popup:

- Run **Diagnose Native Host** (should succeed).
- Set `Key file path` to the same path used above (for example `~/.pii-masker/secret.key`).

If you will run the masker runtime from this same repository checkout, set runtime mode:

```bash
bash ./scripts/release/linux/setup_runtime.sh auto
```

## Generate portable archive from source (alternative to download)

If the release archive is not available, generate it from this repository:

```bash
bash ./scripts/release/linux/build_host.sh
bash ./scripts/release/linux/package_portable.sh
```

`build_host.sh` uses a minimal isolated build environment (`results/release/linux/build-venv`)
and installs only `pyinstaller`, so it does not install runtime-heavy GPU/CUDA dependencies.

Generated archive path:

```bash
results/release/pii-masker-native-host-linux.tar.gz
```

Then either:

- Copy that file to the install machine and continue from extraction step above, or
- Run extraction/install steps directly on the same machine.

If you will also run the masker runtime from this same repository checkout, set runtime mode:

```bash
bash ./scripts/release/linux/setup_runtime.sh auto
```

## Build/package commands (maintainers)

```bash
bash ./scripts/release/linux/build_host.sh
bash ./scripts/release/linux/package_portable.sh
```

## Known-good Flatpak Chrome flow (copy/paste)

Use this when Chrome is installed as Flatpak (`com.google.Chrome`):

```bash
# 1) Build host from source checkout
bash ./scripts/release/linux/build_host.sh

# 2) Register native host for your extension ID
bash ./scripts/release/linux/install_native_host.sh \
  "./results/release/linux/bin/host" \
  "<store_extension_id>" \
  chrome

# 3) Create key in Flatpak-visible path
bash ./scripts/release/linux/generate_key.sh \
  "$HOME/.var/app/com.google.Chrome/config/google-chrome/pii-masker/secret.key"

# 4) Install runtime deps inside Flatpak Chrome Python
bash ./scripts/release/linux/setup_flatpak_runtime.sh chrome auto
```

In extension popup settings:

- `Key file path`:
  `/home/<user>/.var/app/com.google.Chrome/config/google-chrome/pii-masker/secret.key`
- Run **Diagnose Native Host**.

## Verification checklist

- Popup diagnose succeeds.
- `.txt` and `.pdf` redaction work.
- Upgrading companion package keeps native host registration valid.

## Troubleshooting

- Host not found
  - Re-run `install_native_host.sh` with the correct host path and extension ID.
  - Verify browser target: native host manifests are browser-specific.
  - For Flatpak browsers, manifests are installed under `~/.var/app/<app-id>/config/.../NativeMessagingHosts/`.
- Host outdated
  - Install latest companion release.
- Key file missing
  - Generate key and set the same path in extension settings.
  - For Flatpak Chrome/Chromium/Brave, use a key path inside the browser app data tree, for example:
    `~/.var/app/com.google.Chrome/config/google-chrome/pii-masker/secret.key`
- `No module named 'presidio_analyzer'`
  - Rebuild runtime deps with:
    `bash ./scripts/release/linux/setup_runtime.sh auto`
  - If needed, force system Python:
    `bash ./scripts/release/linux/setup_runtime.sh auto --python /usr/bin/python3`
  - For Python 3.14+, setup falls back to `presidio-*==2.2.359` for compatibility.
  - For Flatpak Chrome/Chromium/Brave runtime, install deps into the browser sandbox Python:
    `bash ./scripts/release/linux/setup_flatpak_runtime.sh chrome auto`
- `INTERNAL_ERROR: [Errno 32] Broken pipe`
  - This can happen when the PDF runtime worker starts with a broken interpreter context.
  - Update to a build including the host env-sanitization fix, then rebuild host:
    `bash ./scripts/release/linux/build_host.sh`
  - For Flatpak browsers, also install runtime deps in sandbox Python:
    `bash ./scripts/release/linux/setup_flatpak_runtime.sh chrome auto`

### Automated diagnosis with Puppeteer (optional)

From repository root:

```bash
cd native_host
npm install
cd ..
npm --prefix native_host run puppeteer:diagnose-extension
```

What this does:

- Launches browser with unpacked extension.
- Detects runtime extension ID.
- Registers native host manifest for that ID via `scripts/release/linux/install_native_host.sh`.
- Opens extension popup and runs **Diagnose Native Host**.

If browser binary is not in a standard path, set:

```bash
PUPPETEER_EXECUTABLE_PATH=/path/to/browser \
npm --prefix native_host run puppeteer:diagnose-extension
```

By default this uses Puppeteer's managed Chrome binary (downloaded by `npm install`).
If that browser fails to start on your system, set `PUPPETEER_EXECUTABLE_PATH` to
use your installed Chrome/Chromium binary instead.

For Flatpak browsers, the diagnose script can launch them directly by browser target:

```bash
BROWSER_TARGET=chrome npm --prefix native_host run puppeteer:diagnose-extension
```

Supported targets: `chrome`, `chromium`, `brave`.

If MV3 service-worker detection is flaky on your browser build, pass extension ID directly:

```bash
EXTENSION_ID=<your_extension_id> \
BROWSER_TARGET=chrome \
npm --prefix native_host run puppeteer:diagnose-extension
```

To test against the extension already installed in your browser profile (instead of loading unpacked extension), use:

```bash
USE_INSTALLED_EXTENSION=1 \
EXTENSION_ID=<your_extension_id> \
BROWSER_TARGET=chrome \
npm --prefix native_host run puppeteer:diagnose-extension
```

When using `USE_INSTALLED_EXTENSION=1`, close all browser windows first so the profile
is not locked by another running instance.

Important: extension IDs are profile-specific by browser installation. The ID used in
Flatpak Chrome must exist under:

`~/.var/app/com.google.Chrome/config/google-chrome/Default/Extensions/`

For unpacked developer extensions, Chrome may track the extension in profile preferences
even when it is not present under `Default/Extensions`.
