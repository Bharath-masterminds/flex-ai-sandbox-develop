from dataclasses import dataclass
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


# Opinionated default values for Rally retry configuration
OPINIONATED_DEFAULT_RALLY_RETRY_ATTEMPTS = 3       # Retry fetch up to 3 times
OPINIONATED_DEFAULT_RALLY_RETRY_DELAY = 1.0          # Wait 1 second between fetch retries
OPINIONATED_DEFAULT_RALLY_RETRY_BACKOFF = 2.0      # Exponential backoff factor for retries


@dataclass(frozen=True)
class RallyConfig:
    """Configuration settings for Rally API access.

    Groups together all Rally-related configuration including API credentials,
    endpoint URLs, and connection settings.
    
    Attributes:
        RALLY_API_KEY: API key for authenticating with Rally (secret)
        RALLY_SERVER: Rally API server URL (config)
        RALLY_WORKSPACE: Rally workspace name (config)
        RALLY_VERIFY_SSL: Whether to verify SSL certificates (default: True)
        RALLY_RETRY_ATTEMPTS: Max attempts for retries (default: 3)
        RALLY_RETRY_DELAY: Delay in seconds between retries (default: 2.0)
        RALLY_RETRY_BACKOFF: Exponential backoff factor for retries (default: 2.0)

    Note:
        - Connection retry: Handles transient network issues when connecting to Rally
        - Fetch retry: Handles transient failures during data retrieval (rally.get() calls)
        - SSL verification can be disabled for corporate proxies by setting RALLY_VERIFY_SSL=false
    """
    RALLY_API_KEY: str
    RALLY_SERVER: str
    RALLY_WORKSPACE: str
    RALLY_VERIFY_SSL: bool = True
    RALLY_RETRY_ATTEMPTS: int = OPINIONATED_DEFAULT_RALLY_RETRY_ATTEMPTS
    RALLY_RETRY_DELAY: float = OPINIONATED_DEFAULT_RALLY_RETRY_DELAY
    RALLY_RETRY_BACKOFF: float = OPINIONATED_DEFAULT_RALLY_RETRY_BACKOFF

    @staticmethod
    async def hydrate(
        config_map_retriever: IConfigMapRetriever, 
        secrets_retriever: ISecretRetriever
    ) -> "RallyConfig":
        """Hydrate RallyConfig from config map and secrets retrievers.

        Retrieves all Rally settings from their respective sources:
        - Secrets: API_KEY (sensitive credentials)
        - Config: SERVER, WORKSPACE, retry settings (non-sensitive configuration)

        Args:
            config_map_retriever: Interface for retrieving configuration values
            secrets_retriever: Interface for retrieving secret values
            
        Returns:
            RallyConfig: Fully hydrated configuration object with all Rally settings
        """
        # Retrieve retry details with default fallback
        retry_attempts_str = await config_map_retriever.retrieve_optional_config_map_value("RALLY_RETRY_ATTEMPTS")
        retry_attempts = int(retry_attempts_str) if retry_attempts_str else OPINIONATED_DEFAULT_RALLY_RETRY_ATTEMPTS

        retry_delay_str = await config_map_retriever.retrieve_optional_config_map_value("RALLY_RETRY_DELAY")
        retry_delay = float(retry_delay_str) if retry_delay_str else OPINIONATED_DEFAULT_RALLY_RETRY_DELAY

        retry_backoff_str = await config_map_retriever.retrieve_optional_config_map_value("RALLY_RETRY_BACKOFF")
        retry_backoff = float(retry_backoff_str) if retry_backoff_str else OPINIONATED_DEFAULT_RALLY_RETRY_BACKOFF

        # Retrieve SSL verification setting with default true
        verify_ssl_str = await config_map_retriever.retrieve_optional_config_map_value("RALLY_VERIFY_SSL")
        verify_ssl = verify_ssl_str.lower() not in ['false', '0', 'no'] if verify_ssl_str else True

        return RallyConfig(
            RALLY_API_KEY=await secrets_retriever.retrieve_mandatory_secret_value("RALLY_API_KEY"),
            RALLY_SERVER=await config_map_retriever.retrieve_mandatory_config_map_value("RALLY_SERVER"),
            RALLY_WORKSPACE=await config_map_retriever.retrieve_mandatory_config_map_value("RALLY_WORKSPACE"),
            RALLY_VERIFY_SSL=verify_ssl,
            RALLY_RETRY_ATTEMPTS=retry_attempts,
            RALLY_RETRY_DELAY=retry_delay,
            RALLY_RETRY_BACKOFF=retry_backoff,
        )
