from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

from fx_ai_reusables.secrets.interfaces.dtos.secret_dto import SecretDto


class ISecretRetriever(ABC):
    @abstractmethod
    async def retrieve_secret(self, name_of: str) -> Optional[SecretDto]:
        """
        Retrieve a secret by name.

        Args:
            name_of: The name of the secret to retrieve

        Returns:
            Optional SecretDto object
        """
        pass

    @abstractmethod
    async def retrieve_mandatory_secret_value(self, name_of: str) -> str:
        """
        Retrieve a mandatory secret value by name.

        Args:
            name_of: The name of the secret to retrieve

        Returns:
            The secret value as a string
        """
        pass

    @abstractmethod
    async def retrieve_optional_secret_value(self, name_of: str) -> Optional[str]:
        """
        Retrieve an optional secret value by name.

        Args:
            name_of: The name of the secret to retrieve

        Returns:
            Optional string value of the secret
        """
        pass