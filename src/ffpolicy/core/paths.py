"""Resolution of standard Firefox policy install-path locations."""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path


class ExportTarget(str, Enum):
    SYSTEM_LINUX = "system_linux"
    LINUX_LIB64_DISTRIBUTION = "linux_lib64_distribution"
    LINUX_LIB_DISTRIBUTION = "linux_lib_distribution"
    LINUX_FIREFOX_ESR = "linux_firefox_esr"
    LINUX_OPT_DISTRIBUTION = "linux_opt_distribution"
    DISTRIBUTION = "distribution"
    CUSTOM = "custom"


# Absolute, well-known Linux locations Firefox reads policies.json from,
# keyed by the packaging convention that puts Firefox there. All of these
# live under root-owned directories and normally require elevated privileges
# to write.
LINUX_SYSTEM_PATHS: dict[ExportTarget, str] = {
    ExportTarget.SYSTEM_LINUX: "/etc/firefox/policies/policies.json",
    ExportTarget.LINUX_LIB64_DISTRIBUTION: "/usr/lib64/firefox/distribution/policies.json",
    ExportTarget.LINUX_LIB_DISTRIBUTION: "/usr/lib/firefox/distribution/policies.json",
    ExportTarget.LINUX_FIREFOX_ESR: "/usr/lib/firefox-esr/distribution/policies.json",
    ExportTarget.LINUX_OPT_DISTRIBUTION: "/opt/firefox/distribution/policies.json",
}


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

    if target is ExportTarget.DISTRIBUTION:
        return Path("distribution/policies.json")

    if target is ExportTarget.SYSTEM_LINUX and sys.platform == "darwin":
        return Path("/Library/Application Support/Mozilla/policies.json")

    if target in LINUX_SYSTEM_PATHS:
        return Path(LINUX_SYSTEM_PATHS[target])

    raise ValueError(f"Unhandled export target: {target}")


def target_requires_privileges(target: ExportTarget) -> bool:
    """Whether the target's default location is typically root-owned.

    `CUSTOM` and `DISTRIBUTION` (a path relative to the current working
    directory) are excluded - everything else resolves under `/etc`, `/usr`,
    `/opt`, or the macOS `/Library`, none of which a regular user can write to.
    """
    return target not in (ExportTarget.CUSTOM, ExportTarget.DISTRIBUTION)
