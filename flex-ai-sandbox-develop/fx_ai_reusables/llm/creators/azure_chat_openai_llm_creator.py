from typing import List, Optional  # For type hints

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI
from pydantic import SecretStr

from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.environment_loading.constants import DEFAULT_TEMPERATURE
from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import (
    AzureLlmConfigAndSecretsHolderWrapper,
)
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import (
    IAzureLlmConfigAndSecretsHolderWrapperReader
)
from fx_ai_reusables.llm.creators.interfaces.llm_creator_interface import ILlmCreator


class AzureChatOpenAILlmCreator(ILlmCreator):
    """Implementation of LLM creation service for Azure OpenAI."""

    def __init__(self, environment_values_rdr: IAzureLlmConfigAndSecretsHolderWrapperReader, hcp_authenticator: IHcpAuthenticator):
        self.environment_values_rdr: IAzureLlmConfigAndSecretsHolderWrapperReader = environment_values_rdr
        self.hcp_authenticator: IHcpAuthenticator = hcp_authenticator

    async def create_llm(

            self,
            config: Optional[RunnableConfig] = None,
            tools: Optional[List] = None,
            tool_choice: str = "any",
            with_structured_output: bool = False,
            output_schema=None,
    ) -> BaseChatModel:
        """Initialize Azure OpenAI model with HCP token authentication.

        Args:
            hcp_token: authorization token for HCP
            config: Optional configuration for the runnable
            tools: Optional list of tools to bind to the LLM
            tool_choice: Strategy for tool selection ('any', 'auto', or specific tool name)
            with_structured_output: Whether to enable structured output
            output_schema: Schema for structured output

        Returns:
            Configured Azure OpenAI model instance
        """

        config_holder: AzureLlmConfigAndSecretsHolderWrapper = (
            await self.environment_values_rdr.read_azure_llm_config_and_secrets_holder_wrapper()
        )

        hcp_token: str = await self.hcp_authenticator.get_hcp_token()
        hcp_token_as_secret_str: SecretStr
        hcp_token_as_secret_str = SecretStr(hcp_token)

        # Initialize the Azure OpenAI model with authentication and configuration
        llm = AzureChatOpenAI(
            azure_endpoint=config_holder.azure_openai.AZURE_OPENAI_ENDPOINT,
            api_version=config_holder.azure_openai.AZURE_OPENAI_API_VERSION,
            azure_deployment=config_holder.azure_openai.AZURE_OPENAI_DEPLOYMENT_NAME,
            # revisit the code below to optionally set a property.  it is copilot suggestion.
            **(
                {"model": config_holder.azure_openai.AZURE_OPENAI_MODEL}
                if config_holder.azure_openai.AZURE_OPENAI_MODEL is not None
                else {}
            ),
            azure_ad_token=hcp_token_as_secret_str,  # Using the HCP token for authentication
            default_headers={
                "projectId": config_holder.azure_openai.UAIS_PROJECT_ID,  # Project identifier for tracking/billing
            },
            temperature=DEFAULT_TEMPERATURE  # Set to 0 for deterministic outputs
        )

        # If tools are provided, bind them to the LLM
        if tools:
            llm = llm.bind_tools(tools, tool_choice=tool_choice)

        # If structured output is requested, configure the LLM accordingly
        if with_structured_output:
            llm = llm.with_structured_output(output_schema)

        return llm
