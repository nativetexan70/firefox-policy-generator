# Firefox Policy Generator — Technical Implementation Blueprint

> A Python desktop/CLI application that generates, validates, and manages Firefox
> enterprise `policies.json` configurations, packaged as a standalone Linux AppImage.

**Status:** Planning
**Target platforms:** Linux (primary, AppImage), portable to macOS/Windows
**Language:** Python 3.11+

---

## 0. Executive Summary

The application lets system administrators build valid Firefox enterprise
`policies.json` files through a modern Qt GUI (and a headless CLI). It stays
current by synchronizing policy schemas from Mozilla's official sources, helps
users configure extensions via the AMO API, validates output against JSON
Schema, and exports to standard Firefox policy locations. The whole thing ships
as a self-contained AppImage.

**Guiding principles**

- **Schema-driven UI** — forms are generated from parsed Mozilla schema, not
  hand-coded per policy. New Firefox policies appear automatically after a sync.
- **Offline-first** — every online feature has a bundled fallback so the app is
  fully usable with no network.
- **Separation of concerns** — core logic (models, validation, generation) has
  zero GUI dependencies, so the CLI and tests reuse it directly.
- **Deterministic output** — the same inputs always produce byte-identical
  `policies.json` (stable key ordering) for clean diffs in config management.

---

## 1. Architecture & Project Layout

### 1.1 Module structure

```
fedora-policy-generator/
├── src/
│   └── ffpolicy/
│       ├── __init__.py
│       ├── __main__.py            # `python -m ffpolicy` entrypoint
│       ├── app.py                 # App bootstrap, DI wiring, config load
│       ├── cli.py                 # Headless CLI (argparse/typer)
│       │
│       ├── core/                  # Pure logic — NO Qt imports allowed
│       │   ├── __init__.py
│       │   ├── generator.py       # Assemble policies dict → policies.json
│       │   ├── validator.py       # jsonschema validation + custom rules
│       │   ├── version_check.py   # Firefox min/max version compatibility
│       │   ├── paths.py           # Standard policy install-path resolution
│       │   └── errors.py          # Typed exceptions (ValidationError, etc.)
│       │
│       ├── models/                # Pydantic data models
│       │   ├── __init__.py
│       │   ├── policy_schema.py    # PolicyDefinition, PolicyField, ValueType
│       │   ├── policy_document.py  # The user's in-progress policy set
│       │   ├── extension.py        # ExtensionSetting, InstallationMode
│       │   └── amo.py              # AMO API response models
│       │
│       ├── fetchers/              # Network + caching layer
│       │   ├── __init__.py
│       │   ├── base.py            # HTTP client w/ retry, timeout, ETag cache
│       │   ├── schema_sync.py     # Mozilla policy-templates fetch + parse
│       │   ├── amo_client.py      # addons.mozilla.org API v5 client
│       │   └── cache.py           # On-disk cache (XDG dirs) + TTL
│       │
│       ├── gui/                   # PySide6 UI — depends on core/models only
│       │   ├── __init__.py
│       │   ├── main_window.py     # QMainWindow, layout, menu, status bar
│       │   ├── category_tree.py   # Left nav: policy categories
│       │   ├── form_builder.py    # Schema → dynamic QWidget forms
│       │   ├── extension_manager.py
│       │   ├── json_preview.py    # Live syntax-highlighted preview
│       │   ├── validation_panel.py
│       │   ├── widgets/           # Reusable field widgets (toggle, dropdown…)
│       │   └── highlight.py       # QSyntaxHighlighter for JSON
│       │
│       ├── resources/            # Bundled non-code assets
│       │   ├── schema_backup.json # Offline fallback schema
│       │   ├── categories.yaml    # Category → policy grouping map
│       │   └── icons/
│       │
│       └── packager/             # Build tooling (not shipped in AppImage)
│           ├── build_appimage.sh
│           ├── ffpolicy.desktop
│           └── ffpolicy.spec      # PyInstaller spec
│
├── tests/
│   ├── unit/
│   ├── functional/
│   └── fixtures/                 # Sample schemas, golden policies.json
├── docs/
│   └── IMPLEMENTATION_PLAN.md    # (this file)
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 1.2 Dependencies

| Package | Purpose | Notes |
|---|---|---|
| `PySide6` | Qt GUI framework | Official Qt binding; LGPL |
| `requests` | HTTP for fetchers | Or `httpx` if async is wanted later |
| `pydantic` v2 | Data modeling + validation | Fast, typed, JSON-native |
| `jsonschema` | Validate output vs. Firefox schema | Draft 7/2020-12 |
| `PyYAML` | Parse `categories.yaml`, any YAML templates | |
| `platformdirs` | XDG cache/config dirs cross-platform | For `fetchers/cache.py` |
| `typer` *(opt)* | Ergonomic CLI | Or stdlib `argparse` |

**Dev/build deps:** `pytest`, `pytest-qt`, `pytest-mock`, `responses` (mock
HTTP), `ruff` (lint+format), `mypy`, `PyInstaller`, `appimagetool`.

### 1.3 Dependency-flow rule

`gui/` → `core/` + `models/`; `core/` → `models/`; `fetchers/` → `models/`.
**`core/` and `models/` must never import `gui/` or `PySide6`.** Enforce with a
CI lint check (grep or `import-linter`). This is what keeps the CLI and unit
tests fast and headless.

---

## 2. Data Model & Schema Engine

### 2.1 Source formats from Mozilla

Mozilla's `policy-templates` repo publishes several artifacts. The most
machine-friendly is **`schema.json`** (a JSON Schema of all policies) plus the
**`README.md`** for human descriptions and version metadata. Strategy:

1. **Primary source:** `schema.json` — authoritative types/structure.
2. **Enrichment source:** parse the README table for descriptions,
   "compatibility" (Firefox min version), and per-policy notes.
3. Merge both into internal `PolicyDefinition` models.

### 2.2 Pydantic models (core shapes)

```python
# models/policy_schema.py
class ValueType(str, Enum):
    BOOL = "boolean"; STRING = "string"; INT = "integer"
    ENUM = "enum"; OBJECT = "object"; ARRAY = "array"; URL = "url"

