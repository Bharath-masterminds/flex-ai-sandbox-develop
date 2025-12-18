import logging
from typing import List, cast

from langchain_community.vectorstores import FAISS
from langchain_core.vectorstores import VectorStore

class LocalOnlyVectorStoreMerger:
    """
    A class to merge multiple vector stores into a single vector store.
    This will cast the VectorStore to a FAISS type, so it is only suitable for FAISS vector stores.
    The "Local" is that the cast prevents a remote-call to the AI mothership.
    """

    @staticmethod
    async def merge(many_vector_stores: List[VectorStore]) -> VectorStore:
        """
        Merges the vector stores into a single vector store.

        :return: A new vector store containing all vectors from the input stores.
        """
        logging.info(f"VectorStoreMerger: Starting Merge. many_vector_stores.count={len(many_vector_stores)}")

        # no "new", so use item-0 as the starter
        target_vectorstore_zero: VectorStore = many_vector_stores[0]

        cast_target_vectorstore: FAISS = cast(FAISS, target_vectorstore_zero)

        if len(many_vector_stores) == 1:
            # If there's only one vector store, return it directly
            logging.info(f"VectorStoreMerger: Only One. Just return it. many_vector_stores-count={len(many_vector_stores)}")
            return cast_target_vectorstore

        counter:int = 0

        # Skip the first vector store (which is already our target)
        for current_vs in many_vector_stores[1:]:
            counter += 1
            logging.info(f"VectorStoreMerger: Looping. counter={counter}. many_vector_stores.count{len(many_vector_stores)}")

            cast_current_vs: FAISS = cast(FAISS, current_vs)

            # the below is important and a FAISS-specific method.  It does not seem to make a remote call.
            cast_target_vectorstore.merge_from(cast_current_vs)


        logging.info(f"VectorStoreMerger: about to return (single) cast_target_vectorstore.")
        return cast_target_vectorstore
