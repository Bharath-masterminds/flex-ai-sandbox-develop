import logging
from typing import List

from langchain_core.vectorstores import VectorStore
from fx_ai_reusables.vectorizers.constants import DEFAULT_SIMILARITY_SEARCH_K

class VectorStoreMerger:
    """
    A class to merge multiple vector stores into a single vector store.
    """

    @staticmethod
    def merge(many_vector_stores: List[VectorStore]) -> VectorStore:
        """
        Merges the vector stores into a single vector store.

        :return: A new vector store containing all vectors from the input stores.
        """
        logging.info(f"VectorStoreMerger: Starting Merge. many_vector_stores.count={len(many_vector_stores)}")

        target_vectorstore: VectorStore = many_vector_stores[0]

        if len(many_vector_stores) == 1:
            # If there's only one vector store, return it directly
            logging.info(f"VectorStoreMerger: Only One. Just return it. many_vector_stores-count={len(many_vector_stores)}")
            return target_vectorstore

        all_docs = []

        counter:int = 0

        # Skip the first vector store (which is already our target)
        for vs in many_vector_stores[1:]:
            counter += 1
            logging.info(f"VectorStoreMerger: Looping. counter={counter}. many_vector_stores.count{len(many_vector_stores)}")

            # You may need to use a retriever or custom method to extract all documents
            docs = vs.similarity_search("", k=DEFAULT_SIMILARITY_SEARCH_K)  # Use a blank query to get many docs
            logging.info(f"VectorStoreMerger: Looping. this-loop-docs-count:{len(docs)}")
            all_docs.extend(docs)

        logging.info(f"VectorStoreMerger: all_docs.count={len(all_docs)}")
        # Add all documents to the target vectorstore
        target_vectorstore.add_documents(all_docs)

        logging.info(f"VectorStoreMerger: about to return (single) target_vectorstore.")
        return target_vectorstore
