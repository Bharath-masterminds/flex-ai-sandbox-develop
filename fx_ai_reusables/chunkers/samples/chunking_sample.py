import asyncio
from typing import List

from langchain_core.documents import Document

from fx_ai_reusables.chunkers.concretes.by_source_folder_chunker import BySourceFolderChunker
from fx_ai_reusables.chunkers.interfaces.chunker_interface import IChunker


# sample usage
async def main():
    chunker_instance: IChunker = BySourceFolderChunker()

    root_directory: str = "~/src"  # Replace with your source code directory
    glob_filter = "**/*.cs"

    result:List[Document] = await chunker_instance.chunk_it(root_directory, glob_filter)

    print("List[Document].SIZE:", result.__sizeof__())


# Run the main function
asyncio.run(main())