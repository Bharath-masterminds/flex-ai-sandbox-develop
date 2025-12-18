"""
Liquid Mapper Composition Root - Main IoC container for the Liquid Mapper system.
Wires up all dependencies using dependency-injector, reusing fx_ai_reusables components.
"""

import logging
import sys
from pathlib import Path
from dependency_injector import containers, providers

# Add parent directory to path for relative imports
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from ioc.liquid_mapper_ioc_config import LiquidMapperIocConfig
from services.mapping_search_service import MappingSearchService
from services.context_db_service import ContextDbService
from services.file_storage_service import FileStorageService
from services.prompt_builder_service import PromptBuilderService

from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.secrets.concretes.file_mount.volume_mount_secret_retriever import VolumeMountSecretRetriever
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.configmaps.concretes.local_file.local_file_config_map_retriever import LocalFileConfigMapRetriever
from fx_ai_reusables.llm.creators.interfaces.llm_creator_interface import ILlmCreator
from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.cache_aside_decorators.hcp_authenticator_cache_aside_decorator import HcpAuthenticatorCacheAsideDecorator
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.streamlit.authenticators import StreamlitAzureAuth
from fx_ai_reusables.ioc.configuration.ioc_configuration import IocConfig


class LiquidMapperCompositionRoot(containers.DeclarativeContainer):
    """
    Liquid Mapper Composition Root - Main IoC container for dependency injection.
    
    Reuses fx_ai_reusables components (secrets, config, LLM, auth) and adds
    Liquid Mapper specific services (mapping search, context DB, file storage).
    """

    # Define configuration
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
        return logger

    # Create logger providers
    _hcp_authenticator_logger = providers.Callable(_create_logger, name="HcpAuthenticator")
    _llm_creator_logger = providers.Callable(_create_logger, name="LlmCreator")
    _streamlit_azure_auth_logger = providers.Callable(_create_logger, name="StreamlitAzureAuth")
    _mapping_search_logger = providers.Callable(_create_logger, name="MappingSearchService")
    _file_storage_logger = providers.Callable(_create_logger, name="FileStorageService")
    _context_db_logger = providers.Callable(_create_logger, name="ContextDbService")
    _prompt_builder_logger = providers.Callable(_create_logger, name="PromptBuilderService")

    # Config map retriever - use local file for dev, environment variables for deployed
    _config_map_retriever: IConfigMapRetriever = providers.Selector(
        _config.DeploymentFlavor,
        DEVELOPMENTLOCAL=providers.Singleton(
            LocalFileConfigMapRetriever,
            properties_file_names=["use_cases/Liquid_Mapper/liquidmapper.configmaps.txt"],
            base_directory=Path(__file__).resolve().parents[3],  # Go to workspace root
            logger=providers.Callable(_create_logger, name="LocalFileConfigMapRetriever"),
            lazy_load=True
        ),
        K8DEPLOYED=providers.Singleton(EnvironmentVariablesConfigMapRetriever),
        GITWORKFLOWDEPLOYED=providers.Singleton(EnvironmentVariablesConfigMapRetriever),
    )

    # Secrets retriever - environment-based selection
    _secrets_retriever: ISecretRetriever = providers.Selector(
        _config.DeploymentFlavor,
        DEVELOPMENTLOCAL=providers.Singleton(EnvironmentVariableSecretRetriever),
        K8DEPLOYED=providers.Singleton(VolumeMountSecretRetriever),
        GITWORKFLOWDEPLOYED=providers.Singleton(VolumeMountSecretRetriever),
    )

    # Environment reader for Azure LLM configuration
    _environment_reader_instance: IAzureLlmConfigAndSecretsHolderWrapperReader = providers.Singleton(
        AzureLlmConfigAndSecretsHolderWrapperReader,
        config_map_retriever=_config_map_retriever,
        secrets_retriever=_secrets_retriever
    )

    # HCP Authentication (for LLM API calls) - with caching decorator
    _undecorated_hcp_authenticator: IHcpAuthenticator = providers.Factory(
        HcpAuthenticator,
        azure_llm_configmap_and_secrets_holder_wrapper_retriever=_environment_reader_instance
    )

    _hcp_authenticator: IHcpAuthenticator = providers.Singleton(
        HcpAuthenticatorCacheAsideDecorator,
        inner_item_to_decorate=_undecorated_hcp_authenticator
    )

    # LLM Creator
    _llm_creator: ILlmCreator = providers.Singleton(
        AzureChatOpenAILlmCreator,
        environment_values_rdr=_environment_reader_instance,
        hcp_authenticator=_hcp_authenticator
    )

    # Streamlit Azure Auth (for user authentication)
    _streamlit_azure_auth: StreamlitAzureAuth = providers.Singleton(
        StreamlitAzureAuth,
        secret_retriever=_secrets_retriever,
        config_map_retriever=_config_map_retriever,
        logger=_streamlit_azure_auth_logger
    )

    # Liquid Mapper IoC Config instance (needs config map retriever)
    _liquid_mapper_config = providers.Singleton(
        LiquidMapperIocConfig,
        config_map_retriever=_config_map_retriever
    )

    # Liquid Mapper specific services
    _mapping_search_service = providers.Factory(
        MappingSearchService,
        logger=_mapping_search_logger
    )

    _context_db_service = providers.Factory(
        ContextDbService,
        secret_retriever=_secrets_retriever,
        logger=_context_db_logger
    )

    _file_storage_service = providers.Factory(
        FileStorageService,
        mapping_table_path=providers.Callable(
            lambda config: config.get_full_mapping_table_path(),
            config=_liquid_mapper_config
        ),
        liquid_template_path=providers.Callable(
            lambda config: config.get_full_liquid_template_path(),
            config=_liquid_mapper_config
        ),
        logger=_file_storage_logger
    )

    _prompt_builder_service = providers.Factory(
        PromptBuilderService,
        logger=_prompt_builder_logger
    )

    # Public providers exposed as class attributes
    get_azure_auth: StreamlitAzureAuth = providers.Callable(
        lambda auth: auth,
        auth=_streamlit_azure_auth
    )
    
    get_secret_retriever: ISecretRetriever = providers.Callable(
        lambda retriever: retriever,
        retriever=_secrets_retriever
    )
    
    get_config_map_retriever: IConfigMapRetriever = providers.Callable(
        lambda retriever: retriever,
        retriever=_config_map_retriever
    )
    
    get_llm_creator: ILlmCreator = providers.Callable(
        lambda creator: creator,
        creator=_llm_creator
    )

    get_mapping_search_service = providers.Callable(
        lambda service: service,
        service=_mapping_search_service
    )

    get_context_db_service = providers.Callable(
        lambda service: service,
        service=_context_db_service
    )

    get_file_storage_service = providers.Callable(
        lambda service: service,
        service=_file_storage_service
    )
