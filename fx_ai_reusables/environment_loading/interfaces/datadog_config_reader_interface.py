from abc import ABC, abstractmethod

from fx_ai_reusables.environment_loading.domain.datadog_config import DatadogConfig


class IDatadogConfigReader(ABC):
    """Interface for Datadog configuration retrieval.
    
    Provides abstraction for reading Datadog settings, allowing for different
    implementations (e.g., environment variables, file-based, K8s secrets).
    """

    @abstractmethod
    async def read_datadog_config(self) -> DatadogConfig:
        """Read and return Datadog configuration.
        
        Returns:
            DatadogConfig: Complete Datadog configuration with all settings
        """
        pass
