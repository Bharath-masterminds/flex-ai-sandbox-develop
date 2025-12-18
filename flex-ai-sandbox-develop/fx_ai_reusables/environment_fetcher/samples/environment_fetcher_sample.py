import asyncio
import logging

from fx_ai_reusables.configmaps import IConfigMapRetriever, EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.environment_fetcher import IEnvironmentFetcherAsync
from fx_ai_reusables.environment_fetcher.concrete_dotenv import EnvironmentFetcherAsync
from fx_ai_reusables.environment_fetcher.concrete_empty.empty_environment_fetcher_async import EmptyEnvironmentFetcherAsync

# sample usage
async def main():

    logging.basicConfig(
        level=logging.DEBUG,  # or DEBUG
        format='%(asctime)s %(levelname)s %(message)s'
    )


    empty_env_fetcher: IEnvironmentFetcherAsync = EmptyEnvironmentFetcherAsync()
    await empty_env_fetcher.load_environment()



    # also see : fx_ai_reusables/tests/unit/test_environment_fetch.py the below is very uninteresting
    env_file_env_fetcher: IEnvironmentFetcherAsync = EnvironmentFetcherAsync()
    await env_file_env_fetcher.load_environment(None, override = True, current_working_directory = True)

    #note, the above .. makes ENVIRONMENT variables "available"
    # below shows how to consume them.

    config_map_retriever: IConfigMapRetriever = EnvironmentVariablesConfigMapRetriever()
    found_value: str = await config_map_retriever.retrieve_mandatory_config_map_value("SAMPLE_TEST_NOT_REAL_ENVIRONMENT_VARIABLE_NAME")
    logging.info(found_value)

# Run the main function
asyncio.run(main())