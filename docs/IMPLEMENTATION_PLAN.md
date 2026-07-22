# Firefox Policy Generator — Technical Implementation Blueprint

> A Python desktop/CLI application that generates, validates, and manages Firefox
> enterprise `policies.json` configurations, packaged as a standalone Linux AppImage.

**Status:** Implemented (Phases 0-6 below, plus compliance presets added after PR #4/#5)
**Target platforms:** Linux (primary, AppImage), portable to macOS/Windows
**Language:** Python 3.11+

This document was originally written as a forward-looking design blueprint before
any code existed. It's kept up to date as an as-built record: the architecture,
diagrams, and roadmap below describe what was actually built, with deviations
from the original plan called out explicitly rather than silently rewritten.

---

## 0. Executive Summary

The application lets system administrators build valid Firefox enterprise
`policies.json` files through a modern Qt GUI (and a headless CLI). It stays
current by synchronizing policy schemas from Mozilla's official sources, helps
users configure extensions via the AMO API, validates output against JSON
Schema, and exports to standard Firefox policy locations. Bundled compliance
presets (e.g. DISA STIG) apply a known-good baseline in one step. The whole
thing ships as a self-contained AppImage.

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

### 1.1 Module structure (as built)

```
fedora-policy-generator/
├── src/
│   └── ffpolicy/
│       ├── __init__.py
│       ├── __main__.py            # `python -m ffpolicy` entrypoint; dispatches
│       │                          # to cli.py when argv has args, else the GUI
│       ├── cli.py                 # Headless CLI (Typer)
│       │
│       ├── core/                  # Pure logic — NO Qt imports allowed
│       │   ├── __init__.py
│       │   ├── generator.py       # Assemble policies dict → policies.json
│       │   ├── validator.py       # jsonschema validation + custom rules
│       │   ├── version_check.py   # Firefox min/max version compatibility
│       │   ├── paths.py           # Standard policy install-path resolution
│       │   ├── presets.py         # Preset/PresetRule models, apply_preset()
│       │   └── errors.py          # Typed exceptions (ExportError, etc.)
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
│       │   ├── main_window.py     # QMainWindow, menu bar, splitter, footer
│       │   ├── category_tree.py   # Left nav: policy categories
│       │   ├── form_builder.py    # Schema → dynamic QWidget forms
│       │   ├── extension_manager.py  # AMO search + manual entry + table
│       │   ├── json_preview.py    # Live syntax-highlighted preview
│       │   ├── validation_panel.py
│       │   ├── preset_details.py  # Rule-by-rule description/recommendation dialog
│       │   ├── style.py           # Shared QSS stylesheet
│       │   ├── highlight.py       # QSyntaxHighlighter for JSON
│       │   └── widgets/
│       │       └── field_widgets.py  # Reusable field editors (bool/string/enum/…)
│       │
│       ├── resources/            # Bundled non-code assets
│       │   ├── schema_backup.json # Offline fallback schema (31 policies)
│       │   ├── categories.yaml    # Category → policy grouping map
│       │   ├── presets/
│       │   │   └── disa_stig.yaml # DISA STIG baseline, expands to 9 profile presets
│       │   └── icons/
│       │
│       └── packager/             # Build tooling (not shipped in AppImage)
│           ├── build_appimage.sh
│           ├── ffpolicy.desktop
│           └── ffpolicy.spec      # PyInstaller spec
│
├── tests/
│   ├── unit/       # core/models/fetchers/gui/presets logic in isolation
│   ├── functional/ # CLI end-to-end, export-path resolution, golden-file check
│   └── fixtures/   # Sample input + golden policies.json
├── docs/
│   ├── IMPLEMENTATION_PLAN.md    # (this file)
│   └── DISA_STIG.md              # Preset usage + full rule → policy mapping
├── pyproject.toml
├── requirements.txt / requirements-dev.txt
└── README.md
```

Deviations from the original plan: there's no `app.py` (bootstrap/DI wiring was
never needed - `__main__.py` and `cli.py` are simple enough without it), and
`gui/widgets/` holds one module (`field_widgets.py`) rather than one file per
widget type, since the editors are small and share `build_field_editor()`'s
dispatch logic.

