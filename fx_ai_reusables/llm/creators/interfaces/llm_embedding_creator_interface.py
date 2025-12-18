from abc import ABC, abstractmethod

from langchain_core.embeddings import Embeddings

class ILlmEmbeddingCreator(ABC):

    @abstractmethod
    async def create_llm_embeddings(
            self
    ) -> Embeddings:
        pass
