import os
from typing import Optional

from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.secrets.interfaces.dtos.secret_dto import SecretDto

class EnvironmentVariableSecretRetriever(ISecretRetriever):
    async def retrieve_secret(self, name_of: str) -> Optional[SecretDto]:
        value = os.environ.get(name_of)
        if value is not None:
            return SecretDto(secret_name=name_of, _secret_value=value)
        return None

    async def retrieve_mandatory_secret_value(self, name_of: str) -> str:
        value = os.environ.get(name_of)
        if value is None:
            raise KeyError(f"Mandatory secret '{name_of}' not found in environment variables.")
        return value

    async def retrieve_optional_secret_value(self, name_of: str) -> Optional[str]:
        return os.environ.get(name_of)