### 1.2 Dependencies

| Package | Purpose | Notes |
|---|---|---|
| `PySide6` | Qt GUI framework | Official Qt binding; LGPL |
| `requests` | HTTP for fetchers | |
| `pydantic` v2 | Data modeling + validation | Fast, typed, JSON-native |
| `jsonschema` | Validate output vs. Firefox schema | Draft 7 |
| `PyYAML` | Parse `categories.yaml` and `presets/*.yaml` | |
| `platformdirs` | XDG cache/config dirs cross-platform | For `fetchers/cache.py` |
| `typer` | CLI framework | |

**Dev/build deps:** `pytest`, `pytest-qt`, `pytest-mock`, `pytest-cov`,
`responses` (mock HTTP), `ruff`, `mypy`, `import-linter` (backs `lint-imports`),
`PyInstaller`, `appimagetool`.

### 1.3 Dependency-flow rule

`gui/` → `core/` + `models/`; `core/` → `models/`; `fetchers/` → `models/`.
**`core/` and `models/` must never import `gui/` or `PySide6`.** Enforced by
`lint-imports` (an `import-linter` contract in `setup.cfg`) as a CI step, not
just convention. This is what keeps the CLI and unit tests fast and headless.

---

## 2. Data Model & Schema Engine

### 2.1 Source formats from Mozilla

Mozilla's `policy-templates` repo used to publish a machine-readable
**`schema.json`** plus a **`README.md`** table for descriptions/versions.
`fetchers/schema_sync.py` was built against that format:

1. **Primary source:** `schema.json` — authoritative types/structure.
2. **Enrichment source:** parse the README for descriptions, "compatibility"
   (Firefox min version), and per-policy notes.
3. Merge both into internal `PolicyDefinition` models.

> **Known issue:** Mozilla has since retired `policy-templates`' `schema.json`
> and moved policy docs to `firefox-admin-docs.mozilla.org`, backed by
> `mozilla/enterprise-admin-reference`, which publishes one `.mdx` file per
> policy rather than a single schema + README table. `SCHEMA_URL` in
> `schema_sync.py` currently 404s, so the "live" tier never succeeds and every
> run silently falls through to the cached/bundled tier. The bundled
> `schema_backup.json` has been manually verified against the new source (see
> §8), so the app is still correct, but `schema_sync.py`'s live-fetch path
> needs a rewrite against the new per-policy `.mdx` format - tracked as
> follow-up work, not yet done.

### 2.2 Pydantic models (core shapes, as built)

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
    category: str = "Uncategorized"          # from categories.yaml
    description: str | None = None
    min_firefox_version: int | None = None
    max_firefox_version: int | None = None
    root_field: PolicyField                  # tree describing the value shape

class PolicySchema(BaseModel):
    source_version: str
    fetched_at: datetime
    policies: dict[str, PolicyDefinition]
```

```python
# models/policy_document.py — the user's working set
class PolicyDocument(BaseModel):
    values: dict[str, Any] = {}
    def to_policies_json(self) -> dict:      # -> {"policies": {...}}, sorted keys
        ...
