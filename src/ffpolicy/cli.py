"""Headless CLI: generate, validate, and export policies.json from a YAML/JSON input file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from ffpolicy.core.errors import ExportError, FfPolicyError
from ffpolicy.core.generator import export_policies_json, render_policies_json
from ffpolicy.core.paths import ExportTarget, resolve_export_path, target_requires_privileges
from ffpolicy.core.presets import Preset, apply_preset, load_bundled_presets, load_preset
from ffpolicy.core.validator import IssueLevel, has_errors, validate_document
from ffpolicy.fetchers.schema_sync import load_bundled_schema, sync_schema
from ffpolicy.models.policy_document import PolicyDocument

app = typer.Typer(help="Generate, validate, and export Firefox enterprise policies.json.")

OfflineOption = Annotated[
    bool, typer.Option(help="Skip network sync; use bundled schema only")
]
InputFileArgument = Annotated[
    Path | None, typer.Argument(help="YAML or JSON policy input file (optional with --preset)")
]
PresetOption = Annotated[
    str | None,
    typer.Option(
        help=(
            "Apply a bundled preset id (see `ffpolicy presets`, "
            "e.g. disa_stig__mac_1_classified) as a baseline before the input file"
        )
    ),
]


def _load_document(
    input_file: Path | None, preset_id: str | None
) -> tuple[PolicyDocument, int | None]:
    """Build a document from an optional preset baseline plus an optional input
    file. The input file's top level is either a bare policy-name -> value
    mapping, or a `{firefox_version, policies}` wrapper. Input file values
    override the preset's for any key both define, so a preset can be applied
    as a starting point and then hand-tuned.
    """
    if input_file is None and preset_id is None:
        raise typer.BadParameter("Provide an input file, --preset, or both")

    document = PolicyDocument()
    firefox_version = None

    if preset_id is not None:
        try:
            apply_preset(document, load_preset(preset_id))
        except KeyError as exc:
            raise typer.BadParameter(str(exc)) from exc

    if input_file is not None:
        text = input_file.read_text(encoding="utf-8")
        is_yaml = input_file.suffix.lower() in (".yaml", ".yml")
        data: Any = yaml.safe_load(text) if is_yaml else json.loads(text)

        if not isinstance(data, dict):
            raise typer.BadParameter(f"{input_file} must contain a top-level mapping")

        if "policies" in data:
            document.values.update(data["policies"])
            firefox_version = data.get("firefox_version")
        else:
            document.values.update(data)

    return document, firefox_version


def _load_policy_schema(offline: bool):
    if offline:
        return load_bundled_schema(), "bundled"
    return sync_schema()


def _print_issues(issues: list) -> None:
    for issue in issues:
        is_error = issue.level is IssueLevel.ERROR
        prefix = "ERROR" if is_error else "WARNING"
        typer.echo(f"[{prefix}] {issue.policy}: {issue.message}", err=is_error)


@app.command()
def validate(
    input_file: InputFileArgument = None,
    preset: PresetOption = None,
    offline: OfflineOption = False,
) -> None:
    """Validate a policy input file and/or preset. Exits non-zero if any errors are found."""
    document, firefox_version = _load_document(input_file, preset)
    policy_schema, tier = _load_policy_schema(offline)
    typer.echo(f"Schema: {tier}")

    issues = validate_document(
        document, policy_schema=policy_schema, target_firefox_version=firefox_version
    )
    _print_issues(issues)

    if has_errors(issues):
        typer.echo("Validation FAILED", err=True)
        raise typer.Exit(code=1)
    typer.echo("Validation OK")


@app.command()
def generate(
    input_file: InputFileArgument = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output policies.json path")
    ] = Path("policies.json"),
    preset: PresetOption = None,
    overwrite: Annotated[bool, typer.Option(help="Overwrite an existing output file")] = False,
    offline: OfflineOption = False,
) -> None:
    """Validate and write policies.json to an explicit output path."""
    document, firefox_version = _load_document(input_file, preset)
    policy_schema, _tier = _load_policy_schema(offline)

    issues = validate_document(
        document, policy_schema=policy_schema, target_firefox_version=firefox_version
    )
    _print_issues(issues)
    if has_errors(issues):
        typer.echo("Validation FAILED - not writing output", err=True)
        raise typer.Exit(code=1)

    try:
        written = export_policies_json(document, output, overwrite=overwrite)
    except ExportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote {written}")


@app.command()
def export(
    input_file: InputFileArgument = None,
    target: Annotated[ExportTarget, typer.Option(help="Standard export location")] = (
        ExportTarget.SYSTEM_LINUX
    ),
    custom_path: Annotated[
        Path | None, typer.Option(help="Required when --target=custom")
    ] = None,
    preset: PresetOption = None,
    overwrite: Annotated[bool, typer.Option(help="Overwrite an existing output file")] = False,
    elevate: Annotated[
        bool,
        typer.Option(
            help=(
                "Retry via pkexec/sudo if the target is a root-owned system "
                "location (/etc, /usr, /opt) and a plain write is denied"
            )
        ),
    ] = False,
    offline: OfflineOption = False,
) -> None:
    """Validate and write policies.json to a standard Firefox policy location.

    Standard Linux locations (--target system_linux/linux_lib64_distribution/
    linux_lib_distribution/linux_firefox_esr/linux_opt_distribution) resolve to
    root-owned paths and normally require --elevate to write.
    """
    document, firefox_version = _load_document(input_file, preset)
    policy_schema, _tier = _load_policy_schema(offline)

    issues = validate_document(
        document, policy_schema=policy_schema, target_firefox_version=firefox_version
    )
    _print_issues(issues)
    if has_errors(issues):
        typer.echo("Validation FAILED - not writing output", err=True)
        raise typer.Exit(code=1)

    try:
        resolved = resolve_export_path(target, custom_path)
        if elevate and target_requires_privileges(target):
            typer.echo(f"{resolved} may require elevated privileges - using pkexec/sudo if needed")
        written = export_policies_json(
            document, resolved, overwrite=overwrite, allow_privilege_escalation=elevate
        )
    except (ExportError, FfPolicyError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote {written}")


@app.command()
def preview(
    input_file: InputFileArgument = None,
    preset: PresetOption = None,
) -> None:
    """Print the rendered policies.json without writing or validating."""
    document, _firefox_version = _load_document(input_file, preset)
    typer.echo(render_policies_json(document), nl=False)


@app.command(name="presets")
def list_presets() -> None:
    """List bundled configuration presets (e.g. DISA STIG profiles).

    Presets sharing a `family` (e.g. the nine DISA STIG Mission Assurance
    Category / confidentiality profiles) apply an identical ruleset - only
    the id/name/profile differ - so they're grouped under one header.
    """
    presets = load_bundled_presets()
    if not presets:
        typer.echo("No bundled presets found.")
        return

    standalone = sorted(
        (p for p in presets.values() if p.family is None), key=lambda p: p.id
    )
    families: dict[str, list[Preset]] = {}
    for preset in presets.values():
        if preset.family is not None:
            families.setdefault(preset.family, []).append(preset)

    for preset in standalone:
        typer.echo(f"{preset.id}  -  {preset.name}")
        typer.echo(f"  {preset.description}")
        typer.echo(f"  Source: {preset.source}")
        _print_rule_summary(preset)
        typer.echo("")

    for family_name in sorted(families):
        variants = sorted(families[family_name], key=lambda p: p.profile_id or "")
        first = variants[0]
        typer.echo(f"{family_name}")
        typer.echo(f"  {first.description}")
        typer.echo(f"  Source: {first.source}")
        _print_rule_summary(first)
        typer.echo("  Profiles:")
        for variant in variants:
            typer.echo(f"    {variant.id}  -  {variant.profile_title}")
        typer.echo(
            "  Run `ffpolicy preset-info <id>` for the full rule-by-rule "
            "description and recommendation for any profile above."
        )
        typer.echo("")


def _print_rule_summary(preset: Preset) -> None:
    typer.echo(
        f"  {len(preset.automated_rules)} rule(s) applied automatically, "
        f"{len(preset.manual_rules)} require manual/procedural action"
    )
    for rule in preset.manual_rules:
        typer.echo(f"    [{rule.id} {rule.severity}] {rule.title}")
        if rule.note:
            typer.echo(f"      -> {rule.note}")


@app.command(name="preset-info")
def preset_info(
    preset_id: Annotated[str, typer.Argument(help="Preset id, e.g. from `ffpolicy presets`")],
) -> None:
    """Show every rule in a preset with its setting description and recommendation."""
    try:
        preset = load_preset(preset_id)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"{preset.name}")
    typer.echo(f"{preset.description}")
    typer.echo(f"Source: {preset.source}")
    typer.echo("")

    for rule in sorted(preset.rules, key=lambda r: r.id):
        policy = rule.policy or "(manual/procedural - no policies.json setting)"
        typer.echo(f"[{rule.id}] {rule.version}  severity={rule.severity}  policy={policy}")
        typer.echo(f"  {rule.title}")
        typer.echo(f"  Description: {rule.description}")
        typer.echo(f"  Recommendation: {rule.recommendation}")
        if rule.note:
            typer.echo(f"  Note: {rule.note}")
        typer.echo("")


if __name__ == "__main__":
    app()
