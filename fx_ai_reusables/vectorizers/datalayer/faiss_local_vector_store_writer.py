import logging
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from fx_ai_reusables.llm.creators.interfaces.llm_embedding_creator_interface import ILlmEmbeddingCreator
from fx_ai_reusables.vectorizers.datalayer.interfaces.vector_store_writer_interface import IVectorStoreWriter


class FaissLocalVectorStoreStoreWriter(IVectorStoreWriter):

    def __init__(self, llm_embedding_create: ILlmEmbeddingCreator, source_files_folder: str):
        self.llm_embedding_create: ILlmEmbeddingCreator = llm_embedding_create
        self.source_files_folder: str = source_files_folder

    async def write_vector_store(self, unique_identifier: str, chunks: List[Document], piece_meal_start_index: int) -> VectorStore:

        if chunks is None or len(chunks) == 0:
            raise ValueError("`chunks` must not be None and must contain at least one Document.")

        embedding_result: Embeddings = await self.llm_embedding_create.create_llm_embeddings()

        # Step 3: Create the FAISS vector store from the document chunks
        logging.info("Creating FAISS vector store from document chunks...chunks-size=%s", chunks.__sizeof__())
        vectorstore: FAISS = FAISS.from_documents(chunks, embedding_result)

        logging.info("💾 Saving FAISS index...self.source_files_folder=%s, unique_identifier=%s", self.source_files_folder, unique_identifier)
        vectorstore.save_local(self.source_files_folder, unique_identifier)

        return vectorstore
