import logging
from typing import Optional

from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import AzureLlmConfigAndSecretsHolderWrapper
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader

class AzureLlmConfigAndSecretsHolderWrapperCacheAsideDecorator(IAzureLlmConfigAndSecretsHolderWrapperReader):
    """Cache Aside Decorator for IEnvironmentValuesReader.
        AzureLlmConfigAndSecretsHolderWrapper is stored as a member-variable.
    """

    def __init__(self, inner_item_to_decorate: IAzureLlmConfigAndSecretsHolderWrapperReader):
        self._inner_item_to_decorate: IAzureLlmConfigAndSecretsHolderWrapperReader = inner_item_to_decorate
        self.cached_object_holder: Optional[AzureLlmConfigAndSecretsHolderWrapper] = None

    async def read_azure_llm_config_and_secrets_holder_wrapper(self) -> AzureLlmConfigAndSecretsHolderWrapper:
        logging.info("EnvironmentValuesReaderCacheAsideDecorator initiated")

        if self.cached_object_holder is None:
            logging.info("cached_object_holder (AzureLlmConfigAndSecretsHolderWrapper) is NONE, reading the values from _inner_item_to_decorate")
            self.cached_object_holder = await self._inner_item_to_decorate.read_azure_llm_config_and_secrets_holder_wrapper()

        if self.cached_object_holder is None:
            raise ValueError("AzureLlmConfigAndSecretsHolderWrapper is None. This should not happen if the _inner_item_to_decorate is implemented correctly.")

        return self.cached_object_holder