import os
from dataclasses import dataclass

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever

@dataclass(frozen=True)
class RemoteEmbeddingModelConfig:
    AZURE_OPENAI_EMBEDDINGS_ENDPOINT: str
    AZURE_OPENAI_EMBEDDINGS_API_KEY: str
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: str
    AZURE_OPENAI_EMBEDDING_MODEL_NAME: str

    @staticmethod
    async def all_items_exist() -> bool:
        """ return true if all items that make up the EmbeddingModelConfig exist in the environment, otherwise false """
        return "AZURE_OPENAI_EMBEDDINGS_ENDPOINT" in os.environ and "AZURE_OPENAI_EMBEDDINGS_API_KEY" in os.environ and "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME" in os.environ and "AZURE_OPENAI_EMBEDDING_MODEL_NAME" in os.environ

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "RemoteEmbeddingModelConfig":
        return RemoteEmbeddingModelConfig(
            AZURE_OPENAI_EMBEDDINGS_ENDPOINT=await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_OPENAI_EMBEDDINGS_ENDPOINT"),
            AZURE_OPENAI_EMBEDDINGS_API_KEY=await secrets_retriever.retrieve_mandatory_secret_value("AZURE_OPENAI_EMBEDDINGS_API_KEY"),
            AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
            AZURE_OPENAI_EMBEDDING_MODEL_NAME=await config_map_retriever.retrieve_mandatory_config_map_value("AZURE_OPENAI_EMBEDDING_MODEL_NAME"),
        )
