"""Firefox target-version compatibility checks for configured policies."""

from __future__ import annotations

from ffpolicy.models.policy_schema import PolicyDefinition


def is_compatible(definition: PolicyDefinition, target_firefox_version: int) -> bool:
    """Whether `definition` is usable on `target_firefox_version`."""
    if definition.min_firefox_version is not None and (
        target_firefox_version < definition.min_firefox_version
    ):
        return False
    if definition.max_firefox_version is not None and (
        target_firefox_version > definition.max_firefox_version
    ):
        return False
    return True


def incompatibility_reason(
    definition: PolicyDefinition, target_firefox_version: int
) -> str | None:
    """Human-readable reason `definition` is incompatible, or None if compatible."""
    if definition.min_firefox_version is not None and (
        target_firefox_version < definition.min_firefox_version
    ):
        return (
            f"{definition.name} requires Firefox >= {definition.min_firefox_version}, "
            f"target is {target_firefox_version}"
        )
    if definition.max_firefox_version is not None and (
        target_firefox_version > definition.max_firefox_version
    ):
        return (
            f"{definition.name} requires Firefox <= {definition.max_firefox_version}, "
            f"target is {target_firefox_version}"
        )
    return None
