import asyncio
import logging
import os
import uuid
from typing import List, cast
from uuid import UUID

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import Language

from fx_ai_reusables.authenticators.hcp.cache_aside_decorators.hcp_authenticator_cache_aside_decorator import (
    HcpAuthenticatorCacheAsideDecorator
)
from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.chunkers.concretes.source_code_by_folder_chunker import SourceCodeBySourceFolderChunker
from fx_ai_reusables.chunkers.interfaces.chunker_interface import IChunker
from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.environment_fetcher import StaticEnvironmentFetcher
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import (
    AzureLlmConfigAndSecretsHolderWrapperReader
)
from fx_ai_reusables.llm.creators.azure_openai_embeddings_creator import AzureOpenAIEmbeddingsCreator
from fx_ai_reusables.llm.creators.interfaces.llm_embedding_creator_interface import ILlmEmbeddingCreator
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.vectorizers.constants import PIECE_MEAL_INTERMEDIATE_CHUNK_LENGTH
from fx_ai_reusables.vectorizers.datalayer.faiss_local_vector_store_reader import FaissLocalVectorStoreStoreReader
from fx_ai_reusables.vectorizers.datalayer.faiss_local_vector_store_writer import FaissLocalVectorStoreStoreWriter
from fx_ai_reusables.vectorizers.datalayer.cache_aside_decorators.memory_vector_reader_cache_aside_decorator import (
    MemoryVectorStoreReaderCacheAsideDecorator
)
from fx_ai_reusables.vectorizers.datalayer.interfaces.vector_store_reader_interface import IVectorStoreReader
from fx_ai_reusables.vectorizers.datalayer.interfaces.vector_store_writer_interface import IVectorStoreWriter
from fx_ai_reusables.vectorizers.datalayer.vector_store_by_pieces_decorators.piece_meal_vector_store_writer_decorator import (
    PieceMealVectorStoreWriterDecorator
)
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader


# sample usage
async def main():
    logging.basicConfig(
        level=logging.INFO,  # or DEBUG
        format='%(asctime)s %(levelname)s %(message)s'
    )

    StaticEnvironmentFetcher.load_environment()

    home_path_root: str = os.path.expanduser("~")

    # Prerequisites.  Create "chunks".

    chunker_instance: IChunker = SourceCodeBySourceFolderChunker(Language.CSHARP)

    source_code_relative_directory: str = "my/src/code/directory"  # Replace with your source code directory
    source_code_full_directory: str = os.path.join(home_path_root, source_code_relative_directory)
    glob_filter = "**/*.cs"

    chunks: List[Document] = await chunker_instance.chunk_it(source_code_full_directory, glob_filter)
    print("List[Document].SIZE:", chunks.__sizeof__())

    # End Prerequisites.  Create "chunks".

    # Prerequisites.  Create "vector store writer" and "vector store reader".
    # Set up configuration and secret retrievers
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()
    
    # Create environment reader with proper dependencies
    environment_reader_instance: IAzureLlmConfigAndSecretsHolderWrapperReader = AzureLlmConfigAndSecretsHolderWrapperReader(
        config_map_retriever, secrets_retriever
    )
    
    # Create authenticator with proper dependencies
    undecorated_raw_hcp_authentication: IHcpAuthenticator = HcpAuthenticator(environment_reader_instance)
    cache_aside_hcp_authentication: IHcpAuthenticator = HcpAuthenticatorCacheAsideDecorator(undecorated_raw_hcp_authentication)

    # Create embedding creator with proper dependencies
    llm_embedding_creator: ILlmEmbeddingCreator = AzureOpenAIEmbeddingsCreator(
        cache_aside_hcp_authentication, environment_reader_instance
    )

    # unique-identifier - fix UUID type annotation
    new_guid: UUID = uuid.uuid4()  # Create a new GUID
    guid_str: str = "SampleOneVectorStoreName-" + str(new_guid)  # Convert GUID to string

    # below folder needs to pre-exist
    vector_store_relative_path = "vector-store-playground"
    vector_store_full_path: str = os.path.join(home_path_root, vector_store_relative_path)

    # write the vector store
    vector_store_write_instance_undecorated: IVectorStoreWriter = FaissLocalVectorStoreStoreWriter(llm_embedding_creator,
                                                                                       vector_store_full_path)

    #this is the "how many at a time" .. when you have a large collection-size of chunks.  especially important for "remote-azure" calls to avoid "timeout/too-much-payload" issues
    piece_meal_intermediate_chunk_length: int = PIECE_MEAL_INTERMEDIATE_CHUNK_LENGTH
    vector_store_write_instance: IVectorStoreWriter = PieceMealVectorStoreWriterDecorator(vector_store_write_instance_undecorated,
                                                                                          environment_reader_instance,
                                                                                          vector_store_full_path,
                                                                                          piece_meal_intermediate_chunk_length)

    write_result: VectorStore = await vector_store_write_instance.write_vector_store(guid_str, chunks, 0)
    logging.info("VectorStore-write-result: %s", write_result.__dict__)

    # force flush of token at this point.  since we are changing from write-to-read and ensure a better EXPIRES_ON value
    # Cast and call flush
    await cast(HcpAuthenticatorCacheAsideDecorator, cache_aside_hcp_authentication).flush_cache_aside()

    # read the vector store
    vector_store_reader_instance_undecorated: IVectorStoreReader = FaissLocalVectorStoreStoreReader(
        llm_embedding_creator, vector_store_full_path, True)

    # add cache-aside decorator for reader
    vector_store_reader_instance_final_decorated: IVectorStoreReader = MemoryVectorStoreReaderCacheAsideDecorator(
        vector_store_reader_instance_undecorated)

    #loop to show cache-aside decorator functionality
    for i in range(0, 5):
        i: int  # type hint for clarity
        read_result: VectorStore = await vector_store_reader_instance_final_decorated.read_vector_store(guid_str)
        logging.info("VectorStore-read-result:(Counter=%s): __dict__ = %s", i, read_result.__dict__)

    logging.info("VectorStoreWriteReadSample.py has completed.")

# Run the main function
asyncio.run(main())
