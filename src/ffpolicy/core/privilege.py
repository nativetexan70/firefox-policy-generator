"""Elevated writes for Linux/macOS system policy locations (e.g. /etc, /usr, /opt)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ffpolicy.core.errors import ExportError

# Preference order: pkexec pops a native PolicyKit dialog (works from a GUI
# with no controlling terminal); sudo is the CLI/terminal fallback.
_ESCALATION_TOOLS = ("pkexec", "sudo")


def find_escalation_tool() -> str | None:
    """Return the first available privilege-escalation helper on PATH, if any."""
    for tool in _ESCALATION_TOOLS:
        if shutil.which(tool):
            return tool
    return None


def write_with_escalation(content: str, target: Path) -> Path:
    """Write `content` to `target` via `pkexec`/`sudo install`, creating parent
    directories as needed. Streams are left inherited (not captured) so a
    sudo password prompt or pkexec auth dialog can actually reach the user.
    """
    tool = find_escalation_tool()
    if tool is None:
        raise ExportError(
            f"{target} requires elevated privileges to write, and neither "
            "pkexec nor sudo is available on this system. Re-run this command "
            "as root, or export to a custom path and copy it into place manually."
        )

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False, suffix=".json"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [tool, "install", "-D", "-m", "644", str(tmp_path), str(target)]
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise ExportError(
            f"failed to write {target} with elevated privileges via {tool} "
            f"(exit code {result.returncode})"
        )

    return target