class PolicyField(BaseModel):
    key: str
    type: ValueType
    description: str | None = None
    enum_values: list[str] | None = None
    default: Any | None = None
    required: bool = False
    children: list["PolicyField"] = []      # nested objects/arrays

class PolicyDefinition(BaseModel):
    name: str                                # e.g. "ExtensionSettings"
    category: str                            # from categories.yaml
    description: str | None = None
    min_firefox_version: int | None = None
    max_firefox_version: int | None = None
    root_field: PolicyField                  # tree describing the value shape

class PolicySchema(BaseModel):
    source_version: str                      # git sha / release tag of templates
    fetched_at: datetime
    policies: dict[str, PolicyDefinition]
```

```python
# models/policy_document.py — the user's working set
class PolicyDocument(BaseModel):
    values: dict[str, Any] = {}              # policy name → configured value
    def to_policies_json(self) -> dict:      # -> {"policies": {...}}
        ...
```

### 2.3 Schema parsing pipeline (`fetchers/schema_sync.py`)

```
fetch schema.json ──┐
                    ├─► merge ─► normalize types ─► attach categories
fetch README.md  ───┘            (JSON Schema →      (categories.yaml)
   (versions,                     ValueType)
    descriptions)
                                        │
                                        ▼
                          PolicySchema  ─► cache to disk (fetchers/cache.py)
```

- **Normalization:** map JSON Schema constructs to `ValueType`
  (`{"type":"boolean"}`→BOOL, `enum`→ENUM, `{"type":"object","properties":…}`→
  OBJECT with recursive children, `format:"uri"`→URL).
- **Caching:** store the parsed `PolicySchema` as JSON under
  `platformdirs.user_cache_dir("ffpolicy")/schema/`. Key by source version;
  respect HTTP `ETag`/`Last-Modified` to avoid re-downloading.
- **Fallback chain:** live fetch → disk cache → bundled
  `resources/schema_backup.json`. Log which tier was used; surface it in the UI
  status bar ("Schema: cached · Firefox 128 templates").

### 2.4 Dynamic form generation mapping

`gui/form_builder.py` walks a `PolicyDefinition.root_field` and emits widgets:

| ValueType | Widget |
|---|---|
| BOOL | `QCheckBox` / toggle |
| STRING | `QLineEdit` |
| INT | `QSpinBox` |
| ENUM | `QComboBox` (enum_values) |
| URL | `QLineEdit` + URL validator |
| OBJECT | `QGroupBox` recursing over children |
| ARRAY | Add/remove list of the child widget |

Each widget's `valueChanged` signal writes back into the `PolicyDocument`,
triggering revalidation and a live JSON-preview refresh (debounced ~150 ms).

---

## 3. Extension / AMO API Service

### 3.1 Endpoint integration

- **Search:** `GET https://addons.mozilla.org/api/v5/addons/search/?q={query}&app=firefox&type=extension`
- **Detail:** `GET https://addons.mozilla.org/api/v5/addons/addon/{id_or_slug}/`
- **URL paste:** parse an AMO URL (`…/firefox/addon/<slug>/`) → detail call.

