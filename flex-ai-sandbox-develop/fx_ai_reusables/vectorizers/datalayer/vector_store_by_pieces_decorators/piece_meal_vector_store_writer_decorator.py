import json
import logging
from typing import List, cast

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from tenacity import AsyncRetrying, wait_random_exponential, stop_after_attempt

from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import AzureLlmConfigAndSecretsHolderWrapper
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.vectorizers.constants import DEFAULT_INTERMEDIATE_PERSIST_LENGTH
from fx_ai_reusables.vectorizers.datalayer.interfaces.vector_store_writer_interface import IVectorStoreWriter
from fx_ai_reusables.vectorizers.helpers.local_only_vector_store_merger import LocalOnlyVectorStoreMerger


class PieceMealVectorStoreWriterDecorator(IVectorStoreWriter):
    """Decorator for IVectorStoreWriter.
        When there are "too many" chunks, this will take a piece-them-up, create a smaller vector-store(s), then rejoin all the intermediate vector-stores.
    """

    def __init__(self, inner_item_to_decorate: IVectorStoreWriter,
                 azure_llm_configmap_and_secrets_holder_wrapper_retriever: IAzureLlmConfigAndSecretsHolderWrapperReader,
                 destination_folder: str,
                 intermediate_persist_length: int = DEFAULT_INTERMEDIATE_PERSIST_LENGTH):
        self._inner_item_to_decorate: IVectorStoreWriter = inner_item_to_decorate
        self.azure_llm_configmap_and_secrets_holder_wrapper_retriever = azure_llm_configmap_and_secrets_holder_wrapper_retriever
        self.destination_folder = destination_folder
        self.chunk_intermediate_persist_length = intermediate_persist_length

    async def write_vector_store(self, unique_identifier: str, chunks: List[Document],
                                 piece_meal_start_index: int) -> VectorStore:


        env_config_holder: AzureLlmConfigAndSecretsHolderWrapper = await self.azure_llm_configmap_and_secrets_holder_wrapper_retriever.read_azure_llm_config_and_secrets_holder_wrapper()
        wait_random_exponential_min: int = env_config_holder.piece_meal_vector_store_writer_dec_settings.wait_random_exponential_min
        wait_random_exponential_max: int = env_config_holder.piece_meal_vector_store_writer_dec_settings.wait_random_exponential_max
        stop_after_attempt_count: int = env_config_holder.piece_meal_vector_store_writer_dec_settings.stop_after_attempt_count

        async for attempt in AsyncRetrying(
                wait=wait_random_exponential(min=wait_random_exponential_min, max=wait_random_exponential_max),
                stop=stop_after_attempt(stop_after_attempt_count),
                reraise=True
        ):
            try:
                with attempt:
                    logging.info(f"Attempt {attempt.retry_state.attempt_number} to write vector store for {unique_identifier}")
                    # Inside the async for attempt loop, before calling __internal_write_vector_store:
                    logging.info(
                        f"Retry attempt: {attempt.retry_state.attempt_number}, details: {json.dumps(attempt.retry_state.__dict__, default=str)}")
                    result = await self.__internal_write_vector_store(unique_identifier, chunks, piece_meal_start_index)
                    return result
            except Exception as e:
                logging.error(f"Attempt {attempt.retry_state.attempt_number} failed with error: {e}")

        raise Exception("Failed to write vector store after retries")

    async def __internal_write_vector_store(self, unique_identifier: str, chunks: List[Document], piece_meal_start_index: int) -> VectorStore:

        logging.info(f"starting PieceMealVectorStoreWriterDecorator.write_vector_store, chunks size: {chunks.__sizeof__()}")

        if len(chunks) <= self.chunk_intermediate_persist_length:
            # If we have fewer chunks than the chunk size, just delegate to inner writer
            return await self._inner_item_to_decorate.write_vector_store(unique_identifier, chunks, piece_meal_start_index)


        # use math-min in case the len-of-chunks is smaller than the chunk_intermediate_persist_length
        computed_chunk_length: int = min(len(chunks), self.chunk_intermediate_persist_length)
        # Create multiple vector stores with chunks of size computed_chunk_length
        vector_stores: List[VectorStore] = []
        for i in range(0, len(chunks), computed_chunk_length):

            current_batch: List[Document] = chunks[i:i + computed_chunk_length]

            logging.info(
                f"PieceMealVectorStoreWriterDecorator:Processing items {i} to {i + len(current_batch) - 1} out of {len(chunks)}")

            # Create a unique identifier for each batch
            batch_id:str = f"intermediate_file_{unique_identifier}_batch_{i // computed_chunk_length}"

            logging.info(f"Writing {len(current_batch)} chunks to {batch_id}")

            # piece_meal_start_index won't be used for "raw", but pass it along for consistency
            current_vector_store: VectorStore = await self._inner_item_to_decorate.write_vector_store(batch_id, current_batch, piece_meal_start_index)
            vector_stores.append(current_vector_store)

            #logging.info(f"PieceMealVectorStoreWriterDecorator: About to sleep for {artificialDelayMs} ms")
            # Artificial delay to avoid overwhelming the system
            #await asyncio.sleep(artificialDelayMs / 1000)


        logging.info(f"Combining multiple vector-stores into one. {len(vector_stores)}")
        # Combine all vector stores using merge_from
        recombined_return_item = await LocalOnlyVectorStoreMerger.merge(vector_stores)

        logging.info(f"Casting recombined_return_item to FAISS")
        # Cast the VectorStore to FAISS
        faiss_vector_store = cast(FAISS, recombined_return_item)

        logging.info(f"Saving single-merged-vector-store to single file. {self.destination_folder}, {unique_identifier}")
        faiss_vector_store.save_local(self.destination_folder, unique_identifier)

        return recombined_return_item


