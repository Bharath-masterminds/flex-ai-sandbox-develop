import asyncio
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage

from fx_ai_reusables.authenticators.hcp.concretes import HcpAuthenticator
from fx_ai_reusables.authenticators.hcp.interfaces import IHcpAuthenticator
from fx_ai_reusables.llm.creators import AzureChatOpenAILlmCreator
from fx_ai_reusables.llm.creators.interfaces import ILlmCreator
from fx_ai_reusables.configmaps.concretes import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.secrets.concretes.env_variable import EnvironmentVariableSecretRetriever
from fx_ai_reusables.environment_loading.concretes import AzureLlmConfigAndSecretsHolderWrapperReader


# Define the weather tool factory
def make_population_tool(llm):
    async def get_population(city: str) -> str:
        """
        Get the population for a given city using the LLM.
        """
        prompt = f"What is the population in {city}?"
        response = await llm.ainvoke(prompt)
        return response

    return get_population


async def main():

    # Create dependencies for AzureLlmConfigAndSecretsHolderWrapperReader
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()
    environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)

    # not shown, there is a cache-aside decorator for the HCP authenticator, that looks at the EXPIRES_ON value.
    hcp_token_creator: IHcpAuthenticator = HcpAuthenticator(environment_reader)

    # Initialize the LLM
    llm_creator: ILlmCreator = AzureChatOpenAILlmCreator(environment_reader, hcp_token_creator)
    llm = await llm_creator.create_llm()

    # Create the tool with the llm bound
    population_tool = make_population_tool(llm)

    # Create the agent
    agent = create_react_agent(
        model=llm, tools=[population_tool], prompt="You are a helpful assistant"
    )

    # Run the agent
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "what is the approximate estimated population in sf based on 2020 data?",
                }
            ]
        }
    )
    # print(result)

    # Extract and print the last AIMessage content
    messages = result.get("messages", [])
    # Find the last AIMessage in the list


    final_ai_message = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            final_ai_message = msg
            break

    if final_ai_message:
        print(final_ai_message.content)
    else:
        print("No AIMessage found in result.")


# Run the async main function
asyncio.run(main())
