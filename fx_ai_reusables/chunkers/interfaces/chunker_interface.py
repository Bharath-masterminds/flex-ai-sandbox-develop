from abc import ABC, abstractmethod

from typing import List

from langchain_core.documents import Document

class IChunker(ABC):
    """Interface for IChunker Retrieval. """

    @abstractmethod
    async def chunk_it(self, root_directory:str, glob_filter: str, chunk_size_value:int = 1000, chunk_overlap_value:int = 100) \
            -> List[Document]:
        pass

