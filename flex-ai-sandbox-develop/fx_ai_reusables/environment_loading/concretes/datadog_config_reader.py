from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.environment_loading.interfaces.datadog_config_reader_interface import IDatadogConfigReader
from fx_ai_reusables.environment_loading.domain.datadog_config import DatadogConfig


class DatadogConfigReader(IDatadogConfigReader):
    """Concrete implementation of Datadog configuration reader.
    
    Reads Datadog configuration using injected config map and secrets retrievers,
    consolidating all Datadog settings access through a single interface.
    """

    def __init__(
        self, 
        config_map_retriever: IConfigMapRetriever, 
        secrets_retriever: ISecretRetriever
    ):
        """Initialize the Datadog config reader with retrievers.
        
        Args:
            config_map_retriever: Interface for retrieving configuration values
            secrets_retriever: Interface for retrieving secret values
        """
        self.config_map_retriever = config_map_retriever
        self.secrets_retriever = secrets_retriever

    async def read_datadog_config(self) -> DatadogConfig:
        """Read and return Datadog configuration.
        
        Uses the hydrate method of DatadogConfig to consolidate all setting
        retrieval in one place.
        
        Returns:
            DatadogConfig: Complete Datadog configuration with all settings
        """
        return await DatadogConfig.hydrate(
            self.config_map_retriever,
            self.secrets_retriever
        )
