from abc import ABC, abstractmethod

from langchain_core.vectorstores import VectorStore


class IVectorStoreReader(ABC):
    """Interface for FAISS Retrieval.
     class FAISS (implements) (VectorStore):
     """

    @abstractmethod
    async def read_vector_store(self, unique_identifier: str) -> VectorStore:
        pass