Fields extracted for `ExtensionSettings`:

| ExtensionSettings key | AMO source field |
|---|---|
| add-on ID (map key) | `guid` |
| `install_url` | `current_version.file.url` (the signed XPI URL) |
| display name (UI only) | `name` |
| icon (UI only) | `icon_url` |

### 3.2 Installation modes

Expose the four modes as an enum with per-mode required fields:

```python
class InstallationMode(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    FORCE_INSTALLED = "force_installed"    # requires install_url
    NORMAL_INSTALLED = "normal_installed"  # requires install_url
```

Validation rule: `force_installed`/`normal_installed` **must** carry a valid
`install_url`; `blocked`/`allowed` must not.

### 3.3 Caching strategy

- Cache AMO responses per-add-on under `user_cache_dir/amo/` with a **24h TTL**
  (extensions update, but not minute-to-minute).
- Debounce search input (~300 ms) to avoid hammering the API on each keystroke.
- Handle rate limiting (HTTP 429) with backoff; degrade gracefully to "search
  unavailable, enter GUID manually" so the feature is never a hard blocker.

---

## 4. UI Design & User Workflow

### 4.1 Main window layout

```
┌───────────────────────────────────────────────────────────────┐
│  Menu: File  Edit  Schema(Sync)  Export  Help        [status]  │
├───────────────┬───────────────────────────┬───────────────────┤
│ Category Tree │   Interactive Editor      │  JSON Preview      │
│ ───────────── │   ─────────────────────   │  ───────────────   │
│ ▸ Security    │   [dynamic form for the   │  {                 │
│ ▸ Extensions  │    selected policy, built │   "policies": {    │
│ ▸ UI/Bookmarks│    from schema]           │     ...            │
│ ▸ Privacy/Net │                           │   }                │
│ ▸ Updates     │                           │  }                 │
│ ▸ Custom Prefs│                           │  (syntax-highl.)   │
├───────────────┴───────────────────────────┴───────────────────┤
│  Validation panel: ✓ valid · 2 warnings   [Export policies.json]│
└───────────────────────────────────────────────────────────────┘
```

### 4.2 Categories (`resources/categories.yaml`)

Maps every policy name to one of: **Security, Extensions, UI/Bookmarks,
Privacy & Network, Updates, Custom Preferences**. Unmapped/new policies (after a
sync) fall into a **"Uncategorized"** bucket so nothing is ever hidden.

### 4.3 Extension Manager screen

A table view: `[Search box] → results list → "Add"`. Each configured extension
becomes a row: *Name · GUID · Mode dropdown · install_url · Remove*. Writes into
the `ExtensionSettings` policy value in the document model.

### 4.4 Key workflows

1. **Build a policy set:** pick category → toggle/fill fields → watch live
   preview → validate → export.
2. **Add an extension:** Extensions category → search AMO → pick result →
   choose mode → auto-filled GUID/URL → appears in preview.
3. **Sync schema:** Schema menu → "Sync now" → progress → status bar shows new
   template version; new policies appear in the tree.
4. **Export:** choose target (`/etc/firefox/policies/`,
   `distribution/policies.json`, or custom path) → confirm overwrite → write.

### 4.5 Live preview & highlighting

`gui/highlight.py` subclasses `QSyntaxHighlighter` for JSON (keys, strings,
numbers, booleans, punctuation). The preview re-renders from
`PolicyDocument.to_policies_json()` on every debounced change and shows inline
validation squiggles from the validation panel's results.

---

## 5. AppImage Build Scripting & CI Pipeline

