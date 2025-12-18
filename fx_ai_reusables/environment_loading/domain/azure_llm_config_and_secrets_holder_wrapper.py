from dataclasses import dataclass
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.environment_loading.domain.azure_doc_intelligence_config import AzureDocIntelligenceConfig
from fx_ai_reusables.environment_loading.domain.azure_openai_config import AzureOpenAIConfig
from fx_ai_reusables.environment_loading.domain.hcp_config import HcpConfig
from fx_ai_reusables.environment_loading.domain.local_embedding_model_config import LocalEmbeddingModelConfig
from fx_ai_reusables.environment_loading.domain.piece_meal_vector_store_writer_decorator_settings import PieceMealVectorStoreWriterDecoratorSettings
from fx_ai_reusables.environment_loading.domain.remote_embedding_model_config import RemoteEmbeddingModelConfig
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


@dataclass(frozen=True)
class AzureLlmConfigAndSecretsHolderWrapper:
    """ A wrapper for environment configuration that holds instances of various (inner) configuration classes."""

    azure_openai: AzureOpenAIConfig
    hcp: HcpConfig
    doc_intelligence: Optional[AzureDocIntelligenceConfig]

    #note, the below is optional
    remote_embedding_model: Optional[RemoteEmbeddingModelConfig]
    local_embedding_model: Optional[LocalEmbeddingModelConfig]

    piece_meal_vector_store_writer_dec_settings: PieceMealVectorStoreWriterDecoratorSettings

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "AzureLlmConfigAndSecretsHolderWrapper":
        return AzureLlmConfigAndSecretsHolderWrapper(
            azure_openai=await AzureOpenAIConfig.hydrate(config_map_retriever, secrets_retriever),
            hcp=await HcpConfig.hydrate(config_map_retriever, secrets_retriever),
            doc_intelligence=await AzureDocIntelligenceConfig.hydrate(config_map_retriever, secrets_retriever) if await AzureDocIntelligenceConfig.all_items_exist() else None,
            remote_embedding_model=await  RemoteEmbeddingModelConfig.hydrate(config_map_retriever, secrets_retriever) if await RemoteEmbeddingModelConfig.all_items_exist() else None,
            local_embedding_model=await  LocalEmbeddingModelConfig.hydrate(config_map_retriever, secrets_retriever) if await LocalEmbeddingModelConfig.all_items_exist() else None,
            piece_meal_vector_store_writer_dec_settings=await PieceMealVectorStoreWriterDecoratorSettings.hydrate(config_map_retriever, secrets_retriever)

        )
