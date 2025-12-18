from dataclasses import dataclass
import os

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever

@dataclass(frozen=True)
class LocalEmbeddingModelConfig:
    HUGGING_FACE_EMBEDDING_MODEL_NAME: str

    @staticmethod
    async def all_items_exist() -> bool:
        """ return true if all items that make up the EmbeddingModelConfig exist in the environment, otherwise false """
        return "HUGGING_FACE_EMBEDDING_MODEL_NAME" in os.environ

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "LocalEmbeddingModelConfig":
        return LocalEmbeddingModelConfig(
            HUGGING_FACE_EMBEDDING_MODEL_NAME=await config_map_retriever.retrieve_mandatory_config_map_value("HUGGING_FACE_EMBEDDING_MODEL_NAME")
        )
