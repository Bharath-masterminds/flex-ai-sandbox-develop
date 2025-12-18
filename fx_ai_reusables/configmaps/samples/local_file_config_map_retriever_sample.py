import asyncio
import logging
from pathlib import Path
from typing import Sequence, Dict, Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.configmaps.concretes.local_file.local_file_config_map_retriever import LocalFileConfigMapRetriever


async def main() -> None:
    """Demonstrates LocalFileConfigMapRetriever usage with two property files and various retrievals."""
    log_format: str = "%(asctime)s %(levelname)s %(message)s"
    level: int = logging.DEBUG
    logging.basicConfig(level=level, format=log_format)

    sample_dir: Path = Path(__file__).parent
    property_files: Sequence[str] = ["sample-appsettings-a.config.txt"
        , "sample-appsettings-b.config.txt"]

    contents: Dict[str, str] = {
        "sample-appsettings-a.config.txt": """# first file
MyFirstConfigMapName=ValueFromFileA
SharedOverrideKey=OriginalValueA
NameEqualsValue=NameEqualsValue
""",
        "sample-appsettings-b.config.txt": """# second file overrides prior
SharedOverrideKey=OverriddenValueB
AnotherKey=AnotherValueB
""",
    }

    for fname, text in contents.items():
        fname_str: str = fname
        text_str: str = text
        fpath: Path = sample_dir / fname_str
        file_exists: bool = fpath.exists()
        if not file_exists:
            written_bytes: int = fpath.write_text(text_str, encoding="utf-8")

    retriever: IConfigMapRetriever = LocalFileConfigMapRetriever(
        properties_file_names=property_files,
        base_directory=sample_dir,
        lazy_load=True,
    )

    mandatory_config_key: str = "MyFirstConfigMapName"
    mandatory_value: str = await retriever.retrieve_mandatory_config_map_value(mandatory_config_key)
    logging.info("Mandatory retrieval %s=%s", mandatory_config_key, mandatory_value)

    shared_override_key: str = "SharedOverrideKey"
    optional_value: Optional[str] = await retriever.retrieve_optional_config_map_value(shared_override_key)
    logging.info("Optional retrieval %s=%s", shared_override_key, optional_value)

    missing_key: str = "DoesNotExistKey"
    missing_optional: Optional[str] = await retriever.retrieve_optional_config_map_value(missing_key)
    logging.info("Optional retrieval %s=%s", missing_key, missing_optional)

    name_equals_value_key: str = "NameEqualsValue"
    name_equals_value: Optional[str] = await retriever.retrieve_optional_config_map_value(name_equals_value_key)
    logging.info("Optional retrieval %s=%s", name_equals_value_key, name_equals_value)


if __name__ == "__main__":
    asyncio.run(main())
