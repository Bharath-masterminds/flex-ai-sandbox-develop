import logging
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_core.vectorstores import VectorStore

from fx_ai_reusables.vectorizers.datalayer.interfaces.vector_store_reader_interface import IVectorStoreReader


class MemoryVectorStoreReaderCacheAsideDecorator(IVectorStoreReader):
    """Cache Aside Decorator for IVectorReader.
        FAISS is stored as an in member member-variable.
    """

    def __init__(self, inner_item_to_decorate: IVectorStoreReader):
        self._inner_item_to_decorate: IVectorStoreReader = inner_item_to_decorate
        self.cached_object_holder: Optional[FAISS] = None

    async def read_vector_store(self, unique_identifier: str) -> VectorStore:

        if self.cached_object_holder is None:
            logging.info("cached_object_holder (FAISS) is NONE, reading the values from inner_item_to_decorate")
            self.cached_object_holder = await self._inner_item_to_decorate.read_vector_store(unique_identifier)
        else:
            logging.info("cached_object_holder (FAISS) is hydrated, using cache-aside version")

        if self.cached_object_holder is None:
            raise ValueError(
                "FAISS is None. This should not happen if the inner_item_to_decorate is implemented correctly.")

        return self.cached_object_holder
