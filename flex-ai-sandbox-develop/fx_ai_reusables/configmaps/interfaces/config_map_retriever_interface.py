from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class ConfigMapDto:
    # This would need to be expanded based on the actual Java ConfigMapDto structure
    # For now just adding placeholder fields
    name: str
    value: str


class IConfigMapRetriever(ABC):
    @abstractmethod
    async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
        """
        Retrieves a config map by name.

        Args:
            configuration_item_name: The name of the configuration item

        Returns:
            Optional ConfigMapDto if found, None otherwise
        """
        pass

    @abstractmethod
    async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
        """
        Retrieves a mandatory config map value by name.

        Args:
            configuration_item_name: The name of the configuration item

        Returns:
            The configuration value as a string

        Raises:
            Exception if the configuration item is not found
        """
        pass

    @abstractmethod
    async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
        """
        Retrieves an optional config map value by name.

        Args:
            configuration_item_name: The name of the configuration item

        Returns:
            The configuration value as a string if found, None otherwise
        """
        pass