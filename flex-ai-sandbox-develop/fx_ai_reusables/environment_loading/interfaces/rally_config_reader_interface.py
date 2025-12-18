from abc import ABC, abstractmethod

from fx_ai_reusables.environment_loading.domain.rally_config import RallyConfig


class IRallyConfigReader(ABC):
    """Interface for Rally configuration retrieval.

    Provides abstraction for reading Rally settings, allowing for different
    implementations (e.g., environment variables, file-based, K8s secrets).
    """

    @abstractmethod
    async def read_rally_config(self) -> RallyConfig:
        """Read and return Rally configuration.

        Returns:
            RallyConfig: Complete Rally configuration with all settings
        """
        pass
