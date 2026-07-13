"""Domain and application errors exposed by Pack AI."""


class PackAIError(Exception):
    """Base class for expected Pack AI failures."""


class PackValidationError(PackAIError):
    """Raised when a pack request violates an input contract."""


class ArchiveCreationError(PackAIError):
    """Raised when an archive cannot be completed atomically."""
