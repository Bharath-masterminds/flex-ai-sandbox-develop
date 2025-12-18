from typing import List

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from fx_ai_reusables.chunkers.interfaces.chunker_interface import IChunker
from fx_ai_reusables.vectorizers.constants import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP


class BySourceFolderChunker(IChunker):

    async def chunk_it(self, root_directory:str, glob_filter: str, chunk_size_value:int = DEFAULT_CHUNK_SIZE, chunk_overlap_value:int = DEFAULT_CHUNK_OVERLAP) \
            -> List[Document]:

        # Step 1: Load source code files from a directory
        loader: DirectoryLoader = DirectoryLoader(root_directory, glob=glob_filter, loader_cls=TextLoader)
        documents: List[Document] = loader.load()

        # Step 2: Chunk the documents
        print("📄 Loading and processing source code files...")
        splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size_value, chunk_overlap=chunk_overlap_value)
        chunks: List[Document] = splitter.split_documents(documents)

        return chunks

