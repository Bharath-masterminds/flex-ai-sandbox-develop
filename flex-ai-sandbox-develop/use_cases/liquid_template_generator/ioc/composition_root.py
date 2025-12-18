from dependency_injector import containers, providers
import logging

from fx_ai_reusables.authenticators.hcp.cache_aside_decorators.hcp_authenticator_cache_aside_decorator import \
    HcpAuthenticatorCacheAsideDecorator
from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.configmaps import EnvironmentVariablesConfigMapRetriever, IConfigMapRetriever
from fx_ai_reusables.environment_fetcher import IEnvironmentFetcher, EnvironmentFetcher, EmptyEnvironmentFetcher
from fx_ai_reusables.environment_loading import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import \
    IAzureLlmConfigAndSecretsHolderWrapperReader

from fx_ai_reusables.ioc.configuration.ioc_configuration import IocConfig
from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
from fx_ai_reusables.llm.creators.interfaces.llm_creator_interface import ILlmCreator
from fx_ai_reusables.secrets import EnvironmentVariableSecretRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.secrets.concretes.hashicorp_vault import HashiCorpVaultSecretRetrieverFactory
from fx_ai_reusables.streamlit.authenticators import StreamlitAzureAuth
from use_cases.liquid_template_generator.runners.interfaces.stream_lit_runner_interface import IStreamLitRunner
from use_cases.liquid_template_generator.runners.stream_lit_runner_concrete import StreamLitRunnerConcrete
from use_cases.liquid_template_generator.utils.file_handler import FileHandler
from use_cases.liquid_template_generator.utils.template_generator import TemplateGenerator
from use_cases.liquid_template_generator.utils.template_renderer import TemplateRenderer


class MyCompositionRoot(containers.DeclarativeContainer):
    """
    MyCompositionRoot is the main IoC container for the application.
    Your app should not call it "My", "My" is used here to show it has no special naming requirement.
    """

    # Define configuration
    # note "private" _ to encapsulate in this class
    _config = providers.Configuration()

    # Set configuration values during container initialization
    _config.from_dict({
        "DeploymentFlavor": IocConfig.DeploymentFlavor
    })

    # Logger factory for creating named loggers
    @staticmethod
    def _create_logger(name: str) -> logging.Logger:
        """Create a logger with the given name that uses the root logger configuration."""
        logger = logging.getLogger(name)
        # Don't add custom handlers - let the logger use the root logger's configuration
        # This prevents duplicate log messages when both root and named loggers have handlers
        # The root logger is configured in app.py with logging.basicConfig()
        return logger

    # Create logger providers
    _template_renderer_logger = providers.Callable(_create_logger, name="TemplateRenderer")
    _template_generator_logger = providers.Callable(_create_logger, name="TemplateGenerator") 
    _file_handler_logger = providers.Callable(_create_logger, name="FileHandler")
    _stream_lit_runner_logger = providers.Callable(_create_logger, name="StreamLitRunner")
    _streamlit_azure_auth_logger = providers.Callable(_create_logger, name="StreamlitAzureAuth")

    #PRIMARY "CHOICE" Functionality: Select between different implementations based on configuration
    # Define animal manager provider based on deployment flavor
    # note "private" _ to encapsulate in this class

    _config_map_retriever: IConfigMapRetriever = providers.Selector(
        _config.DeploymentFlavor,
        DEVELOPMENTLOCAL=providers.Factory(EnvironmentVariablesConfigMapRetriever),
        K8DEPLOYED=providers.Factory(EnvironmentVariablesConfigMapRetriever),
        GITWORKFLOWDEPLOYED=providers.Factory(EnvironmentVariablesConfigMapRetriever),
    )

    _secrets_retriever: ISecretRetriever = providers.Selector(
        _config.DeploymentFlavor,
        DEVELOPMENTLOCAL=providers.Singleton(
            HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap,
            config_retriever=_config_map_retriever,
            logger=providers.Callable(_create_logger, name="HashiVaultSecretRetriever")
        ),
        K8DEPLOYED=providers.Factory(EnvironmentVariableSecretRetriever),
        GITWORKFLOWDEPLOYED=providers.Factory(EnvironmentVariableSecretRetriever),
    )

    _environment_reader_instance: IAzureLlmConfigAndSecretsHolderWrapperReader = providers.Factory(
        AzureLlmConfigAndSecretsHolderWrapperReader,
        config_map_retriever=_config_map_retriever,
        secrets_retriever=_secrets_retriever
    )

    _undecorated_raw_hcp_authentication: IHcpAuthenticator = providers.Factory(
        HcpAuthenticator,
        azure_llm_configmap_and_secrets_holder_wrapper_retriever=_environment_reader_instance
    )

    _cache_aside_hcp_authentication: IHcpAuthenticator = providers.Singleton(
        HcpAuthenticatorCacheAsideDecorator,
        inner_item_to_decorate=_undecorated_raw_hcp_authentication
    )


    _llm_creator: ILlmCreator = providers.Singleton(
        AzureChatOpenAILlmCreator,
        environment_values_rdr=_environment_reader_instance,
        hcp_authenticator = _cache_aside_hcp_authentication
    )



    _template_rend: TemplateRenderer = providers.Singleton(
        TemplateRenderer,
        logger=_template_renderer_logger
    )

    _template_gen: TemplateGenerator = providers.Singleton(
        TemplateGenerator,
        _template_rend,
        llm_creator=_llm_creator,
        max_iterations=4,
        logger=_template_generator_logger
    )

    _streamlit_azure_auth: StreamlitAzureAuth = providers.Singleton(
        StreamlitAzureAuth,
        secret_retriever=_secrets_retriever,
        config_map_retriever=_config_map_retriever,
        logger=_streamlit_azure_auth_logger
    )

    _file_handler: FileHandler = providers.Factory(
        FileHandler,
        logger=_file_handler_logger
    )

    # Define _runner/IStreamLitRunner/StreamLitRunnerConcrete with injected-dependencies here.  this will be the "top layer" object, as seen in 'get_application_entry_class' below
        # note "private" _ to encapsulate in this class
    _runner: IStreamLitRunner = providers.Factory(
        StreamLitRunnerConcrete,
        template_rend = _template_rend,
        template_gen= _template_gen,
        file_hand = _file_handler,
        secret_retriever = _secrets_retriever,
        config_map_retriever = _config_map_retriever,
        azure_auth = _streamlit_azure_auth,
        logger=_stream_lit_runner_logger
    )

    # below ("public") method 'get_env_fetcher' exposed so that it can be called once from the hosting app
    # need to figure out a better way to deal with this.  Maybe one of the other objects here could get it injected
    # and call it?????
    get_env_fetcher: IEnvironmentFetcher = providers.Selector(
        _config.DeploymentFlavor,
        DEVELOPMENTLOCAL=providers.Factory(EnvironmentFetcher),
        K8DEPLOYED=providers.Factory(EmptyEnvironmentFetcher),
        GITWORKFLOWDEPLOYED=providers.Factory(EmptyEnvironmentFetcher),
    )

    # below ("public") method 'get_application_entry_class' could be named anything.  the 'controller' language below is from 'dependency_injector' framework.
    # Use a providers to expose the _runner through a public interface 'IStreamLitRunner'
    get_application_entry_class: IStreamLitRunner = providers.Callable(
        lambda controller: controller,
        controller=_runner
    )
  