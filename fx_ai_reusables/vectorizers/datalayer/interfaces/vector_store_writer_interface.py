from abc import ABC, abstractmethod
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


class IVectorStoreWriter(ABC):
    """Interface for FAISS Retrieval.
    class FAISS (implements) (VectorStore):
    """

    @abstractmethod
    async def write_vector_store(self, unique_identifier: str, chunks: List[Document], piece_meal_start_index: int) -> FAISS:
        """piece_meal_start_index does not really belong on the interface.
        but practically, it is hard to write a large vector store without it."""
        pass
