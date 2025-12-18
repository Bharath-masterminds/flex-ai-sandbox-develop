from dataclasses import dataclass
from typing import final


@dataclass(frozen=True)
class ConfigMapDto:
    """
    Immutable data class representing a configuration map entry.
    Equivalent to the Java ConfigMapDto class.
    """
    configuration_name: str
    configuration_value: str

    def get_config_map_name(self) -> str:
        """Returns the configuration name."""
        return self.configuration_name

    def get_config_map_value(self) -> str:
        """Returns the configuration value."""
        return self.configuration_value