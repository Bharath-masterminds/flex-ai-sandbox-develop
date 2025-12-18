from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import AzureLlmConfigAndSecretsHolderWrapper
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever

class AzureLlmConfigAndSecretsHolderWrapperReader(IAzureLlmConfigAndSecretsHolderWrapperReader):

    def __init__(self, config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever):
        self.config_map_retriever: IConfigMapRetriever = config_map_retriever
        self.secrets_retriever: ISecretRetriever = secrets_retriever


    async def read_azure_llm_config_and_secrets_holder_wrapper(self) -> AzureLlmConfigAndSecretsHolderWrapper:
        return await AzureLlmConfigAndSecretsHolderWrapper.hydrate(self.config_map_retriever, self.secrets_retriever)

