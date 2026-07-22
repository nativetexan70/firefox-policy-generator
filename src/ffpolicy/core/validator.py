"""Three-layer validation: JSON Schema, per-policy required-field rules, version checks."""

from __future__ import annotations

from enum import Enum

import jsonschema
from pydantic import BaseModel

from ffpolicy.core.version_check import incompatibility_reason
from ffpolicy.models.extension import MODES_REQUIRING_INSTALL_URL, InstallationMode
from ffpolicy.models.policy_document import PolicyDocument
from ffpolicy.models.policy_schema import PolicySchema


class IssueLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    level: IssueLevel
    policy: str
    message: str


def _validate_json_schema(document: PolicyDocument, json_schema: dict) -> list[ValidationIssue]:
    validator = jsonschema.Draft7Validator(json_schema)
    issues: list[ValidationIssue] = []
    for error in validator.iter_errors(document.to_policies_json()):
        policy = error.path[1] if len(error.path) > 1 else (error.path[0] if error.path else "*")
        issues.append(
            ValidationIssue(level=IssueLevel.ERROR, policy=str(policy), message=error.message)
        )
    return issues


def _validate_extension_settings(document: PolicyDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    settings = document.values.get("ExtensionSettings")
    if not isinstance(settings, dict):
        return issues

    for guid, entry in settings.items():
        if not isinstance(entry, dict):
            continue
        mode = entry.get("installation_mode")
        install_url = entry.get("install_url")
        try:
            mode_enum = InstallationMode(mode)
        except ValueError:
            issues.append(
                ValidationIssue(
                    level=IssueLevel.ERROR,
                    policy="ExtensionSettings",
                    message=f"{guid}: unknown installation_mode {mode!r}",
                )
            )
            continue

        requires_url = mode_enum in MODES_REQUIRING_INSTALL_URL
        if requires_url and not install_url:
            issues.append(
                ValidationIssue(
                    level=IssueLevel.ERROR,
                    policy="ExtensionSettings",
                    message=f"{guid}: installation_mode {mode_enum.value!r} requires install_url",
                )
            )
        elif not requires_url and install_url:
            issues.append(
                ValidationIssue(
                    level=IssueLevel.ERROR,
                    policy="ExtensionSettings",
                    message=(
                        f"{guid}: installation_mode {mode_enum.value!r} must not set install_url"
                    ),
                )
            )
    return issues


def _validate_versions(
    document: PolicyDocument, schema: PolicySchema, target_firefox_version: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for name in document.values:
        definition = schema.policies.get(name)
        if definition is None:
            continue
        reason = incompatibility_reason(definition, target_firefox_version)
        if reason:
            issues.append(ValidationIssue(level=IssueLevel.WARNING, policy=name, message=reason))
    return issues


def validate_document(
    document: PolicyDocument,
    *,
    json_schema: dict | None = None,
    policy_schema: PolicySchema | None = None,
    target_firefox_version: int | None = None,
) -> list[ValidationIssue]:
    """Run all applicable validation layers and return the combined issue list."""
    issues: list[ValidationIssue] = []

    if json_schema is not None:
        issues.extend(_validate_json_schema(document, json_schema))

    issues.extend(_validate_extension_settings(document))

    if policy_schema is not None and target_firefox_version is not None:
        issues.extend(_validate_versions(document, policy_schema, target_firefox_version))

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.level is IssueLevel.ERROR for issue in issues)
