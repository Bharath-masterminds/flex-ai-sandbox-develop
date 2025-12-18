from fx_ai_reusables.authenticators.hcp.cache_aside_decorators.hcp_authenticator_cache_aside_decorator import HcpAuthenticatorCacheAsideDecorator
from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader

from deprecated import deprecated

@deprecated(reason="Do not use Singleton.")
class HcpAuthenticatorSingleton:
    """ Singleton for IHcpAuthenticator. Cheap substitute for IoC/DI library. """

    _instance: IHcpAuthenticator = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = HcpAuthenticatorCacheAsideDecorator(HcpAuthenticator(AzureLlmConfigAndSecretsHolderWrapperReader()))
        return cls._instance

