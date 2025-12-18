from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.environment_loading.interfaces.rally_config_reader_interface import IRallyConfigReader
from fx_ai_reusables.environment_loading.domain.rally_config import RallyConfig


class RallyConfigReader(IRallyConfigReader):
    """Concrete implementation of Rally configuration reader.
    
    Reads Rally configuration using injected config map and secrets retrievers,
    consolidating all Rally settings access through a single interface.
    """

    def __init__(
        self, 
        config_map_retriever: IConfigMapRetriever, 
        secrets_retriever: ISecretRetriever
    ):
        """Initialize the Rally config reader with retrievers.
        
        Args:
            config_map_retriever: Interface for retrieving configuration values
            secrets_retriever: Interface for retrieving secret values
        """
        self.config_map_retriever = config_map_retriever
        self.secrets_retriever = secrets_retriever

    async def read_rally_config(self) -> RallyConfig:
        """Read and return Rally configuration.
        
        Uses the hydrate method of RallyConfig to consolidate all setting
        retrieval in one place.
        
        Returns:
            RallyConfig: Complete Rally configuration with all settings
        """
        return await RallyConfig.hydrate(
            self.config_map_retriever,
            self.secrets_retriever
        )
