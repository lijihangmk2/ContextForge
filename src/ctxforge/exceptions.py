"""ctxforge exceptions."""


class CForgeError(Exception):
    """Base exception for all ctxforge errors."""


class ProjectNotFoundError(CForgeError):
    """Raised when .ctxforge/ directory is not found."""


class InvalidProjectError(CForgeError):
    """Raised when project.toml is invalid or malformed."""


class ProfileNotFoundError(CForgeError):
    """Raised when a requested profile does not exist."""


class InvalidProfileError(CForgeError):
    """Raised when profile.toml is invalid or malformed."""


class CliNotFoundError(CForgeError):
    """Raised when no AI CLI tool is detected."""


class RunnerError(CForgeError):
    """Raised when a CLI runner fails to execute."""
