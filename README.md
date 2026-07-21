# fedora-policy-generator

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

Input files are YAML or JSON, either a bare `policy-name: value` mapping or a
`{firefox_version, policies}` wrapper - see `tests/fixtures/sample_input.yaml`.
Pass `--offline` to skip the live Mozilla schema sync and use the bundled fallback.

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
