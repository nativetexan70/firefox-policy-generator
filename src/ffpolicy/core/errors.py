"""Typed exceptions raised by core logic."""


class FfPolicyError(Exception):
    """Base class for all ffpolicy core errors."""


class ValidationError(FfPolicyError):
    """Raised when a policy document fails validation and cannot be exported."""


class SchemaLoadError(FfPolicyError):
    """Raised when no policy schema could be obtained (live, cache, or bundled)."""


class ExportError(FfPolicyError):
    """Raised when writing policies.json to a target path fails."""
