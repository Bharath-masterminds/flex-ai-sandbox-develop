import os
from typing import Optional


class EnvironmentVariableReaderHelper:
    """Wrapper to retrieve environment variables with error handling."""

    @staticmethod
    async def read_mandatory_value(environ_variable_name: str) -> str:
        """Reads a mandatory environment variable. Throws an error if the variable is not set."""

        if environ_variable_name not in os.environ:
            raise EnvironmentError(f"Required environment variable '{environ_variable_name}' is not set.")

        return os.getenv(environ_variable_name)

    @staticmethod
    async def read_optional_value(environ_variable_name: str) -> Optional[str]:
        """Reads an optional environment variable. Returns None if the variable is not set."""

        if environ_variable_name in os.environ:
            return os.getenv(environ_variable_name)
        else:
            return None