```

### 2.3 Schema parsing pipeline (`fetchers/schema_sync.py`)

- **Normalization:** map JSON Schema constructs to `ValueType`
  (`{"type":"boolean"}`→BOOL, `enum`→ENUM, `{"type":"object","properties":…}`→
  OBJECT with recursive children, `format:"uri"`→URL, and a wildcard `"*"`
  child for maps keyed by arbitrary names).
- **Caching:** `fetchers/cache.py` stores fetched data under
  `platformdirs.user_cache_dir("ffpolicy")`, respecting HTTP `ETag` to avoid
  re-downloading unchanged data.
- **Fallback chain:** live fetch → disk cache → bundled
  `resources/schema_backup.json`. `sync_schema()` returns `(schema, tier)` so
  callers (CLI, GUI status bar) can report which tier was used;
  `load_bundled_schema()` skips the network entirely for `--offline` CLI runs
  and tests.

The bundled schema currently covers **31 policies** (started at 11 in Phase 1;
grew to cover every policy the DISA STIG preset needed - see §9).

### 2.4 Dynamic form generation mapping

`gui/widgets/field_widgets.build_field_editor` walks a `PolicyField` tree and
emits widgets:

| ValueType | Widget |
|---|---|
| BOOL | `QCheckBox` (its own label - no duplicate row label) |
| STRING / URL | `QLineEdit` |
| INT | `QSpinBox` |
| ENUM | `QComboBox` (enum_values) |
| OBJECT | `QGroupBox` recursing over children |
| ARRAY | Add/remove list of the child widget |
| OBJECT with a wildcard (`"*"`) child | Falls back to a raw JSON `QTextEdit` -
  the fixed-field form generator can't synthesize a form for arbitrary keys |

Each widget's `valueChanged` signal writes back into the `PolicyDocument`,
triggering revalidation and a live JSON-preview refresh (debounced 150 ms via
`MainWindow._debounce`, a `QTimer`).

---

## 3. Extension / AMO API Service

### 3.1 Endpoint integration

- **Search:** `GET https://addons.mozilla.org/api/v5/addons/search/?q={query}&app=firefox&type=extension`
- **Detail:** `GET https://addons.mozilla.org/api/v5/addons/addon/{id_or_slug}/`
- `parse_addon_slug_from_url()` exists in `amo_client.py` for parsing an AMO
  page URL into a slug, but isn't yet wired into the GUI search flow.

Fields extracted for `ExtensionSettings`:

| ExtensionSettings key | AMO source field |
|---|---|
| add-on ID (map key) | `guid` |
| `install_url` | `current_version.file.url` (the signed XPI URL) |
| display name (UI only) | `name` |
| icon (UI only) | `icon_url` |

### 3.2 Installation modes

```python
class InstallationMode(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    FORCE_INSTALLED = "force_installed"    # requires install_url
    NORMAL_INSTALLED = "normal_installed"  # requires install_url
```

Validation rule: `force_installed`/`normal_installed` **must** carry a valid
`install_url`; `blocked`/`allowed` must not.

### 3.3 Caching, ranking, and manual fallback (as built)

- AMO responses are cached per-query/per-add-on under `user_cache_dir/amo/`
  with a **24h TTL**.
- `rank_by_name_relevance()` re-sorts search results (exact name match >
  prefix match > substring match > no direct match) before they reach the UI,
  since AMO's own relevance ranking weighs description/summary matches the
  same as name matches.
- On search failure (rate-limited, network-restricted, or an add-on simply not
  listed on AMO), `ExtensionManager` degrades to an **always-visible manual
  entry row** (GUID + installation mode + optional install URL) rather than a
  dead end - this was added after the original search-only design left no
  path forward when `addons.mozilla.org` is unreachable.

---

## 4. UI Design & User Workflow

### 4.1 Main window layout (as built)

```
┌──────────────────────────────────────────────────────────────────┐
│  Presets                                                          │
├───────────────┬────────────────────────────┬─────────────────────┤
│ CATEGORIES    │  POLICY EDITOR              │  JSON PREVIEW        │
│ ───────────── │  ─────────────────────────  │  ───────────────    │
│ ▸ Security    │  [dynamic form for the      │  {                  │
│ ▸ Extensions  │   selected policy, built    │    "policies": {    │
│ ▸ UI/Bookmarks│   from schema; or the       │      ...            │
│ ▸ Privacy/Net │   Extension Manager for     │    }                │
│ ▸ Updates     │   ExtensionSettings]        │  }                  │
│ ▸ Custom Prefs│                             │  (syntax-highl.)    │
├───────────────┴────────────────────────────┴─────────────────────┤
│  ✓ valid              [footer bar]      [Export policies.json]   │
└──────────────────────────────────────────────────────────────────┘
Schema: bundled · 31 policies                          [status bar]
```

