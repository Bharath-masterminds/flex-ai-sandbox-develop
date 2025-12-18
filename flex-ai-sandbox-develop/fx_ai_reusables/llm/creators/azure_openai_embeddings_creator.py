from langchain_core.embeddings import Embeddings
from langchain_openai import AzureOpenAIEmbeddings
from pydantic import SecretStr

from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import (
    AzureLlmConfigAndSecretsHolderWrapper,
)
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import (
    IAzureLlmConfigAndSecretsHolderWrapperReader
)
from fx_ai_reusables.llm.creators.interfaces.llm_embedding_creator_interface import ILlmEmbeddingCreator


class AzureOpenAIEmbeddingsCreator(ILlmEmbeddingCreator):

    def __init__(self, hcp_authenticator: IHcpAuthenticator, azure_llm_configmap_and_secrets_holder_wrapper_retriever: IAzureLlmConfigAndSecretsHolderWrapperReader):
        self.hcp_authenticator: IHcpAuthenticator = hcp_authenticator
        self.azure_llm_configmap_and_secrets_holder_wrapper_retriever = azure_llm_configmap_and_secrets_holder_wrapper_retriever

    async def create_llm_embeddings(
            self
    ) -> Embeddings:
        """Massage Azure OpenAI model with HCP token authentication.

        Args:
            llm: BaseChatModel instance to be configured
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
            await self.azure_llm_configmap_and_secrets_holder_wrapper_retriever.read_azure_llm_config_and_secrets_holder_wrapper()
        )

        hcp_token: str = await self.hcp_authenticator.get_hcp_token()

        hcp_token_as_secret_str: SecretStr
        hcp_token_as_secret_str = SecretStr(hcp_token)

        # Initialize the Azure OpenAI embeddings
        embedding: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
            azure_deployment=config_holder.remote_embedding_model.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME,
            model=config_holder.remote_embedding_model.AZURE_OPENAI_EMBEDDING_MODEL_NAME,
            api_version=config_holder.azure_openai.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config_holder.azure_openai.AZURE_OPENAI_ENDPOINT,
            openai_api_type="azure_ad",
            validate_base_url=False,
            azure_ad_token=hcp_token_as_secret_str,
            default_headers={
                "projectId": config_holder.azure_openai.UAIS_PROJECT_ID,
            }
        )

        return embedding
