from dataclasses import dataclass
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


# Default timeout value for Datadog API requests (in seconds)
OPINIONATED_DEFAULT_DATADOG_TIMEOUT = 30


@dataclass(frozen=True)
class DatadogConfig:
    """Configuration settings for Datadog API access.
    
    Groups together all Datadog-related configuration including API credentials,
    endpoint URLs, and connection settings.
    
    Attributes:
        DATADOG_API_KEY: API key for authenticating with Datadog (secret)
        DATADOG_APP_KEY: Application key for Datadog API access (secret)
        DATADOG_API_URL: Base URL for Datadog API endpoints (config)
        DATADOG_TIMEOUT: Optional timeout in seconds for API requests (config)
    """
    DATADOG_API_KEY: str
    DATADOG_APP_KEY: str
    DATADOG_API_URL: str
    DATADOG_TIMEOUT: int

    @staticmethod
    async def hydrate(
        config_map_retriever: IConfigMapRetriever, 
        secrets_retriever: ISecretRetriever
    ) -> "DatadogConfig":
        """Hydrate DatadogConfig from config map and secrets retrievers.
        
        Retrieves all Datadog settings from their respective sources:
        - Secrets: API_KEY, APP_KEY (sensitive credentials)
        - Config: API_URL, TIMEOUT (non-sensitive configuration)
        
        Args:
            config_map_retriever: Interface for retrieving configuration values
            secrets_retriever: Interface for retrieving secret values
            
        Returns:
            DatadogConfig: Fully hydrated configuration object with all Datadog settings
        """
        # Retrieve timeout with default fallback
        timeout_str = await config_map_retriever.retrieve_optional_config_map_value("DATADOG_TIMEOUT")
        timeout = int(timeout_str) if timeout_str else OPINIONATED_DEFAULT_DATADOG_TIMEOUT
        
        return DatadogConfig(
            DATADOG_API_KEY=await secrets_retriever.retrieve_mandatory_secret_value("DATADOG_API_KEY"),
            DATADOG_APP_KEY=await secrets_retriever.retrieve_mandatory_secret_value("DATADOG_APP_KEY"),
            DATADOG_API_URL=await config_map_retriever.retrieve_mandatory_config_map_value("DATADOG_API_URL"),
            DATADOG_TIMEOUT=timeout,
        )
