import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Sequence, Dict, Pattern

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import (
    IConfigMapRetriever,
    ConfigMapDto,
)


class LocalFileConfigMapRetriever(IConfigMapRetriever):
    """
    Developer-local file based ConfigMap retriever (non-production).
    Merges multiple *.properties style files (key=value per line) into one map; later files override earlier ones.
    """

    ERROR_MSG_PROPERTIES_FILE_NAMES_IS_NULL_OR_EMPTY = "properties_file_names is null or empty"
    ERROR_MSG_PROPERTIES_FILE_NAME_IS_BLANK = "Encountered blank properties file name"
    ERROR_MSG_RETRIEVE_CONFIG_MAP_FAILURE = 'Failure retrieving ConfigMap value (configuration_item_name="%s")'
    ERROR_MSG_CONFIG_MAP_NAME_REGEX_VALIDATION_FAILED = (
        'ConfigMap name "%s" failed regex validation (pattern="%s")'
    )
    ERROR_MSG_MISSING_CONFIG_MAP = 'Missing mandatory ConfigMap "%s"'
    LOG_MSG_ATTEMPTING_RETRIEVAL = 'Attempting ConfigMap retrieval (name="%s")'
    LOG_MSG_CONFIG_MAP_NOT_FOUND_IN_PROPERTY_FILES = (
        'ConfigMap not found in property files (names="%s", configMapName="%s")'
    )
    LOG_MSG_CONFIG_MAP_VALUE_EMPTY = 'Value of ConfigMap is empty (name="%s")'
    DEFAULT_CONFIG_MAP_NAME_REGEX = r"^[A-Za-z0-9_.\-]+$"

    def __init__(
        self,
        properties_file_names: Sequence[str],
        *,
        base_directory: Optional[Path] = None,
        config_map_name_regex: str = DEFAULT_CONFIG_MAP_NAME_REGEX,
        encoding: str = "utf-8",
        logger: Optional[logging.Logger] = None,
        lazy_load: bool = True,
    ) -> None:
        if not properties_file_names:
            raise ValueError(self.ERROR_MSG_PROPERTIES_FILE_NAMES_IS_NULL_OR_EMPTY)
        if any(not fn or str(fn).strip() == "" for fn in properties_file_names):
            raise ValueError(self.ERROR_MSG_PROPERTIES_FILE_NAME_IS_BLANK)

        self._properties_file_names: list[str] = list(properties_file_names)
        self._base_directory: Optional[Path] = base_directory
        self._regex_pattern: Pattern[str] = re.compile(config_map_name_regex)
        self._encoding: str = encoding
        self._logger: logging.Logger = logger or logging.getLogger(self.__class__.__name__)
        self._lazy_load: bool = lazy_load
        self._properties_cache: Optional[Dict[str, str]] = None
        self._load_lock: asyncio.Lock = asyncio.Lock()

    async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
        self._logger.debug(self.LOG_MSG_ATTEMPTING_RETRIEVAL, configuration_item_name)
        self._validate_name(configuration_item_name)
        await self._ensure_loaded()
        assert self._properties_cache is not None  # for type checkers
        raw_value: str = self._properties_cache.get(configuration_item_name, "")
        self._inspect_name_and_value(configuration_item_name, raw_value)

        if raw_value.strip() == "":
            csv: str = ",".join(self._properties_file_names)
            self._logger.debug(
                self.LOG_MSG_CONFIG_MAP_NOT_FOUND_IN_PROPERTY_FILES,
                csv,
                configuration_item_name,
            )
            self._logger.info(self.LOG_MSG_CONFIG_MAP_VALUE_EMPTY, configuration_item_name)
            return None

        return ConfigMapDto(name=configuration_item_name, value=raw_value)

    async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
        dto: ConfigMapDto = await self.retrieve_config_map(configuration_item_name)
        if dto is None:
            raise ValueError(self.ERROR_MSG_MISSING_CONFIG_MAP % configuration_item_name)
        return dto.value

    async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
        dto: ConfigMapDto = await self.retrieve_config_map(configuration_item_name)
        return None if dto is None else dto.value

    def _validate_name(self, configuration_item_name: str) -> None:
        if not self._regex_pattern.match(configuration_item_name):
            raise ValueError(
                self.ERROR_MSG_CONFIG_MAP_NAME_REGEX_VALIDATION_FAILED
                % (configuration_item_name, self._regex_pattern.pattern)
            )

    async def _ensure_loaded(self) -> None:
        if self._lazy_load and self._properties_cache is not None:
            return
        async with self._load_lock:
            if self._properties_cache is not None and self._lazy_load:
                return
            try:
                merged: Dict[str, str] = {}
                for file_name in self._properties_file_names:
                    path: Path = self._resolve_path(file_name)
                    file_props: Dict[str, str] = await asyncio.to_thread(self._parse_properties_file, path)
                    merged.update(file_props)
                self._properties_cache = merged
            except Exception as ex:
                ex_exception: Exception = ex
                self._logger.error(self.ERROR_MSG_RETRIEVE_CONFIG_MAP_FAILURE, ex_exception)
                raise

    def _resolve_path(self, file_name: str) -> Path:
        p: Path = Path(file_name)
        if not p.is_absolute() and self._base_directory:
            p = self._base_directory / p
        if not p.exists():
            raise FileNotFoundError(f'config file "{p}" not found')
        return p

    def _parse_properties_file(self, file_path: Path) -> Dict[str, str]:
        props: Dict[str, str] = {}
        with file_path.open("r", encoding=self._encoding) as f:
            for line in f:
                line_stripped: str = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    continue
                if "=" not in line_stripped:
                    continue
                key: str
                value: str
                key, value = line_stripped.split("=", 1)
                props[key.strip()] = value.strip()
        return props

    def _inspect_name_and_value(self, name: str, value: str) -> None:
        # Placeholder for parity with Java's ConfigMapKeyValueInspector.checkForNameAndValueAreSame
        # (assuming it warns if identical)
        if value and value == name:
            self._logger.debug('ConfigMap name equals its value (name="%s")', name)
            error_msg: str = f'ConfigMap name equals its value (name="{name}")'
            raise ValueError(error_msg)
