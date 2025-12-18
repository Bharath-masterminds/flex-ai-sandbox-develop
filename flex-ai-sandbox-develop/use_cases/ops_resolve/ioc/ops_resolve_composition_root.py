"""
OpsResolve Composition Root - Main IoC container for the OpsResolve system.
Wires up all dependencies based on deployment environment using dependency-injector.
"""

import logging
from dependency_injector import containers, providers

from use_cases.ops_resolve.ioc.ops_resolve_ioc_config import OpsResolveIocConfig
from use_cases.ops_resolve.ops_resolve_supervisor import OpsResolveSupervisor

from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.secrets.concretes.file_mount.volume_mount_secret_retriever import VolumeMountSecretRetriever
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.llm.creators.interfaces.llm_creator_interface import ILlmCreator
from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.cache_aside_decorators.hcp_authenticator_cache_aside_decorator import HcpAuthenticatorCacheAsideDecorator
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.agents.servicenow.servicenow_agent import ServiceNowAgent
from fx_ai_reusables.agents.app_insights.app_insights_agent import AppInsightsAgent
from fx_ai_reusables.tools.servicenow_tools import create_get_incident_by_incident_number_tool
from fx_ai_reusables.tools.app_insights_tools import (
    create_get_app_insights_operation_id_using_url_tool,
    create_get_app_insights_logs_using_operation_id_tool,
)
from fx_ai_reusables.streamlit.authenticators import StreamlitAzureAuth


class OpsResolveCompositionRoot(containers.DeclarativeContainer):
    """
    OpsResolve Composition Root - Main IoC container for dependency injection.
    
    Uses dependency-injector library for declarative dependency management.
    Selects appropriate implementations based on deployment environment:
    - DEVELOPMENTLOCAL: Environment variable secrets
    - K8DEPLOYED: Volume mount secrets  
    - GITWORKFLOWDEPLOYED: Volume mount secrets
    
    All environments use the same agents and LLM configuration.
    """

    # Define configuration
    _config = providers.Configuration()

    # Set configuration values during container initialization
    _config.from_dict({
        "DeploymentFlavor": OpsResolveIocConfig.DeploymentFlavor
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
    _servicenow_agent_logger = providers.Callable(_create_logger, name="ServiceNowAgent")
    _app_insights_agent_logger = providers.Callable(_create_logger, name="AppInsightsAgent")
    _supervisor_logger = providers.Callable(_create_logger, name="OpsResolveSupervisor")
    _streamlit_azure_auth_logger = providers.Callable(_create_logger, name="StreamlitAzureAuth")

    # Config map retriever - always use environment variables
    _config_map_retriever: IConfigMapRetriever = providers.Singleton(
        EnvironmentVariablesConfigMapRetriever
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

    # Helper to create LLM asynchronously (since agents need actual LLM instance)
    @staticmethod
    async def _create_llm_async(llm_creator: ILlmCreator):
        """Helper to create LLM asynchronously."""
        return await llm_creator.create_llm()

    # ServiceNow Agent Factory (needs async LLM creation)
    @staticmethod
    async def _create_servicenow_agent(llm_creator: ILlmCreator, secret_retriever: ISecretRetriever):
        """Create ServiceNow agent with async LLM creation and secret retriever."""
        llm = await OpsResolveCompositionRoot._create_llm_async(llm_creator)
        
        # Create tools using factory function with secret retriever
        tools = [create_get_incident_by_incident_number_tool(secret_retriever)]
        
        return ServiceNowAgent(tools, llm, secret_retriever)

    # App Insights Agent Factory (needs async LLM creation)
    @staticmethod
    async def _create_app_insights_agent(llm_creator: ILlmCreator, secret_retriever: ISecretRetriever):
        """Create App Insights agent with async LLM creation and secret retriever."""
        llm = await OpsResolveCompositionRoot._create_llm_async(llm_creator)
        
        # Create tools using factory functions with secret retriever
        tools = [
            create_get_app_insights_operation_id_using_url_tool(secret_retriever),
            create_get_app_insights_logs_using_operation_id_tool(secret_retriever),
        ]
        
        return AppInsightsAgent(tools, llm, secret_retriever)

    # Supervisor Factory (needs async agent and LLM creation)
    @staticmethod
    async def _create_supervisor(llm_creator: ILlmCreator, secret_retriever: ISecretRetriever):
        """Create supervisor with all dependencies asynchronously."""
        llm = await OpsResolveCompositionRoot._create_llm_async(llm_creator)
        
        # Create agents with secret retriever
        servicenow_agent = await OpsResolveCompositionRoot._create_servicenow_agent(llm_creator, secret_retriever)
        app_insights_agent = await OpsResolveCompositionRoot._create_app_insights_agent(llm_creator, secret_retriever)
        
        # Create supervisor with LLM and agents
        return OpsResolveSupervisor(llm, [servicenow_agent, app_insights_agent])

    # Public providers exposed as class attributes (not methods!)
    # These are callable and can be invoked like: container.get_azure_auth()
    
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
    
    # CRITICAL FIX - November 2024:
    # get_supervisor must be a provider, NOT an instance method!
    # 
    # ISSUE: Originally implemented as: async def get_supervisor(self) -> OpsResolveSupervisor
    # This caused error: 'DynamicContainer' object has no attribute 'get_supervisor'
    # 
    # ROOT CAUSE:
    # - DeclarativeContainer classes don't create instances of your custom class
    # - When you call OpsResolveCompositionRoot(), it returns a DynamicContainer instance
    # - Instance methods defined on your class DO NOT exist on the DynamicContainer
    # - Only providers (class attributes) are accessible on the container instance
    #
    # SOLUTION:
    # - Convert get_supervisor from instance method to providers.Callable
    # - The provider returns a coroutine (async function) that must be awaited
    # - Usage: supervisor = await container.get_supervisor()
    # - The returned coroutine calls the static _create_supervisor method
    #
    # This pattern must be followed for ANY method you want to expose on the container!
    get_supervisor = providers.Callable(
        lambda llm_creator, secret_retriever: OpsResolveCompositionRoot._create_supervisor(llm_creator, secret_retriever),
        llm_creator=_llm_creator,
        secret_retriever=_secrets_retriever
    )