"""
Shared validation utilities for Liquid Mapper.
Provides consistent validation logic across all services.
"""
import re
from typing import Optional

from exceptions import ValidationError, PathTraversalError


# Validation regex patterns
VALID_IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
FORBIDDEN_FILENAME_CHARS = re.compile(r'[\\/:<>"\|\?\*\x00-\x1f]')


def validate_identifier(identifier: str, field_name: str) -> None:
    """
    Validate an identifier (resource name, IG name, backend source, etc.).
    Allows only alphanumeric characters, dots, hyphens, and underscores.
    
    Args:
        identifier: The identifier to validate
        field_name: Name of the field for error messages
        
    Raises:
        ValidationError: If identifier contains invalid characters
    """
    if identifier and not VALID_IDENTIFIER_PATTERN.match(identifier):
        raise ValidationError(
            f"Invalid {field_name}: '{identifier}'. "
            f"Only alphanumeric characters, dots, hyphens, and underscores allowed."
        )


def validate_required_string(input_str: str, field_name: str) -> None:
    """
    Validate that a required string input is not empty or None.
    
    Args:
        input_str: The string to validate
        field_name: Name of the field for error messages
        
    Raises:
        ValidationError: If input is empty or None
    """
    if not input_str or not input_str.strip():
        raise ValidationError(f"{field_name} is required and cannot be empty")


def validate_filename_component(component: str, field_name: str) -> None:
    """
    Validate a filename component for path traversal and forbidden characters.
    Stricter than validate_identifier - used for file system operations.
    
    Args:
        component: The component to validate
        field_name: Name of the field for error messages
        
    Raises:
        ValidationError: If component is invalid
        PathTraversalError: If path traversal attempt detected
    """
    if not component or not component.strip():
        raise ValidationError(f"{field_name} is required and cannot be empty")
    
    # Check for path traversal attempts
    if ".." in component or "/" in component or "\\" in component:
        raise PathTraversalError(
            f"Path traversal attempt detected in {field_name}: '{component}'"
        )
    
    # Check for forbidden characters
    if FORBIDDEN_FILENAME_CHARS.search(component):
        raise ValidationError(
            f"Invalid characters in {field_name}: '{component}'. "
            f"Only alphanumeric, dots, hyphens, and underscores allowed."
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing/replacing invalid characters.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename safe for file system use
    """
    # Remove forbidden characters
    sanitized = FORBIDDEN_FILENAME_CHARS.sub('_', filename)
    # Remove any remaining path traversal attempts
    sanitized = sanitized.replace("..", "_")
    return sanitized
