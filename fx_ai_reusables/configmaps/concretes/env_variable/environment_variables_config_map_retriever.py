import os
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever, ConfigMapDto


class EnvironmentVariablesConfigMapRetriever(IConfigMapRetriever):
    """
    Implementation of IConfigMapRetriever that retrieves configuration from environment variables.

    This implementation uses the prefix pattern where config maps are identified by a prefix
    in environment variable names.
    """

    async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
        """
        Retrieves all environment variables with the specified prefix as a ConfigMapDto.

        Args:
            configuration_item_name: The prefix used to identify environment variables
                                    belonging to this config map

        Returns:
            ConfigMapDto containing all matching environment variables, or None if no matches found
        """
        prefix = f"{configuration_item_name}_"
        values = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Strip the prefix to get the config property name
                config_key = key[len(prefix):]
                values[config_key] = value

        if not values:
            return None

        return ConfigMapDto(name=configuration_item_name, values=values)

    async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
        """
        Retrieves a mandatory config value from environment variables.

        Args:
            configuration_item_name: The full name of the environment variable

        Returns:
            The configuration value

        Raises:
            KeyError if the environment variable is not found
        """
        value = os.environ.get(configuration_item_name)
        if value is None:
            raise KeyError(f"Mandatory configuration '{configuration_item_name}' not found in environment variables")
        return value

    async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
        """
        Retrieves an optional config value from environment variables.

        Args:
            configuration_item_name: The full name of the environment variable

        Returns:
            The configuration value if found, None otherwise
        """
        return os.environ.get(configuration_item_name)