The window is a **fixed, non-resizable 1600×900**, centered on the primary
screen - sized for a 1920×1080 (FHD) display with room for OS
decorations/taskbars, rather than freely resizable as the original plan
implied. A shared QSS stylesheet (`gui/style.py`) gives the whole app a flat,
modern look (rounded inputs/buttons, a primary-colored Export button,
color-coded validation status). The originally-planned `File`/`Edit`/
`Schema(Sync)`/`Export`/`Help` menus were never built; the one menu that
exists is **Presets** (see §4.3 and §9) - schema sync happens automatically at
startup and export is a footer-bar button, not a menu action or dialog.

### 4.2 Categories (`resources/categories.yaml`)

Maps every policy name to one of: **Security, Extensions, UI/Bookmarks,
Privacy & Network, Updates, Custom Preferences** - unchanged from the original
plan. Unmapped/new policies fall into an **"Uncategorized"** bucket so nothing
is ever hidden.

### 4.3 Extension Manager screen (as built)

`gui/extension_manager.py`: a search box + button, a results list (double-click
to add), a **manual-entry row** (GUID / mode / install URL / Add - always
available, independent of whether search works), and a configured-extensions
table: *GUID · Mode · Install URL · Remove*, with column resize modes tuned so
Mode and Remove don't collapse to unreadable slivers (`Interactive` with
explicit initial widths, not `ResizeToContents` - that mode doesn't reliably
re-measure widget-based cells added after the table is first laid out).

### 4.4 Presets menu (added after the original plan - see §9)

Menu bar → **Presets**. Presets sharing a `family` (e.g. all nine DISA STIG
profiles) are grouped into one submenu containing **View rule details...**
(opens `PresetDetailsDialog`, listing every rule's severity, policy,
description, and recommendation) plus one **Apply \<profile\>...** action per
profile. Applying a preset asks for confirmation, refreshes the live preview/
validation and any open policy form, then surfaces the rules that can't be
expressed in `policies.json` and need manual/procedural follow-up.

### 4.5 Key workflows

1. **Build a policy set:** pick category → toggle/fill fields → watch live
   preview → validate → export.
2. **Add an extension:** Extensions category → search AMO (or use the manual
   entry row) → pick result or fill GUID/mode/URL → appears in preview.
3. **Apply a compliance preset:** Presets menu → pick a profile → confirm →
   baseline applied, manual/procedural items called out → hand-tune anything
   organization-specific (e.g. a pop-up allowlist) on top.
4. **Export:** click "Export policies.json" in the footer bar → file dialog.
   (The CLI additionally supports the standard Linux target locations -
   `/etc/firefox/policies/`, the per-distro `.../distribution/` install
   directories, `distribution/`, or a custom path - via `ffpolicy export
   --target`, with `--elevate` to retry a denied write via pkexec/sudo since
   those locations are root-owned; the GUI only offers "save as" today.)

### 4.6 Live preview & highlighting

`gui/highlight.py` subclasses `QSyntaxHighlighter` for JSON (keys, strings,
numbers, booleans, punctuation). `gui/json_preview.py`'s preview re-renders
from `render_policies_json()` on every debounced change. (Inline validation
squiggles in the preview itself were part of the original plan but weren't
built; the validation panel below the splitter shows issues as a separate
list instead.)

---

## 5. AppImage Build Scripting & CI Pipeline

### 5.1 AppDir layout

