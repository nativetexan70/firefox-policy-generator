"""Assemble a PolicyDocument into a policies.json file on disk."""

from __future__ import annotations

import json
from pathlib import Path

from ffpolicy.core.errors import ExportError
from ffpolicy.core.privilege import write_with_escalation
from ffpolicy.models.policy_document import PolicyDocument

INDENT = 2


def render_policies_json(document: PolicyDocument) -> str:
    """Render deterministic, byte-identical JSON text for the given document."""
    return json.dumps(document.to_policies_json(), indent=INDENT, sort_keys=True) + "\n"


def export_policies_json(
    document: PolicyDocument,
    path: str | Path,
    *,
    overwrite: bool = False,
    allow_privilege_escalation: bool = False,
) -> Path:
    """Write `policies.json` to `path`, creating parent directories as needed.

    Standard Linux/macOS policy locations (`/etc`, `/usr`, `/opt`, `/Library`)
    are root-owned. If a plain write is denied and `allow_privilege_escalation`
    is set, retry via `pkexec`/`sudo` (see `core.privilege`); otherwise the
    permission error is surfaced with a hint to opt into escalation.
    """
    target = Path(path)
    if target.exists() and not overwrite:
        raise ExportError(f"{target} already exists (pass overwrite=True to replace it)")

    content = render_policies_json(document)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        if not allow_privilege_escalation:
            raise ExportError(
                f"permission denied writing {target} - pass "
                "allow_privilege_escalation=True (CLI: --elevate) to retry via "
                "pkexec/sudo, or choose a path you own"
            ) from exc
        return write_with_escalation(content, target)
    except OSError as exc:
        raise ExportError(f"failed to write {target}: {exc}") from exc

    return target
