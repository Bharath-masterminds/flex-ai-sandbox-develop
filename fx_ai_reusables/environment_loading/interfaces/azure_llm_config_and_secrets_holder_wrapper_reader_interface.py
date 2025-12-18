from abc import ABC, abstractmethod

from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import AzureLlmConfigAndSecretsHolderWrapper

class IAzureLlmConfigAndSecretsHolderWrapperReader(ABC):
    """Interface for IAzureLlmConfigAndSecretsHolderWrapperReader Retrieval. """

    @abstractmethod
    async def read_azure_llm_config_and_secrets_holder_wrapper(self) -> AzureLlmConfigAndSecretsHolderWrapper:
        pass

