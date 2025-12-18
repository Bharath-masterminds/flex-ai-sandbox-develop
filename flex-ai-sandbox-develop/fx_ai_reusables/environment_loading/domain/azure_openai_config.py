from dataclasses import dataclass
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


@dataclass(frozen=True)
class AzureOpenAIConfig:
    AZURE_OPENAI_API_VERSION: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str
    AZURE_OPENAI_MODEL: Optional[str]
    AZURE_OPENAI_ENDPOINT: str
    UAIS_PROJECT_ID: str

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "AzureOpenAIConfig":
        from fx_ai_reusables.environment_loading.helpers.environment_variable_reader_helper import EnvironmentVariableReaderHelper
        return AzureOpenAIConfig(
            AZURE_OPENAI_API_VERSION=await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_OPENAI_API_VERSION"),
            AZURE_OPENAI_DEPLOYMENT_NAME=await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_OPENAI_DEPLOYMENT_NAME"),
            # AZURE_OPENAI_MODEL is optional, sometimes (only) the deployment name is used, sometimes the model name is also needed.
            AZURE_OPENAI_MODEL=await config_map_retriever.retrieve_optional_config_map_value("AZURE_OPENAI_MODEL"),
            AZURE_OPENAI_ENDPOINT=await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_OPENAI_ENDPOINT"),
            UAIS_PROJECT_ID=await secrets_retriever.retrieve_mandatory_secret_value("UAIS_PROJECT_ID"),
        )