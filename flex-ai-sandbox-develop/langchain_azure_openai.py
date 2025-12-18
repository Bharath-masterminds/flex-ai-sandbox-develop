# Azure OpenAI with LangChain Integration
#
# This script demonstrates how to use Azure OpenAI services with LangChain,
# including authentication using Healthcare Cloud Platform (HCP) tokens.

# Environment Setup
# First, load environment variables from a .env file. Refer to .env.example

import asyncio
import sys

from fx_ai_reusables.authenticators.hcp.concretes import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.interfaces import IHcpAuthenticator
from fx_ai_reusables.llm.creators import AzureChatOpenAILlmCreator
from fx_ai_reusables.llm.creators.interfaces import ILlmCreator
from fx_ai_reusables.configmaps.concretes import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.secrets.concretes.env_variable import EnvironmentVariableSecretRetriever
from fx_ai_reusables.environment_loading.concretes import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.llm.reporters import LlmReporter
from llm_worker import LlmWorker


# Authentication Functions
# Method to fetch token for azure open ai from HCP


# Get the HCP authentication token
async def main():
    # Get prompt from command line argument, or use a default
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello, how are you?"
    print(f"the supplied prompt is: ***{prompt}***")

    # Create dependencies for AzureLlmConfigAndSecretsHolderWrapperReader
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()
    environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)

    # not shown, there is a cache-aside decorator for the HCP authenticator, that looks at the EXPIRES_ON value.
    hcp_token_creator: IHcpAuthenticator = HcpAuthenticator(environment_reader)


    # Initialize LLM with Authentication
    # Create a function to initialize the Azure OpenAI model with HCP token authentication
    # and optional parameters for tools and structured output.

    llm_creator: ILlmCreator = AzureChatOpenAILlmCreator(environment_reader, hcp_token_creator)
    llm = await llm_creator.create_llm()
    print(f"LLM client created: {llm}")

    # Testing the LLM Integration
    # Now let's initialize the LLM and test it with a simple query.
    # Note, the "logic" is inside LlmWorker. You can go edit the code in LlmWorker to experiment.

    # Pass the prompt to LlmWorker
    resp = await LlmWorker.invoke_llm(llm, prompt=prompt)

    # available keys in the response message
    await LlmReporter.show_keys(resp)

    # Resp is an instance of AIMessage(langchain)
    await LlmReporter.show_type(resp)

    # Display the Response
    # Print the content of the response from the LLM.

    # available keys in the response message
    await LlmReporter.show_content(resp)

    # show usage costs
    await LlmReporter.show_usage_costs(resp)


# Run the main function
asyncio.run(main())
