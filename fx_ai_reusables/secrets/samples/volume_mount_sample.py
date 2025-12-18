import asyncio
import logging

from fx_ai_reusables.secrets.concretes.file_mount.volume_mount_secret_retriever import VolumeMountSecretRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


# sample usage
async def main():

    logging.basicConfig(
        level=logging.DEBUG,  # or DEBUG
        format='%(asctime)s %(levelname)s %(message)s'
    )


    secret_retriever: ISecretRetriever = VolumeMountSecretRetriever()

    result: str = await secret_retriever.retrieve_mandatory_secret_value("MyFirstSecretName")
    #logging.info(f"SAMPLE Logging, Do NOT log in real code.  Retrieved secret value: {result}")

    opt_result: str | None = await secret_retriever.retrieve_optional_secret_value("MyFirstSecretName")
    #logging.info(f"SAMPLE Logging, Do NOT log in real code.  Optional Retrieved secret value: {opt_result}")

    opt_result_empty: str | None = await secret_retriever.retrieve_secret("DoesNotExist")
    #logging.info(f"SAMPLE Logging, Do NOT log in real code.  Optional Retrieved secret value: {opt_result_empty}")


# Run the main function
asyncio.run(main())