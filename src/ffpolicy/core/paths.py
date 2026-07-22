"""Resolution of standard Firefox policy install-path locations."""

from __future__ import annotations

import platform
import sys
from enum import Enum
from pathlib import Path


class ExportTarget(str, Enum):
    SYSTEM_LINUX = "system_linux"
    LINUX_LIB64_DISTRIBUTION = "linux_lib64_distribution"
    LINUX_LIB_DISTRIBUTION = "linux_lib_distribution"
    LINUX_FIREFOX_ESR = "linux_firefox_esr"
    LINUX_OPT_DISTRIBUTION = "linux_opt_distribution"
    LINUX_SNAP = "linux_snap"
    LINUX_FLATPAK_SYSTEM = "linux_flatpak_system"
    LINUX_FLATPAK_USER = "linux_flatpak_user"
    DISTRIBUTION = "distribution"
    CUSTOM = "custom"


# Absolute, well-known Linux locations Firefox reads policies.json from,
# keyed by the packaging convention that puts Firefox there. All of these
# live under root-owned directories and normally require elevated privileges
# to write.
#
# The Firefox snap has a read-only installation directory, so - per Mozilla's
# own guidance (bugzilla.mozilla.org/show_bug.cgi?id=1717216) and Ubuntu's
# snap enterprise-policy docs - it falls back to reading the same
# /etc/firefox/policies/policies.json as native deb/rpm installs, rather than
# a snap-specific path.
LINUX_SYSTEM_PATHS: dict[ExportTarget, str] = {
    ExportTarget.SYSTEM_LINUX: "/etc/firefox/policies/policies.json",
    ExportTarget.LINUX_LIB64_DISTRIBUTION: "/usr/lib64/firefox/distribution/policies.json",
    ExportTarget.LINUX_LIB_DISTRIBUTION: "/usr/lib/firefox/distribution/policies.json",
    ExportTarget.LINUX_FIREFOX_ESR: "/usr/lib/firefox-esr/distribution/policies.json",
    ExportTarget.LINUX_OPT_DISTRIBUTION: "/opt/firefox/distribution/policies.json",
    ExportTarget.LINUX_SNAP: "/etc/firefox/policies/policies.json",
}

# Flatpak Firefox's sandbox can't see the host's /etc, /usr, or /opt, so
# Mozilla exposes policies.json through a flatpak "extension" mount point
# instead (bugzilla.mozilla.org/show_bug.cgi?id=1682462): a file dropped at
# this host path appears inside the sandbox as /app/etc/firefox/policies/
# policies.json. The path is architecture-qualified; `platform.machine()`
# (e.g. "x86_64", "aarch64") matches flatpak's own arch naming on Linux.
_FLATPAK_EXTENSION_SUFFIX = (
    "flatpak/extension/org.mozilla.firefox.systemconfig/{arch}/stable/policies/policies.json"
)


def _flatpak_policy_path(root: Path) -> Path:
    return root / _FLATPAK_EXTENSION_SUFFIX.format(arch=platform.machine())


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

    if target is ExportTarget.LINUX_FLATPAK_SYSTEM:
        return _flatpak_policy_path(Path("/var/lib"))

    if target is ExportTarget.LINUX_FLATPAK_USER:
        return _flatpak_policy_path(Path.home() / ".local/share")

    if target in LINUX_SYSTEM_PATHS:
        return Path(LINUX_SYSTEM_PATHS[target])

    raise ValueError(f"Unhandled export target: {target}")


def target_requires_privileges(target: ExportTarget) -> bool:
    """Whether the target's default location is typically root-owned.

    `CUSTOM`, `DISTRIBUTION` (a path relative to the current working
    directory), and `LINUX_FLATPAK_USER` (under the user's home directory)
    are excluded - everything else resolves under `/etc`, `/usr`, `/opt`,
    `/var/lib`, or the macOS `/Library`, none of which a regular user can
    write to.
    """
    return target not in (
        ExportTarget.CUSTOM,
        ExportTarget.DISTRIBUTION,
        ExportTarget.LINUX_FLATPAK_USER,
    )


def discover_installed_policies() -> list[tuple[ExportTarget, Path]]:
    """Find policies.json files already present at standard system locations.

    Checks every target's default location except `CUSTOM` (no fixed path)
    and `DISTRIBUTION` (relative to the current working directory, not a
    real install location). Several targets share a path (e.g. `LINUX_SNAP`
    and `SYSTEM_LINUX`), so each existing path is reported once, under the
    first target that resolves to it.
    """
    found: list[tuple[ExportTarget, Path]] = []
    seen: set[Path] = set()
    for target in ExportTarget:
        if target in (ExportTarget.CUSTOM, ExportTarget.DISTRIBUTION):
            continue
        path = resolve_export_path(target)
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            found.append((target, path))
    return found
