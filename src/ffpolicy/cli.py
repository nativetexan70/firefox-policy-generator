"""Headless CLI: generate, validate, and export policies.json from a YAML/JSON input file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from ffpolicy.core.errors import ExportError, FfPolicyError
from ffpolicy.core.generator import export_policies_json, render_policies_json
from ffpolicy.core.paths import ExportTarget, resolve_export_path
from ffpolicy.core.validator import IssueLevel, has_errors, validate_document
from ffpolicy.fetchers.schema_sync import load_bundled_schema, sync_schema
from ffpolicy.models.policy_document import PolicyDocument

app = typer.Typer(help="Generate, validate, and export Firefox enterprise policies.json.")

OfflineOption = Annotated[
    bool, typer.Option(help="Skip network sync; use bundled schema only")
]


def _load_input(path: Path) -> tuple[PolicyDocument, int | None]:
    """Load an input file. Its top level is either a bare policy-name -> value
    mapping, or a `{firefox_version, policies}` wrapper.
    """
    text = path.read_text(encoding="utf-8")
    is_yaml = path.suffix.lower() in (".yaml", ".yml")
    data: Any = yaml.safe_load(text) if is_yaml else json.loads(text)

    if not isinstance(data, dict):
        raise typer.BadParameter(f"{path} must contain a top-level mapping")

    if "policies" in data:
        values = data["policies"]
        firefox_version = data.get("firefox_version")
    else:
        values = data
        firefox_version = None

    return PolicyDocument(values=values), firefox_version


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
    input_file: Annotated[Path, typer.Argument(help="YAML or JSON policy input file")],
    offline: OfflineOption = False,
) -> None:
    """Validate a policy input file. Exits non-zero if any errors are found."""
    document, firefox_version = _load_input(input_file)
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
    input_file: Annotated[Path, typer.Argument(help="YAML or JSON policy input file")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output policies.json path")],
    overwrite: Annotated[bool, typer.Option(help="Overwrite an existing output file")] = False,
    offline: OfflineOption = False,
) -> None:
    """Validate and write policies.json to an explicit output path."""
    document, firefox_version = _load_input(input_file)
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
    input_file: Annotated[Path, typer.Argument(help="YAML or JSON policy input file")],
    target: Annotated[ExportTarget, typer.Option(help="Standard export location")] = (
        ExportTarget.SYSTEM_LINUX
    ),
    custom_path: Annotated[
        Path | None, typer.Option(help="Required when --target=custom")
    ] = None,
    overwrite: Annotated[bool, typer.Option(help="Overwrite an existing output file")] = False,
    offline: OfflineOption = False,
) -> None:
    """Validate and write policies.json to a standard Firefox policy location."""
    document, firefox_version = _load_input(input_file)
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
        written = export_policies_json(document, resolved, overwrite=overwrite)
    except (ExportError, FfPolicyError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote {written}")


@app.command()
def preview(
    input_file: Annotated[Path, typer.Argument(help="YAML or JSON policy input file")],
) -> None:
    """Print the rendered policies.json without writing or validating."""
    document, _firefox_version = _load_input(input_file)
    typer.echo(render_policies_json(document), nl=False)


if __name__ == "__main__":
    app()