### 5.1 AppDir layout

```
ffpolicy.AppDir/
├── AppRun                       # entry shim → usr/bin/ffpolicy
├── ffpolicy.desktop
├── ffpolicy.png                 # icon (256x256)
└── usr/
    ├── bin/ffpolicy             # PyInstaller onedir output
    └── lib/                     # bundled Python + Qt + deps
```

### 5.2 `.desktop` file

```ini
[Desktop Entry]
Type=Application
Name=Firefox Policy Generator
Comment=Create and manage Firefox enterprise policies.json
Exec=ffpolicy
Icon=ffpolicy
Categories=Settings;System;Utility;
Terminal=false
```

### 5.3 `build_appimage.sh` (step-by-step)

```bash
#!/usr/bin/env bash
set -euo pipefail

APP=ffpolicy
VERSION="${1:-0.1.0}"
DIST=dist
APPDIR="$DIST/$APP.AppDir"

# 1. Clean
rm -rf build "$DIST"
mkdir -p "$DIST"

# 2. Freeze the app with PyInstaller (onedir keeps AppImage layout clean)
pyinstaller --noconfirm --clean \
    --name "$APP" \
    --windowed \
    --add-data "src/ffpolicy/resources:ffpolicy/resources" \
    src/ffpolicy/__main__.py

# 3. Assemble AppDir
mkdir -p "$APPDIR/usr/bin"
cp -r "dist/$APP/"* "$APPDIR/usr/bin/"
cp src/ffpolicy/packager/$APP.desktop "$APPDIR/$APP.desktop"
cp src/ffpolicy/resources/icons/$APP.png "$APPDIR/$APP.png"

# 4. AppRun shim
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/ffpolicy" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 5. Build the AppImage
ARCH=x86_64 appimagetool "$APPDIR" "$DIST/$APP-$VERSION-x86_64.AppImage"

echo "Built $DIST/$APP-$VERSION-x86_64.AppImage"
```

### 5.4 Dependency-bundling notes

- **Qt plugins:** ensure the `platforms/` (esp. `libqxcb.so`) and `xcb`
  dependencies are pulled in — PyInstaller's PySide6 hook usually handles this;
  verify with a clean-container smoke test.
- **SSL:** bundle `certifi` CA bundle and point `requests` at it via
  `REQUESTS_CA_BUNDLE`, since the host may lack certs.
- **System libs:** `libX11`, `libxcb`, `libGL` are expected on any desktop
  Linux; do **not** bundle glibc. Test on the oldest target distro to keep glibc
  compatibility (build on an old baseline, e.g. a manylinux-style container).

### 5.5 CI pipeline (GitHub Actions)

```yaml
# .github/workflows/build.yml (outline)
jobs:
  test:
    - checkout; setup-python 3.11
    - pip install -r requirements.txt -r requirements-dev.txt
    - ruff check . && mypy src
    - pytest --cov=ffpolicy
  build-appimage:
    needs: test
    runs-on: ubuntu-22.04           # older baseline for glibc compat
    - install appimagetool
    - bash src/ffpolicy/packager/build_appimage.sh ${{ github.ref_name }}
    - upload-artifact: dist/*.AppImage
```

Run GUI tests headless with `xvfb-run` (or `QT_QPA_PLATFORM=offscreen`).

---

## 6. Validation & Testing Strategy

### 6.1 Validation engine (`core/validator.py`)

Three layers, run on every change and pre-export:

1. **Schema validation** — validate `PolicyDocument.to_policies_json()` against
   Mozilla's `schema.json` via `jsonschema`. Catches wrong types, unknown keys,
   malformed structure.
2. **Required-field checks** — per-policy custom rules (e.g. ExtensionSettings
   `force_installed` requires `install_url`).
3. **Version compatibility** — warn when a configured policy's
   `min_firefox_version` exceeds the user's declared target Firefox version.

Results are typed `ValidationIssue(level=ERROR|WARNING, policy, message)` so both
GUI (panel) and CLI (exit code) consume the same output.

### 6.2 Unit tests (`tests/unit/`)

- **Schema parsing:** feed fixture `schema.json` → assert `PolicyDefinition`
  trees, types, versions parse correctly (incl. nested objects/arrays).
