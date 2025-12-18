import logging
import os
import re
from pathlib import Path
from typing import Optional

from fx_ai_reusables.secrets.base.secret_validator import SecretValidator
from fx_ai_reusables.secrets.concretes.file_mount.domain.secret_definition import SecretDefinition
from fx_ai_reusables.secrets.interfaces.dtos.secret_dto import SecretDto
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


def get_property(key: str) -> Optional[str]:
    return os.environ.get(key)


class VolumeMountSecretRetriever(ISecretRetriever):
    ENVIRONMENT_OR_SYSTEM_PROPERTY_NAME_PREFIX: str = "secrets."
    DEFAULT_FILE_NAME_PREFIX: str = "/etc/secrets/"
    SECRET_NAME_REGEX: re.RegexFlag = re.compile(r"^[A-Za-z0-9._-]+$")

    def __init__(self, logger: Optional[logging.Logger] = None):
        if logger is None:
            logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self._logger = logger

    async def retrieve_mandatory_secret_value(self, name_of: str) -> str:
        dto = await self.retrieve_secret(name_of)
        if dto is None:
            raise ValueError(f"Missing secret: {name_of}")
        return dto.secret_value

    async def retrieve_optional_secret_value(self, name_of: str) -> Optional[str]:
        dto: Optional[SecretDto] = await self.retrieve_secret(name_of)
        return dto.secret_value if dto else None

    async def retrieve_secret(self, name_of: str) -> Optional[SecretDto]:
        self._logger.debug("Attempting secret retrieval.")
        if not self.SECRET_NAME_REGEX.fullmatch(name_of):
            raise ValueError(f"Secret name regex mismatch: {name_of}")

        env_prop_prefix:str = self.get_environment_or_system_property_name_prefix()
        env_key:str = f"{env_prop_prefix}{name_of}"
        self._logger.debug("Computed env key: %s", env_key)

        default_file_prefix:str = self.get_default_file_name_prefix()
        default_file_name:str  = f"{default_file_prefix}{name_of.replace('.', '/')}"
        self._logger.debug("Computed default file path: %s", default_file_name)

        definition: SecretDefinition = SecretDefinition(name_of, env_key, default_file_name)
        self._logger.debug("SecretDefinition: %s", definition)

        file_path: str = get_property(definition.get_environment_or_system_property_name())
        if not file_path:
            self._logger.debug("No override path; using default: %s", definition.get_default_full_file_name())
            file_path: str = definition.get_default_full_file_name()
            if not file_path:
                self._logger.debug("Blank file path; returning empty.")
                return None
            p: Path = Path(file_path)
            if not p.exists():
                self._logger.debug("File not found: %s", file_path)
                return None
        else:
            p: Path = Path(file_path)

        self._logger.debug("Reading secret file: %s", file_path)
        try:
            content: str = p.read_text(encoding="utf-8")
        except OSError as ex:
            raise OSError(str(ex)) from ex

        SecretValidator.check_for_name_and_value_are_same(name_of, content)

        if content.strip() == "":
            self._logger.debug("File content empty for secret: %s", name_of)
            return None

        dto: SecretDto = SecretDto(secret_name=name_of, _secret_value=content)
        return dto

    # Protected (overridable) methods
    def get_environment_or_system_property_name_prefix(self) -> str:
        return self.ENVIRONMENT_OR_SYSTEM_PROPERTY_NAME_PREFIX

    def get_default_file_name_prefix(self) -> str:
        return self.DEFAULT_FILE_NAME_PREFIX

    def get_secret_name_reg_ex(self) -> re.RegexFlag:
        return self.SECRET_NAME_REGEX
