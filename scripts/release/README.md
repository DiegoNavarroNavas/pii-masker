# Release Scripts

These scripts support public packaging and manual companion-host installation across platforms.

## Directory layout

- `scripts/release/windows/`
- `scripts/release/macos/`
- `scripts/release/linux/`

Each platform directory provides:

- `build_host.*`: Build a standalone native host binary with PyInstaller.
- `package_portable.*`: Package build output into a distributable archive.
- `install_native_host.*`: Register browser native messaging host manifest.
- `generate_key.*`: Create a new encryption key file for extension settings.

Linux also provides:

- `setup_runtime.sh`: Install runtime dependencies for transformers in `cpu`, `nvidia`, or `auto` mode.
- `setup_flatpak_runtime.sh`: Install runtime dependencies into Flatpak browser Python (`chrome`, `chromium`, or `brave`).
- `install_native_host.sh`: Auto-selects standard or Flatpak native-messaging paths for `chrome`, `chromium`, and `brave`.

## Notes

- Build scripts are for maintainers creating release artifacts.
- Install/key scripts are for end users using companion app packages or portable archives.

## CI workflow

GitHub Actions workflow:

- `.github/workflows/release-native-host.yml`

Behavior:

- Pull requests and pushes to `main`: build and upload native-host + extension artifacts.
- Tag pushes like `v1.2.3`: build artifacts and publish them as GitHub release assets.