```
ffpolicy.AppDir/
├── AppRun                       # entry shim → usr/bin/ffpolicy
├── ffpolicy.desktop
├── ffpolicy.png                 # icon (256x256)
└── usr/
    └── bin/ffpolicy             # PyInstaller onedir output
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

### 5.3 `build_appimage.sh` (as built)

Freezes via `ffpolicy.spec` (a PyInstaller spec, not raw CLI flags - keeps the
resource-bundling and entry-point config in one reviewable file) rather than
inlining `pyinstaller` flags:

```bash
pyinstaller --noconfirm --clean src/ffpolicy/packager/ffpolicy.spec
# ...assemble AppDir, AppRun shim...
ARCH=x86_64 appimagetool --appimage-extract-and-run "$APPDIR" "$DIST/$APP-$VERSION-x86_64.AppImage"
```

`--appimage-extract-and-run` was added after the fact: `appimagetool` is
itself an AppImage that needs FUSE to run directly, which GitHub-hosted CI
runners (and some desktop distros) don't have configured - this flag makes it
self-extract instead, avoiding the dependency.

### 5.4 Dependency-bundling notes

- **Qt plugins:** PyInstaller's PySide6 hook pulls in `platforms/`
  (`libqxcb.so`) and `xcb` dependencies automatically; verified by a real
  freeze + CLI smoke test during Phase 5 (not just planned).
- **System libs:** headless/CI environments need `libegl1 libgl1
  libxkbcommon0 libxcb-cursor0 libxcb-image0 libxcb-render-util0
  libxcb-util1` installed even for *offscreen* Qt rendering - without them
  PySide6 import aborts with `libEGL.so.1`/`libxcb-cursor.so.0` errors. The CI
  workflow installs these before running tests.
- **glibc:** build on `ubuntu-22.04` (an older baseline) for compatibility
  with older target distros; not yet stress-tested against the oldest
  realistic deployment target.

### 5.5 CI pipeline (`.github/workflows/build.yml`, as built)

```yaml
on:
  push: { branches: [main] }
  pull_request:
  workflow_dispatch:
    inputs:
      version: { default: "dev" }   # lets the AppImage build run on-demand

