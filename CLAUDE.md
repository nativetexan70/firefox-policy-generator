# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**fedora-policy-generator** (package name `ffpolicy`) is a Python desktop/CLI application
that generates, validates, and manages Firefox enterprise `policies.json` configurations. It
ships as a PySide6 GUI, a headless CLI, and a self-contained Linux AppImage. See
`docs/IMPLEMENTATION_PLAN.md` for the full design blueprint this codebase follows.

## Development Commands

```bash
# Install (editable, with dev extras)
pip install -e ".[dev]"

# Run the GUI
python -m ffpolicy

# Run the CLI (any args route to cli.py instead of the GUI)
python -m ffpolicy validate tests/fixtures/sample_input.yaml --offline
python -m ffpolicy generate tests/fixtures/sample_input.yaml -o policies.json --offline
python -m ffpolicy export tests/fixtures/sample_input.yaml --target custom --custom-path ./out --offline
python -m ffpolicy preview tests/fixtures/sample_input.yaml

# Test (GUI tests need an offscreen Qt platform in headless/CI environments)
QT_QPA_PLATFORM=offscreen pytest
QT_QPA_PLATFORM=offscreen pytest tests/unit/test_validator.py -k test_force_installed_requires_install_url

# Lint / type-check / import-boundary check
ruff check src tests
mypy src
lint-imports          # enforces core/models never importing gui (setup.cfg)

# Regenerate the golden-file fixture after an intentional output-format change
make update-golden

# Build a Linux AppImage (requires appimagetool on PATH)
bash src/ffpolicy/packager/build_appimage.sh 0.1.0
```

Headless environments are missing Qt's runtime `.so`s by default even for offscreen
rendering; without them PySide6 imports abort with `libEGL.so.1`/`libxcb-cursor.so.0`
errors. Install `libegl1 libgl1 libxkbcommon0 libxcb-cursor0 libxcb-image0
libxcb-render-util0 libxcb-util1` (already handled in `.github/workflows/build.yml`).

## Architecture

```
src/ffpolicy/
├── core/       # Pure logic: generator, validator, version_check, paths, errors.
│               # NEVER imports gui/ or PySide6 - enforced by lint-imports.
├── models/     # Pydantic models: policy_schema (parsed Mozilla schema),
│               # policy_document (user's working set), extension, amo.
├── fetchers/   # Network + disk cache: base (HTTP/ETag), cache (TTL disk cache),
│               # schema_sync (Mozilla policy-templates -> PolicySchema),
│               # amo_client (addons.mozilla.org search/detail).
├── gui/        # PySide6 UI - depends only on core/ + models/, never the reverse.
├── resources/  # Bundled schema_backup.json + categories.yaml (offline fallback),
│               # presets/*.yaml (compliance baselines, e.g. disa_stig.yaml).
├── packager/   # ffpolicy.spec (PyInstaller), build_appimage.sh, .desktop, icon.
├── cli.py      # Typer CLI: validate / generate / export / preview.
└── __main__.py # Dispatches to cli.py when argv has args, else the GUI.
```

**Dependency-flow rule:** `gui` -> `core` + `models`; `fetchers` -> `models`; `core` and
`models` must never import `gui` or `PySide6`. This is what keeps the CLI and unit tests
fast and headless, and it's mechanically enforced by `lint-imports` (config in
`setup.cfg`), not just convention.

**Schema fallback chain** (`fetchers/schema_sync.sync_schema`): live fetch of Mozilla's
`schema.json` + `README.md` -> ETag-cached disk copy -> bundled
`resources/schema_backup.json`. Every call returns `(schema, tier)` so callers (CLI,
GUI status bar) can report which tier was used. `load_bundled_schema()` skips network
entirely for `--offline` CLI runs and tests.

**Deterministic output:** `core/generator.render_policies_json` always sorts keys, so the
same `PolicyDocument` produces byte-identical `policies.json` - this is asserted by the
golden-file test (`tests/functional/test_golden.py` vs `tests/fixtures/golden/`).
Regenerate the golden file only for an intentional format change, via `make update-golden`.

**Form building** (`gui/widgets/field_widgets.build_field_editor`): recursively maps a
`PolicyField` tree to editor widgets by `ValueType` (bool/string/int/enum/url -> plain
widgets, object -> recurses into a group box, array -> add/remove rows). A wildcard-keyed
object child (`key == "*"`, e.g. `ExtensionSettings`) falls back to a raw JSON editor
instead of trying to synthesize a fixed-field form - `ExtensionSettings` itself gets a
dedicated `gui/extension_manager.py` (AMO search + table) instead of the generic form.

**Validation** (`core/validator.validate_document`) runs up to three independent layers
and returns a flat `list[ValidationIssue]`: JSON-Schema validation (when a raw JSON
schema is supplied), `ExtensionSettings` required-field rules (`force_installed`/
`normal_installed` require `install_url`; `allowed`/`blocked` must not set it), and
Firefox min/max version compatibility warnings against a `PolicySchema`. GUI and CLI both
consume the same issue list.

**Presets** (`core/presets.py`, `resources/presets/*.yaml`): a preset bundles a pre-merged
`policy-name -> value` baseline plus `rules` metadata (source rule id/severity/title, and
which top-level policy it maps to, or `policy: null` for items that can't be expressed in
policies.json at all). `apply_preset()` overlays a preset's values onto a `PolicyDocument`
one top-level key at a time; CLI (`--preset <id>` on validate/generate/export/preview, plus
a `presets` list command) and GUI (menu bar -> Presets) both apply a preset as a baseline
that an input file or further manual edits then override. See `docs/DISA_STIG.md` for the
bundled DISA STIG preset and why some source values (e.g. `FirefoxHome.Locked` casing) were
corrected against Firefox's actual schema rather than copied verbatim from the STIG text.

## Testing conventions

- `tests/unit/` - core/models/fetchers/gui logic in isolation; network calls are mocked
  with `responses`, not hit live.
- `tests/functional/` - CLI end-to-end (`typer.testing.CliRunner`), export path
  resolution, and the golden-file check.
- Cache-dependent tests must monkeypatch `platformdirs.user_cache_dir` to a `tmp_path`,
  not `ffpolicy.fetchers.cache.cache_dir` directly - the latter still calls the real
  `platformdirs` function internally and won't isolate the test.
- GUI tests use `pytest-qt`'s `qtbot`; construct `MainWindow(schema=..., schema_tier=...)`
  with `fetchers.schema_sync.load_bundled_schema()` rather than letting it hit the network.
