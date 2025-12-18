from abc import ABC, abstractmethod

from langchain.chains.base import Chain
from langchain_core.vectorstores import VectorStore


class IQuestionAnswerChainMaker(ABC):
    """Interface for Chain creation.
     """

    @abstractmethod
    async def make_chain(self, vector_store: VectorStore, return_source_documents: bool) -> Chain:
        pass
