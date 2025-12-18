from typing import List

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_text_splitters import Language

from fx_ai_reusables.chunkers.interfaces.chunker_interface import IChunker
from fx_ai_reusables.vectorizers.constants import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP


class SourceCodeBySourceFolderChunker(IChunker):

    def __init__(self, source_code_language: Language):
        # Language where will be CSHARP, JAVA, etc, etc.
        # see https://api.python.langchain.com/en/v0.0.354/text_splitter/langchain.text_splitter.Language.html#langchain.text_splitter.Language
        self.source_code_language: Language = source_code_language

    async def chunk_it(self, root_directory: str, glob_filter: str, chunk_size_value: int = DEFAULT_CHUNK_SIZE,
                       chunk_overlap_value: int = DEFAULT_CHUNK_OVERLAP) \
            -> List[Document]:
        import logging

        logging.info(
            f"SourceCodeBySourceFolderChunker:Chunking source code: root_directory={root_directory}, glob_filter={glob_filter}, language={self.source_code_language}")

        # Step 1: Load source code files from a directory
        loader: DirectoryLoader = DirectoryLoader(root_directory, glob=glob_filter, loader_cls=TextLoader)
        documents: List[Document] = loader.load()

        splitter = RecursiveCharacterTextSplitter.from_language(
            language=self.source_code_language, chunk_size=chunk_size_value, chunk_overlap=chunk_overlap_value
        )

        # Step 2: Chunk the documents
        print("📄 Loading and processing source code files...")
        chunks: List[Document] = splitter.split_documents(documents)

        return chunks
