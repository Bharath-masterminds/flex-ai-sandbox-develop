# Azure authentication libraries
# LangChain components
# Azure OpenAI integration for LangChain
from fx_ai_reusables.authenticators.constants import DEFAULT_AUTH_TIMEOUT
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from fx_ai_reusables.environment_loading.domain.azure_llm_config_and_secrets_holder_wrapper import AzureLlmConfigAndSecretsHolderWrapper
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import IAzureLlmConfigAndSecretsHolderWrapperReader


class HcpAuthenticator(IHcpAuthenticator):

    def __init__(self, azure_llm_configmap_and_secrets_holder_wrapper_retriever: IAzureLlmConfigAndSecretsHolderWrapperReader):
        self.azure_llm_configmap_and_secrets_holder_wrapper_retriever: IAzureLlmConfigAndSecretsHolderWrapperReader = azure_llm_configmap_and_secrets_holder_wrapper_retriever

    async def get_hcp_token(self) -> str:
        # Import necessary libraries for making HTTP requests asynchronously
        import httpx

        config_holder: AzureLlmConfigAndSecretsHolderWrapper = await self.azure_llm_configmap_and_secrets_holder_wrapper_retriever.read_azure_llm_config_and_secrets_holder_wrapper()

        # Use an asynchronous client to make a POST request to the auth URL
        async with httpx.AsyncClient() as client:
            # Build the request body with client credentials
            body = {
                "grant_type": config_holder.hcp.HCP_GRANT_TYPE,
                "scope": config_holder.hcp.HCP_TOKEN_SCOPE,
                "client_id": config_holder.hcp.HCP_CLIENT_ID,
                "client_secret": config_holder.hcp.HCP_CLIENT_SECRET,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            # Make the request and extract the access token from the response
            resp = await client.post(config_holder.hcp.HCP_TOKEN_URL, headers=headers, data=body, timeout=DEFAULT_AUTH_TIMEOUT)
            access_token = resp.json()["access_token"]

        return access_token
