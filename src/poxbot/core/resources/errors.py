class ResourceError(Exception):
    """Base exception for resource-related errors."""


class ResourcePathError(ResourceError, ValueError):
    """Raised when a resource address or resolved path is invalid."""


class UnknownResourceSchemeError(ResourceError):
    """Raised when a resource address uses an unregistered scheme."""


class ResourcePermissionError(ResourceError, PermissionError):
    """Raised when an operation is forbidden for a resource scheme."""


class ResourceSchemeAlreadyRegisteredError(ResourceError):
    """Raised when attempting to register an existing scheme."""
