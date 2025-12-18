import sys
import os

import re
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from fx_ai_reusables.agents.interfaces.base_agent import IAgent
from fx_ai_reusables.agents.app_insights.system_prompt import APP_INSIGHTS_SYSTEM_PROMPT
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


class AppInsightsAgent(IAgent):
    """Agent responsible for collecting and analyzing application logs.

    This agent handles interactions with Azure Application Insights to retrieve
    operation IDs, query logs, and provide structured log analysis for incident
    troubleshooting and root cause analysis.

    Attributes:
        app_insight_agent: The LangGraph react agent configured with Azure monitoring tools.
    """

    def __init__(self, tools: List[BaseTool], llm=None, secret_retriever: Optional[ISecretRetriever] = None):
        """Initialize App Insights agent with tools and LLM

        Args:
            tools: List of tools that this agent can use (required)
            llm: The language model instance for agent reasoning and communication
            secret_retriever: Optional ISecretRetriever for dependency injection (used by factory functions)
        """
        super().__init__(tools)
        self.llm = llm
        self.agent = None
        self.secret_retriever = secret_retriever
        if llm:
            self._initialize_agent()
    
    def _build_dynamic_system_prompt(self) -> str:
        """Build system prompt based on available tools with comprehensive information"""

        # Use the constant from system_prompt.py
        base_prompt = APP_INSIGHTS_SYSTEM_PROMPT

        # Extract comprehensive tool information using full docstrings
        tool_descriptions = []
        for tool_name, tool in self.tools.items():
            # Get the full docstring from the original function
            full_docstring = ""
            if hasattr(tool, 'func') and hasattr(getattr(tool, 'func', None), '__doc__'):
                func = getattr(tool, 'func')
                if func and func.__doc__:
                    full_docstring = func.__doc__
            elif tool.description:
                full_docstring = tool.description
            
            # Build detailed tool description with just the complete docstring
            tool_desc = f"""
## {tool.name} :
{full_docstring}"""
            
            tool_descriptions.append(tool_desc)

        tools_section = '\n\n**# Available Tools:**\n' + '\n'.join(tool_descriptions)

        footer = "\n\n**Instructions:** Always provide detailed analysis with evidence from the telemetry data. Use the complete docstring information above to understand when and how to use each tool effectively."

        return base_prompt + tools_section + footer

    def _initialize_agent(self):
        """Initialize the LangGraph ReAct agent"""
        if self.llm is None:
            raise ValueError("LLM is not provided. Cannot initialize the agent.")
        
        system_prompt = self._build_dynamic_system_prompt()
        
        self.agent = create_react_agent(
            self.llm,
            list(self.tools.values()),
            prompt=system_prompt
        )

    async def execute_capability(self, instruction: str) -> Any:
        """Execute a capability using natural language instruction

        Args:
            instruction: Natural language instruction for what the agent should do

        Returns:
            The result from the agent execution
        """
        if not self.agent:
            raise ValueError("Agent not initialized. LLM is required for capability execution.")

        # Create message format expected by LangGraph
        messages = [{"role": "user", "content": instruction}]

        # Invoke the agent
        result = await self.agent.ainvoke({"messages": messages})

        return result

    @classmethod
    async def initialize(cls, tools: List[BaseTool], llm, secret_retriever: Optional[ISecretRetriever] = None):
        """Create and initialize an AppInsightsAgent instance.

        Factory method that creates a properly configured AppInsightsAgent.

        Args:
            tools: List of tools that this agent can use (required)
            llm: The language model instance for agent reasoning and communication.
            secret_retriever: Optional ISecretRetriever for dependency injection

        Returns:
            AppInsightsAgent: A fully initialized AppInsightsAgent instance.

        Raises:
            Exception: If agent creation fails.
        """
        instance = cls(tools, llm, secret_retriever)
        return instance

    @property
    def service_name(self) -> str:
        # Must be a safe identifier (no spaces or special chars) for supervisor compatibility
        return "app_insights"


async def main():
    """Test the App Insights agent with dynamic tool injection"""
    import asyncio
    import os
    from dotenv import load_dotenv
    from phoenix.otel import register
    from fx_ai_reusables.tools.app_insights_tools import (
        create_get_app_insights_operation_id_using_url_tool,
        create_get_app_insights_logs_using_operation_id_tool
    )
    from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
    from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
    from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
    from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
    from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever

    # Load environment variables
    load_dotenv()

    # Setup Phoenix tracing
    try:
        from phoenix_setup import setup_phoenix_tracing
        setup_phoenix_tracing("app-insights-agent")
    except Exception as e:
        pass

    try:
        # Initialize authentication and LLM
        config_map_retriever = EnvironmentVariablesConfigMapRetriever()
        secrets_retriever = EnvironmentVariableSecretRetriever()
        environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)
        hcp_authenticator = HcpAuthenticator(environment_reader)

        llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)

        llm = await llm_creator.create_llm()

        # Create tools using factory functions with secret retriever
        tools = [
            create_get_app_insights_operation_id_using_url_tool(secrets_retriever),
            create_get_app_insights_logs_using_operation_id_tool(secrets_retriever)
        ]

        # Create agent with injected tools
        agent = AppInsightsAgent(tools=tools, llm=llm, secret_retriever=secrets_retriever)

        # Test dynamic system prompt generation
        system_prompt = agent._build_dynamic_system_prompt()

        # Test tool availability
        available_tools = agent.get_available_tools()

        # Test tool retrieval
        for tool_name in agent.get_available_tools():
            tool = agent.get_tool_by_name(tool_name)

        # Test actual capability execution with operation ID
        try:
            instruction = "Get logs for operation ID 1c2504930429469d8955c04957f930e7 with time frame from june to august 2025"
            result = await agent.execute_capability(instruction)
            if 'messages' in result:
                last_message = result['messages'][-1]
                if hasattr(last_message, 'content'):
                    pass
        except Exception as e:
            pass

    except Exception as e:
        return 1

    return 0


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)