- **Generator:** `PolicyDocument` → `policies.json` produces expected, stably
  ordered dict; compare against golden fixtures.
- **Validator:** table-driven cases — valid docs pass; each invalid shape yields
  the expected `ValidationIssue`.
- **AMO client:** mock HTTP (`responses`) → assert GUID/install_url extraction
  and cache hit/miss/TTL behavior.
- **Version check:** min/max boundary cases.

### 6.3 Functional tests (`tests/functional/`)

- **Export routines:** write to a temp dir; re-read and assert byte-identical to
  golden `policies.json`; verify path resolution for each target
  (`/etc/firefox/policies/`, `distribution/`, custom) using a fake filesystem
  root. Confirm overwrite-guard and permission-error handling.
- **Fallback chain:** simulate no-network → assert bundled backup schema loads
  and the app is still usable.
- **CLI end-to-end:** `ffpolicy --generate <input.yaml> -o out.json` produces a
  valid file and non-zero exit on validation errors.

### 6.4 GUI tests (`pytest-qt`, optional but recommended)

- Selecting a category populates the form.
- Toggling a field updates the live JSON preview.
- Adding an extension writes a correct `ExtensionSettings` entry.

### 6.5 Golden-file discipline

Keep canonical `policies.json` outputs in `tests/fixtures/golden/`. Regenerate
intentionally (a `make update-golden` target) and review diffs in PRs — this is
the safety net for the deterministic-output guarantee.

---

## 7. Execution Roadmap (phased task list)

### Phase 0 — Project scaffolding
- [ ] `pyproject.toml`, `src/ffpolicy/` package, tooling (ruff, mypy, pytest).
- [ ] CI skeleton: lint + test on push.
- [ ] Enforce the "core/models never import gui" rule in CI.

### Phase 1 — Core & models (no network, no GUI)
- [ ] Pydantic models (`policy_schema`, `policy_document`, `extension`, `amo`).
- [ ] Bundle a real `schema_backup.json` + `categories.yaml`.
- [ ] `generator.py` + `validator.py` + `version_check.py` with unit tests.
- [ ] **Milestone:** generate & validate a `policies.json` fully offline.

### Phase 2 — Fetchers
- [ ] HTTP base client (retry/timeout/ETag), disk cache with TTL.
- [ ] `schema_sync.py`: fetch+parse Mozilla templates → `PolicySchema`.
- [ ] `amo_client.py`: search/detail + extraction, mocked tests.
- [ ] **Milestone:** live sync updates the cached schema; AMO search works.

### Phase 3 — CLI
- [ ] `cli.py`: generate/validate/export from a YAML/JSON input.
- [ ] **Milestone:** headless end-to-end usable in config-management pipelines.

### Phase 4 — GUI
- [ ] `main_window` shell + category tree + JSON preview + highlighter.
- [ ] `form_builder` (schema → widgets) + field widgets.
- [ ] Extension manager + validation panel + export dialog.
- [ ] **Milestone:** full visual build-validate-export loop.

### Phase 5 — Packaging
- [ ] PyInstaller spec, `build_appimage.sh`, `.desktop`, icon.
- [ ] Clean-container smoke test (Qt plugins, SSL, glibc baseline).
- [ ] CI job producing an `.AppImage` artifact per tag.
- [ ] **Milestone:** downloadable, self-contained AppImage.

### Phase 6 — Hardening
- [ ] Functional export + fallback tests; GUI smoke tests under xvfb.
- [ ] Golden-file suite + `update-golden` target.
- [ ] Docs: user guide + contributor guide.

---

## 8. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Mozilla changes template repo layout/URLs | Isolate all URLs/parsing in `schema_sync.py`; bundled fallback keeps app working; pin a known-good version. |
| AMO API shape/rate changes | Isolated `amo_client.py`; graceful manual-entry degradation; cached responses. |
| AppImage misses a Qt/SSL dep | Clean-container smoke test in CI; explicit bundling checklist (§5.4). |
| glibc incompatibility on older distros | Build on an old baseline (ubuntu-22.04 / manylinux). |
| Schema-driven forms hit an unmapped type | `form_builder` falls back to a raw JSON editor for unknown shapes. |

---

*End of blueprint. Implementation should proceed phase-by-phase; each phase has a
concrete milestone that is independently testable before moving on.*
