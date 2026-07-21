"""Assemble a PolicyDocument into a policies.json file on disk."""

from __future__ import annotations

import json
from pathlib import Path

from ffpolicy.core.errors import ExportError
from ffpolicy.models.policy_document import PolicyDocument

INDENT = 2


def render_policies_json(document: PolicyDocument) -> str:
    """Render deterministic, byte-identical JSON text for the given document."""
    return json.dumps(document.to_policies_json(), indent=INDENT, sort_keys=True) + "\n"


def export_policies_json(
    document: PolicyDocument, path: str | Path, *, overwrite: bool = False
) -> Path:
    """Write `policies.json` to `path`, creating parent directories as needed."""
    target = Path(path)
    if target.exists() and not overwrite:
        raise ExportError(f"{target} already exists (pass overwrite=True to replace it)")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_policies_json(document), encoding="utf-8")
    except OSError as exc:
        raise ExportError(f"failed to write {target}: {exc}") from exc

    return target
