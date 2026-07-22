# Firefox Policy Generator

A desktop/CLI application to generate, validate, and export Firefox enterprise
`policies.json` configurations. Ships as a PySide6 GUI, a headless CLI, and a
self-contained Linux AppImage.

See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for the full design.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# GUI
python -m ffpolicy

# CLI
python -m ffpolicy validate my-policies.yaml
python -m ffpolicy generate my-policies.yaml -o policies.json
python -m ffpolicy export my-policies.yaml --target system_linux
python -m ffpolicy preview my-policies.yaml
```

### Export targets

`--target` resolves to the standard Firefox policy locations for common Linux
packaging conventions (plus `custom`, which needs `--custom-path`):

| `--target`                     | Path                                          |
| ------------------------------- | ---------------------------------------------- |
| `system_linux` (default)        | `/etc/firefox/policies/policies.json`          |
| `linux_lib64_distribution`      | `/usr/lib64/firefox/distribution/policies.json` (Fedora/RHEL) |
| `linux_lib_distribution`        | `/usr/lib/firefox/distribution/policies.json` (Debian/Ubuntu) |
| `linux_firefox_esr`             | `/usr/lib/firefox-esr/distribution/policies.json` (Debian ESR) |
| `linux_opt_distribution`        | `/opt/firefox/distribution/policies.json` (manual tarball installs) |
| `linux_snap`                     | `/etc/firefox/policies/policies.json` (Firefox snap - same file as `system_linux`; the snap's read-only install dir falls back to this path) |
| `linux_flatpak_system`           | `/var/lib/flatpak/extension/org.mozilla.firefox.systemconfig/<arch>/stable/policies/policies.json` (system-wide Flatpak Firefox) |
| `linux_flatpak_user`             | `~/.local/share/flatpak/extension/org.mozilla.firefox.systemconfig/<arch>/stable/policies/policies.json` (per-user Flatpak Firefox) |
| `distribution`                  | `distribution/policies.json` (relative to cwd) |
| `custom`                        | `--custom-path` you supply                     |

Flatpak Firefox's sandbox can't see the host's `/etc`, `/usr`, or `/opt`, so
Mozilla exposes policies through a flatpak "extension" mount point instead - a
file placed at the host path above shows up inside the sandbox as
`/app/etc/firefox/policies/policies.json`. `<arch>` is the flatpak
architecture string (e.g. `x86_64`, `aarch64`), auto-detected from the host.

Every location above except `distribution`/`custom`/`linux_flatpak_user` is
root-owned, so a plain write from an unprivileged user fails. Pass `--elevate`
to retry the write via `pkexec` (preferred - triggers a PolicyKit auth dialog)
or `sudo` (interactive terminal password prompt), whichever is found on `PATH`:

```bash
python -m ffpolicy export my-policies.yaml --target linux_lib64_distribution --elevate
```

Without `--elevate`, a permission error is reported with a hint to pass it or
choose a path you own.

Input files are YAML or JSON, either a bare `policy-name: value` mapping or a
`{firefox_version, policies}` wrapper - see `tests/fixtures/sample_input.yaml`.
Pass `--offline` to skip the live Mozilla schema sync and use the bundled fallback.

### Compliance presets

Bundled presets apply a known-good baseline in one step, then let you layer
your own settings on top. See [`docs/DISA_STIG.md`](docs/DISA_STIG.md) for the
DISA STIG (Mozilla Firefox) presets, one per compliance profile:

```bash
python -m ffpolicy presets                                  # list what's available
python -m ffpolicy preset-info disa_stig__mac_1_classified   # every rule's description + recommendation
python -m ffpolicy generate --preset disa_stig__mac_1_classified -o policies.json --offline
```

or apply one from the GUI's Presets menu.

## Development

```bash
make lint       # ruff + import-boundary check
make typecheck  # mypy
make test       # pytest (GUI tests run under an offscreen Qt platform)
```

## Building an AppImage

```bash
bash src/ffpolicy/packager/build_appimage.sh 0.1.0
```
