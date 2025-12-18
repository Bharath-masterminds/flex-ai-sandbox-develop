import asyncio

from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.environment_fetcher import IEnvironmentFetcherAsync
from fx_ai_reusables.environment_fetcher.concrete_dotenv.environment_fetcher_async import EnvironmentFetcherAsync
from fx_ai_reusables.environment_loading.cache_aside_decorators.azure_llm_config_and_secrets_holder_wrapper_cache_aside_decorator import (
    AzureLlmConfigAndSecretsHolderWrapperCacheAsideDecorator
)
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import AzureLlmConfigAndSecretsHolderWrapper
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


# sample usage
async def main():

    # need to refactor to inject IEnvironmentFetcherAsync
    env_file_env_fetcher: IEnvironmentFetcherAsync = EnvironmentFetcherAsync()
    await env_file_env_fetcher.load_environment()

    config_map_retriever: IConfigMapRetriever = EnvironmentVariablesConfigMapRetriever()
    secret_retriever: ISecretRetriever = EnvironmentVariableSecretRetriever()

    # undecorated is for the raw functionality
    undecorated_azure_llm_configmap_and_secrets_holder_wrapper_retriever: IAzureLlmConfigAndSecretsHolderWrapperReader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secret_retriever)

    # now decorate the undecorated reader to provide cache-aside functionality
    cache_aside_azure_llm_configmap_and_secrets_holder_wrapper_retriever: IAzureLlmConfigAndSecretsHolderWrapperReader = AzureLlmConfigAndSecretsHolderWrapperCacheAsideDecorator(
        undecorated_azure_llm_configmap_and_secrets_holder_wrapper_retriever)

    holder: AzureLlmConfigAndSecretsHolderWrapper = await cache_aside_azure_llm_configmap_and_secrets_holder_wrapper_retriever.read_azure_llm_config_and_secrets_holder_wrapper()
    # print a few NON-secret values to verify loading
    print("holder.azure_openai.AZURE_OPENAI_API_VERSION:", holder.azure_openai.AZURE_OPENAI_API_VERSION)

    print("holder.azure_openai.AZURE_OPENAI_DEPLOYMENT_NAME:", holder.azure_openai.AZURE_OPENAI_DEPLOYMENT_NAME)
    if holder.azure_openai.AZURE_OPENAI_MODEL:
        print(f"holder.azure_openai.AZURE_OPENAI_MODEL: {holder.azure_openai.AZURE_OPENAI_MODEL} (was optional, but set)")
    else:
        print("holder.azure_openai.AZURE_OPENAI_MODEL is NONE.")


    print("holder.doc_intelligence.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:", holder.doc_intelligence.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT)

    if holder.remote_embedding_model:
        print(f"holder.embedding_model.AZURE_OPENAI_EMBEDDINGS_ENDPOINT: {holder.remote_embedding_model.AZURE_OPENAI_EMBEDDINGS_ENDPOINT}!")
    else:
        print("holder.embedding_model is NONE.  Are ALL variables that make up the EmbeddingModelConfig set?")

    print("holder.hcp.HCP_TOKEN_URL:", holder.hcp.HCP_TOKEN_URL)
    print("holder.hcp.HCP_TOKEN_SCOPE:", holder.hcp.HCP_TOKEN_SCOPE)
    print("holder.hcp.HCP_GRANT_TYPE:", holder.hcp.HCP_GRANT_TYPE)


# Run the main function
asyncio.run(main())
