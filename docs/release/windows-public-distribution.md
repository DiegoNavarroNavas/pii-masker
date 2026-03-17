# Windows Public Installation

This guide is for end users installing the public extension + companion host on Windows.

## What users install

1. Browser extension from a store listing (Chrome Web Store or Edge Add-ons).
2. Companion package from GitHub Releases (installer or portable bundle).

## Install steps (recommended installer flow)

1. Install the extension from the store.
2. Install the companion app package (`.msi` or signed `.exe`) from the matching release.
3. Open the extension popup and run **Diagnose Native Host**.
4. Set `Key file path` in popup (for example `C:\Users\<you>\.pii-masker\secret.key`).
5. If key file does not exist, generate it:

```powershell
.\scripts\release\windows\generate_key.ps1 -KeyPath "$HOME\.pii-masker\secret.key"
```

6. Save extension settings and test upload redaction on a `.txt` file first.

## Portable/manual flow (no installer)

If distributing a zip archive instead of an installer:

1. Unzip the companion package to a stable location (do not move later), for example:
   `C:\Users\<you>\AppData\Local\pii-masker\`
2. Get your extension ID from `chrome://extensions` or `edge://extensions`.
3. Register native host:

```powershell
.\helpers\install_native_host.ps1 `
  -ExtensionId "<store_extension_id>" `
  -HostExePath "C:\Users\<you>\AppData\Local\pii-masker\bin\host.exe"
```

4. Run popup **Diagnose Native Host**.
5. Generate key from package helper (if missing):

```powershell
.\helpers\generate_key.ps1 -KeyPath "$HOME\.pii-masker\secret.key"
```

## Build/package commands (maintainers)

```powershell
.\scripts\release\windows\build_host.ps1
.\scripts\release\windows\package_portable.ps1
```

## Reinstall companion from source (developer flow)

Use this when host behavior changed in source (for example new vault persistence features) and your installed companion is stale.

1. From repo root, rebuild the host executable:

```powershell
.\native_host\build_host_exe.ps1
```

2. Reinstall host registration (script auto-reuses existing extension ID when already installed):

```powershell
.\native_host\install_chrome_host.ps1
```

If this is the first install (or ID cannot be inferred), pass it once:

```powershell
.\native_host\install_chrome_host.ps1 -ExtensionId "<your_extension_id>"
```

Optional one-step rebuild + reinstall:

```powershell
.\native_host\install_chrome_host.ps1 -BuildExe
```

3. Reload the extension in browser, open popup, and run:
   - **Refresh Vault Output Path**
   - **Diagnose Native Host**

4. Validate by redacting one small `.txt` upload and confirming a new `.vault.json` appears in the shown vault output folder.

## Verification checklist

- Diagnose returns host reachable.
- Redaction works for `.txt` and `.pdf`.
- Host upgrade keeps registration intact (diagnose still succeeds).

## Troubleshooting

- `Specified native messaging host not found`
  - Re-run `install_native_host.ps1` with correct extension ID and host path.
- `Native host ... is too old`
  - Install latest companion package from latest release.
- `Key file not found`
  - Generate key using `generate_key.ps1` and update popup path.
