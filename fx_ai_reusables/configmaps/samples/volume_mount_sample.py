import asyncio
import logging

from fx_ai_reusables.configmaps import IConfigMapRetriever
from fx_ai_reusables.configmaps.concretes.file_mount.volume_mount_config_map_retriever import \
    VolumeMountConfigMapRetriever


# sample usage
async def main():

    logging.basicConfig(
        level=logging.DEBUG,  # or DEBUG
        format='%(asctime)s %(levelname)s %(message)s'
    )


    config_map_retriever: IConfigMapRetriever = VolumeMountConfigMapRetriever()

    result: str = await config_map_retriever.retrieve_mandatory_config_map_value("MyFirstConfigMapName")
    logging.info(f"SAMPLE Logging, Do NOT log in real code.  Retrieved config_map value: {result}")

    opt_result: str | None = await config_map_retriever.retrieve_optional_config_map_value("MyFirstConfigMapName")
    logging.info(f"SAMPLE Logging, Do NOT log in real code.  Optional Retrieved config_map value: {opt_result}")

    opt_result_empty: str | None = await config_map_retriever.retrieve_config_map("DoesNotExist")
    logging.info(f"SAMPLE Logging, Do NOT log in real code.  Optional Retrieved config_map value: {opt_result_empty}")


# Run the main function
asyncio.run(main())