jobs:
  test:
    - checkout; setup-python 3.11
    - install system Qt runtime libs (see §5.4)
    - pip install -e ".[dev]"
    - ruff check . && lint-imports && mypy src
    - QT_QPA_PLATFORM=offscreen pytest --cov=ffpolicy
  build-appimage:
    needs: test
    if: startsWith(github.ref, 'refs/tags/') || github.event_name == 'workflow_dispatch'
    - install appimagetool
    - bash src/ffpolicy/packager/build_appimage.sh <version>
    - upload-artifact: dist/*.AppImage
```

Beyond the original plan: `build-appimage` also runs on a manual
`workflow_dispatch` (with an optional `version` input), not only on tag
pushes - so a downloadable AppImage doesn't require cutting a release tag.
GUI tests run under `QT_QPA_PLATFORM=offscreen` (no `xvfb-run` needed).

---

## 6. Validation & Testing Strategy

### 6.1 Validation engine (`core/validator.py`)

Three layers, run via `validate_document()`:

1. **Schema validation** — validate `PolicyDocument.to_policies_json()` against
   a raw JSON Schema via `jsonschema`, when one is supplied.
2. **Required-field checks** — `ExtensionSettings` `force_installed`/
   `normal_installed` require `install_url`; `allowed`/`blocked` must not set it.
3. **Version compatibility** — warn when a configured policy's
   `min_firefox_version` exceeds the declared target Firefox version.

Results are typed `ValidationIssue(level=ERROR|WARNING, policy, message)` so
both GUI (panel) and CLI (exit code) consume the same output.

### 6.2 Unit tests (`tests/unit/`, as built)

- `test_generator.py`, `test_validator.py`, `test_version_check.py` - core logic.
- `test_resources.py` - bundled `schema_backup.json`/`categories.yaml` parse
  and stay consistent with each other.
- `test_schema_sync.py`, `test_amo_client.py` - fetchers, HTTP mocked via
  `responses`; includes the name-relevance ranking behavior.
- `test_presets.py` - preset loading/expansion (all nine DISA STIG profiles
  share values/rules), `apply_preset()` merge semantics, description/
  recommendation fields.
- `test_gui.py` - `pytest-qt`; form population, live preview, extension
  manager (including the manual-entry fallback), Presets menu structure,
  `PresetDetailsDialog`.

### 6.3 Functional tests (`tests/functional/`)

- `test_export_paths.py` - path resolution for all three targets, the
  overwrite guard, and an OS-level write failure.
- `test_golden.py` - `render_policies_json()`'s determinism against
  `tests/fixtures/golden/sample_policies.json`.
- `test_cli.py` - `validate`/`generate`/`export`/`preview`/`presets`/
  `preset-info`, including the preset-as-baseline + input-file-as-override
  workflow.

### 6.4 Golden-file discipline

Canonical `policies.json` output lives in `tests/fixtures/golden/`.
Regenerate intentionally via `make update-golden` and review the diff in the
PR - this is the safety net for the deterministic-output guarantee.

**Current test count: 72 passing** (`ruff`, `mypy`, and `lint-imports` all
clean as of PR #5).

---

## 7. Execution Roadmap

### Phase 0 — Project scaffolding ✅
- [x] `pyproject.toml`, `src/ffpolicy/` package, tooling (ruff, mypy, pytest).
- [x] CI skeleton: lint + test on push.
- [x] Enforce the "core/models never import gui" rule in CI (`lint-imports`).

### Phase 1 — Core & models (no network, no GUI) ✅
- [x] Pydantic models (`policy_schema`, `policy_document`, `extension`, `amo`).
- [x] Bundle a real `schema_backup.json` + `categories.yaml`.
- [x] `generator.py` + `validator.py` + `version_check.py` with unit tests.
- [x] **Milestone:** generate & validate a `policies.json` fully offline.

### Phase 2 — Fetchers ✅ (with a caveat)
- [x] HTTP base client (retry/timeout/ETag), disk cache with TTL.
- [x] `schema_sync.py`: fetch+parse Mozilla templates → `PolicySchema`.
- [x] `amo_client.py`: search/detail + extraction, mocked tests.
- [x] **Milestone:** AMO search works; falls back to manual entry when it doesn't.
- [ ] Live schema sync currently 404s (Mozilla moved the source format - see
      §2.1); bundled fallback is manually verified and covers this, but the
      live-fetch path itself needs a rewrite - not yet done.

### Phase 3 — CLI ✅
- [x] `cli.py`: `validate`/`generate`/`export`/`preview`, plus `presets`/
      `preset-info` (added for compliance presets, §9).
- [x] **Milestone:** headless end-to-end usable in config-management pipelines.

### Phase 4 — GUI ✅
- [x] `main_window` shell + category tree + JSON preview + highlighter.
- [x] `form_builder` (schema → widgets) + field widgets.
- [x] Extension manager + validation panel + export button.
- [x] Menu bar with a Presets menu (not part of the original plan's File/Edit/
      Schema/Export/Help design - see §9).
- [x] Fixed 1600×900 window sized for FHD displays; shared QSS stylesheet.
- [x] **Milestone:** full visual build-validate-export loop.

### Phase 5 — Packaging ✅
- [x] PyInstaller spec, `build_appimage.sh`, `.desktop`, icon.
- [x] Verified locally: the frozen binary runs correctly with bundled resources.
- [x] CI job producing an `.AppImage` artifact on tag push or manual dispatch.
- [x] **Milestone:** downloadable, self-contained AppImage.
- [ ] Clean-container smoke test on the oldest target distro's glibc baseline
      - not yet done; CI builds on ubuntu-22.04 but hasn't been stress-tested
      against an older host.

### Phase 6 — Hardening ✅
- [x] Functional export + fallback tests.
- [x] Golden-file suite + `update-golden` target.
- [x] Docs: `README.md`, `CLAUDE.md`, this file, `docs/DISA_STIG.md`.

### Phase 7 — Compliance presets ✅ (added after the original plan, PR #4-#5)
- [x] `core/presets.py`: `Preset`/`PresetRule` models, `apply_preset()`
      (overlay onto a `PolicyDocument`, one top-level key at a time).
- [x] Bundled DISA STIG (Mozilla Firefox) preset: all 33 benchmark rules
      parsed from the official XCCDF source; 30 with concrete `policies.json`
      values (merged where multiple rules configure the same policy), 3
      inherently manual/procedural (browser version, DOD root certs, a
      MIME-type allowlist).
- [x] Expanded into one preset per STIG Profile (9 Mission Assurance
      Category / confidentiality combinations - all select the same 33 rules
      for this benchmark, so the resource stores the ruleset once and expands
      it via a `profiles` list rather than duplicating YAML nine times).
- [x] Every rule carries a `description` (why it matters) and
      `recommendation` (the concrete fix), surfaced via CLI `preset-info` and
      the GUI's `PresetDetailsDialog`.
- [x] CLI (`--preset <id>`, `presets`, `preset-info`) and GUI (Presets menu)
      both apply a preset as a baseline that an input file or further manual
      edits then override.
- [x] **Milestone:** `ffpolicy generate my-overrides.yaml --preset
      disa_stig__mac_1_classified -o policies.json` - preset baseline with
      org-specific values layered on top.
- [x] 20 new policy definitions added to `schema_backup.json` to support the
      preset's rules, with `min_firefox_version` values corrected against
      Mozilla's current reference docs (6 of the original 11 bundled
      policies had wrong version numbers, one off by 49 versions).

---

## 8. Data Accuracy Note

The bundled `schema_backup.json` was cross-checked against Mozilla's current
policy reference (`firefox-admin-docs.mozilla.org`, via its GitHub source
`mozilla/enterprise-admin-reference` - the docs site itself isn't reachable
from every network environment, including this project's CI/dev sandbox).
That pass found and fixed:

- A phantom policy name in `categories.yaml` (`CertificatesDescription` -
  not a real policy, a leftover from the old README-table docs format).
- Six wrong `min_firefox_version` values in the original 11 bundled policies.
- A missing `StartPage` enum value (`homepage-locked`) on `Homepage`.

The same pass is what surfaced the Phase 2 schema-sync issue in §2.1/§7.

---

## 9. Compliance Presets — Design Notes

Not part of the original blueprint; added after Phase 6 in response to a
request to support the DISA STIG for Mozilla Firefox. Design decisions worth
recording:

- **Merge, don't overwrite.** Several STIG rules configure different keys of
  the *same* top-level policy (6 rules write into `Preferences`; 2 into
  `EnableTrackingProtection`). The bundled preset stores one pre-merged value
  per policy, computed by hand from all contributing rules - `apply_preset()`
  itself does a simple per-key overlay and doesn't need to know which rules
  contributed to which value.
- **Profiles share a ruleset, not a preset.** DISA STIG's nine profiles select
  identical rules for this benchmark (confirmed by parsing the XCCDF
  `<Profile>` elements' `<select>` lists), so `load_bundled_presets()` expands
  one YAML document's `values`/`rules` into nine `Preset` objects that differ
  only in `id`/`name`/`profile_title`, grouped by a shared `family` name for
  menus. A resource with no `profiles` key still loads as a single preset -
  this is additive, not a requirement future presets must follow.
- **Trust the compliance check over the fix-text example.** One bundled
  value (`FirefoxHome.Locked`) is capitalized against Firefox's actual schema
  and DISA's own `about:policies` check, not copied verbatim from the STIG's
  fix-text example (which uses lowercase `locked` - a value Firefox doesn't
  recognize, so it would silently fail to lock the policy in a real
  deployment despite matching the STIG document literally).
- **Manual items are first-class, not dropped.** Rules with no automatable
  `policies.json` value (`policy: null` in the YAML) are still tracked with a
  `note` explaining why, and surfaced everywhere a preset is: CLI `presets`/
  `preset-info` output and the GUI's post-apply confirmation dialog.

See `docs/DISA_STIG.md` for user-facing usage and the full rule → policy
mapping table.
