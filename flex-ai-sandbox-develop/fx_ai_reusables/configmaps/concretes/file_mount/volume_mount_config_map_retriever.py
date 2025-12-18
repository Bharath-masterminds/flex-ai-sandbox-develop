import logging
import os
import re
from pathlib import Path
from re import RegexFlag
from typing import Optional

from fx_ai_reusables.configmaps.base.config_map_validator import ConfigMapValidator
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import ConfigMapDto, IConfigMapRetriever


class VolumeMountConfigMapRetriever(IConfigMapRetriever):
    ENVIRONMENT_OR_SYSTEM_PROPERTY_NAME_PREFIX: str = "configmaps."
    DEFAULT_FILE_NAME_PREFIX: str = "/etc/configmaps/"
    CONFIG_MAP_NAME_REGEX: re.RegexFlag = r"^[a-zA-Z0-9._-]+$"

    def __init__(self, logger: Optional[logging.Logger] = None):
        if logger is None:
            logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self._logger = logger

    async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
        dto: Optional[ConfigMapDto] = await self.retrieve_config_map(configuration_item_name)
        if dto is None:
            raise ValueError(f"Missing config map: {configuration_item_name}")
        return dto.value

    async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
        dto: Optional[ConfigMapDto] = await self.retrieve_config_map(configuration_item_name)
        return None if dto is None else dto.value

    async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
        self._logger.debug("Attempting retrieval for config map: %s", configuration_item_name)

        if not re.match(self._get_config_map_name_regex(), configuration_item_name):
            raise ValueError(f"Config map name did not match regex: {configuration_item_name}")

        env_key: str = self._get_environment_or_system_property_name_prefix() + configuration_item_name
        self._logger.debug("Calculated environment key: %s", env_key)

        file_path: str = os.environ.get(env_key)
        if not file_path:
            file_path = self._get_default_file_name_prefix() + configuration_item_name
            self._logger.debug("Using default file path: %s", file_path)

        if not file_path.strip():
            self._logger.debug("Configuration filename blank.")
            return None

        path_obj: Path = Path(file_path)
        if not path_obj.exists():
            self._logger.debug("Config file not found: %s", file_path)
            return None

        self._logger.debug("Reading config map file: %s", file_path)
        try:
            content: str = path_obj.read_text(encoding="utf-8")
        except OSError as ex:
            raise IOError(f"Error reading config map file: {file_path}") from ex

        ConfigMapValidator.check_for_name_and_value_are_same(configuration_item_name, content)

        if not content.strip():
            self._logger.debug("Value of config map is empty: %s", configuration_item_name)
            return None

        return ConfigMapDto(configuration_item_name,
                            content)

    # Protected-style extension points
    def _get_environment_or_system_property_name_prefix(self) -> str:
        return self.ENVIRONMENT_OR_SYSTEM_PROPERTY_NAME_PREFIX

    def _get_default_file_name_prefix(self) -> str:
        return self.DEFAULT_FILE_NAME_PREFIX

    def _get_config_map_name_regex(self) -> RegexFlag:
        return self.CONFIG_MAP_NAME_REGEX
