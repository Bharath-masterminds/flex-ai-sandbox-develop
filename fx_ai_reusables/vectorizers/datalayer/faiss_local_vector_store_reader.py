from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from fx_ai_reusables.llm.creators.interfaces.llm_embedding_creator_interface import ILlmEmbeddingCreator
from fx_ai_reusables.vectorizers.datalayer.interfaces.vector_store_reader_interface import IVectorStoreReader

class FaissLocalVectorStoreStoreReader(IVectorStoreReader):

    def __init__(self, llm_embedding_create: ILlmEmbeddingCreator, source_files_folder: str,
                 allow_dangerous_deserialization: bool):
        self.llm_embedding_create: ILlmEmbeddingCreator = llm_embedding_create
        self.source_files_folder: str = source_files_folder
        self.allow_dangerous_deserialization: bool = allow_dangerous_deserialization

    async def read_vector_store(self, unique_identifier: str) -> VectorStore:

        embedding_result: Embeddings = await self.llm_embedding_create.create_llm_embeddings()

        vectorstore: FAISS = FAISS.load_local(self.source_files_folder, embedding_result, index_name=unique_identifier,
                                              allow_dangerous_deserialization=self.allow_dangerous_deserialization)

        return vectorstore
