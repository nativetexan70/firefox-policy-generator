"""Load an already-deployed policies.json (found on this system) into a PolicyDocument."""

from __future__ import annotations

import json
from pathlib import Path

from ffpolicy.core.errors import ExportError
from ffpolicy.models.policy_document import PolicyDocument


def import_policies_json(path: str | Path) -> PolicyDocument:
    """Parse `path`'s `{"policies": {...}}` shape (or a bare policy-name
    mapping) into a `PolicyDocument`, for editing or re-exporting a policy
    set that's already installed somewhere on this machine.
    """
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExportError(f"failed to read {source}: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExportError(f"{source} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ExportError(f"{source} must contain a top-level JSON object")

    policies = data.get("policies", data)
    if not isinstance(policies, dict):
        raise ExportError(f'{source}\'s "policies" value must be a JSON object')

    return PolicyDocument(values=dict(policies))
