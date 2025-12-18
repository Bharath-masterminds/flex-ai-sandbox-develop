# secret_definition.py
from dataclasses import dataclass


@dataclass
class SecretDefinition:
    secret_name: str
    environment_or_system_property_name: str
    default_full_file_name: str

    def get_environment_or_system_property_name(self) -> str:
        return self.environment_or_system_property_name

    def get_default_full_file_name(self) -> str:
        return self.default_full_file_name

    def __str__(self) -> str:
        return f"SecretName='{self.secret_name}', EnvironmentOrSystemPropertyName='{self.environment_or_system_property_name}', DefaultFullFileName='{self.default_full_file_name}'"
