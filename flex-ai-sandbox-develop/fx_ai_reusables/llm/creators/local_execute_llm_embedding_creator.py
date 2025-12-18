import logging

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.embeddings import Embeddings

from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import (
    AzureLlmConfigAndSecretsHolderWrapper,
)
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.llm.creators.interfaces.llm_embedding_creator_interface import ILlmEmbeddingCreator

class LocalExecuteLlmEmbeddingCreator(ILlmEmbeddingCreator):
    """Implementation of LLM creation service for local execute."""

    def __init__(self, environment_values_rdr: IAzureLlmConfigAndSecretsHolderWrapperReader):
        self.environment_values_rdr: IAzureLlmConfigAndSecretsHolderWrapperReader = environment_values_rdr

    async def create_llm_embeddings(
            self
    ) -> Embeddings:

        config_holder: AzureLlmConfigAndSecretsHolderWrapper = (
            await self.environment_values_rdr.read_azure_llm_config_and_secrets_holder_wrapper()
        )

        if config_holder.local_embedding_model is None:
            raise ValueError("local_embedding_model is null")

        local_embedding_model_name: str = config_holder.local_embedding_model.HUGGING_FACE_EMBEDDING_MODEL_NAME

        # from langchain_huggingface import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(model_name=local_embedding_model_name)

        # go off VPN for the one time download no zee-scal3r

        logging.info("Exiting LocalExecuteLlmCreator.create_llm_embeddings()")

        return embeddings

