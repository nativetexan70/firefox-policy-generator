"""Resolution of standard Firefox policy install-path locations."""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path


class ExportTarget(str, Enum):
    SYSTEM_LINUX = "system_linux"
    DISTRIBUTION = "distribution"
    CUSTOM = "custom"


def resolve_export_path(target: ExportTarget, custom_path: str | Path | None = None) -> Path:
    """Return the `policies.json` path for a given export target.

    `CUSTOM` requires `custom_path`; the file itself (not just a directory)
    may be passed, in which case it is used as-is.
    """
    if target is ExportTarget.CUSTOM:
        if custom_path is None:
            raise ValueError("custom_path is required for ExportTarget.CUSTOM")
        path = Path(custom_path)
        return path if path.suffix == ".json" else path / "policies.json"

    if target is ExportTarget.SYSTEM_LINUX:
        if sys.platform == "darwin":
            return Path("/Library/Application Support/Mozilla/policies.json")
        return Path("/etc/firefox/policies/policies.json")

    if target is ExportTarget.DISTRIBUTION:
        return Path("distribution/policies.json")

    raise ValueError(f"Unhandled export target: {target}")
