from dataclasses import dataclass

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.environment_loading.helpers.environment_variable_reader_helper import EnvironmentVariableReaderHelper
import os

@dataclass(frozen=True)
class AzureDocIntelligenceConfig:
    AZURE_APP_CLIENT_ID: str
    AZURE_APP_CLIENT_SECRET: str
    AZURE_APP_TENANT_ID: str
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str

    @staticmethod
    async def all_items_exist() -> bool:
        """ return true if all items that make up the EmbeddingModelConfig exist in the environment, otherwise false """
        return "AZURE_APP_CLIENT_ID" in os.environ and "AZURE_APP_CLIENT_SECRET" in os.environ and "AZURE_APP_TENANT_ID" in os.environ and "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" in os.environ

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "AzureDocIntelligenceConfig":
        return AzureDocIntelligenceConfig(
            AZURE_APP_CLIENT_ID = await secrets_retriever.retrieve_mandatory_secret_value("AZURE_APP_CLIENT_ID"),
            AZURE_APP_CLIENT_SECRET = await secrets_retriever.retrieve_mandatory_secret_value("AZURE_APP_CLIENT_SECRET"),
            AZURE_APP_TENANT_ID = await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_APP_TENANT_ID"),
            AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
        )


