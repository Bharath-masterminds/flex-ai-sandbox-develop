"""
Custom exceptions for Liquid Mapper application.
Following OpsResolve pattern of using standard Python exceptions with descriptive messages.
"""


class LiquidMapperError(Exception):
    """Base exception for all Liquid Mapper errors."""
    pass


class MappingNotFoundError(LiquidMapperError):
    """Raised when a requested mapping table cannot be found."""
    pass


class FileStorageError(LiquidMapperError):
    """Raised when file storage operations fail."""
    pass


class ContextDBError(LiquidMapperError):
    """Raised when context database operations fail."""
    pass


class PromptBuildError(LiquidMapperError):
    """Raised when prompt building fails."""
    pass


class ValidationError(LiquidMapperError):
    """Raised when input validation fails."""
    pass


class PathTraversalError(ValidationError):
    """Raised when path traversal attack is detected."""
    pass
