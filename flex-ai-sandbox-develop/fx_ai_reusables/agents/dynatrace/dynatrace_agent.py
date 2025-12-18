import sys
import os

import re
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from fx_ai_reusables.agents.interfaces.base_agent import IAgent
from fx_ai_reusables.agents.dynatrace.system_prompt import DYNATRACE_SYSTEM_PROMPT
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


class DynatraceAgent(IAgent):
    """Agent responsible for monitoring and analyzing observability data via Dynatrace.

    This agent handles interactions with Dynatrace APIs to retrieve service health data,
    infrastructure metrics, problem information, security vulnerabilities, and logs.
    It leverages Dynatrace Davis AI for automatic root cause analysis and Smartscape
    for dependency visualization.

    Attributes:
        agent: The LangGraph react agent configured with Dynatrace monitoring tools.
    """

    def __init__(self, tools: List[BaseTool], llm=None, secret_retriever: Optional[ISecretRetriever] = None):
        """Initialize Dynatrace agent with tools and LLM

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
        base_prompt = DYNATRACE_SYSTEM_PROMPT

        # Extract comprehensive tool information using full docstrings
        tool_descriptions = []
        for tool_name, tool in self.tools.items():
            # Get the full docstring from the original function
            full_docstring = ""
            if hasattr(tool, "func") and hasattr(getattr(tool, "func", None), "__doc__"):
                func = getattr(tool, "func")
                if func and func.__doc__:
                    full_docstring = func.__doc__
            elif tool.description:
                full_docstring = tool.description

            # Build detailed tool description with just the complete docstring
            tool_desc = f"""
## {tool.name} :
{full_docstring}"""

            tool_descriptions.append(tool_desc)

        tools_section = "\n\n**# Available Tools:**\n" + "\n".join(tool_descriptions)

        footer = "\n\n**Instructions:** Always provide detailed analysis with evidence from Dynatrace telemetry data. Use the complete docstring information above to understand when and how to use each tool effectively. Leverage Davis AI insights and Smartscape topology for comprehensive analysis."

        return base_prompt + tools_section + footer

    def _initialize_agent(self):
        """Initialize the LangGraph ReAct agent"""
        if self.llm is None:
            raise ValueError("LLM is not provided. Cannot initialize the agent.")

        system_prompt = self._build_dynamic_system_prompt()

        self.agent = create_react_agent(self.llm, list(self.tools.values()), prompt=system_prompt)

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
        """Create and initialize a DynatraceAgent instance.

        Factory method that creates a properly configured DynatraceAgent.

        Args:
            tools: List of tools that this agent can use (required)
            llm: The language model instance for agent reasoning and communication.
            secret_retriever: Optional ISecretRetriever for dependency injection

        Returns:
            DynatraceAgent: A fully initialized DynatraceAgent instance.

        Raises:
            Exception: If agent creation fails.
        """
        instance = cls(tools, llm, secret_retriever)
        return instance

    @property
    def service_name(self) -> str:
        # Must be a safe identifier (no spaces or special chars) for supervisor compatibility
        return "dynatrace"


async def main():
    """Test the Dynatrace agent with dynamic tool injection"""
    import asyncio
    import os
    from dotenv import load_dotenv
    from phoenix.otel import register
    from fx_ai_reusables.tools.dynatrace_tools import (
        create_list_dynatrace_services_tool,
        create_get_dynatrace_service_dependencies_tool,
        create_find_service_errors_and_traces_tool,
        create_get_service_metrics_tool,
        create_get_active_problems_tool,
        create_get_problem_details_tool,
        create_get_entity_info_tool,
        create_search_logs_tool,
        create_push_deployment_event_tool,
        create_get_synthetic_test_results_tool,
        create_get_security_issues_tool,
        create_get_alerting_profiles_tool,
        create_get_topology_map_tool,
    )
    from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import (
        AzureLlmConfigAndSecretsHolderWrapperReader,
    )
    from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
    from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
    from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import (
        EnvironmentVariablesConfigMapRetriever,
    )
    from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import (
        EnvironmentVariableSecretRetriever,
    )

    # Load environment variables
    load_dotenv()

    # Setup Phoenix tracing
    try:
        from phoenix_setup import setup_phoenix_tracing

        setup_phoenix_tracing("dynatrace-agent")
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

        # Create tools list - all 13 Dynatrace tools using factory functions
        tools = [
            create_list_dynatrace_services_tool(secrets_retriever),
            create_get_dynatrace_service_dependencies_tool(secrets_retriever),
            create_find_service_errors_and_traces_tool(secrets_retriever),
            create_get_service_metrics_tool(secrets_retriever),
            create_get_active_problems_tool(secrets_retriever),
            create_get_problem_details_tool(secrets_retriever),
            create_get_entity_info_tool(secrets_retriever),
            create_search_logs_tool(secrets_retriever),
            create_push_deployment_event_tool(secrets_retriever),
            create_get_synthetic_test_results_tool(secrets_retriever),
            create_get_security_issues_tool(secrets_retriever),
            create_get_alerting_profiles_tool(secrets_retriever),
            create_get_topology_map_tool(secrets_retriever),
        ]

        # Create agent with injected tools
        agent = DynatraceAgent(tools=tools, llm=llm, secret_retriever=secrets_retriever)

        # Test dynamic system prompt generation
        system_prompt = agent._build_dynamic_system_prompt()

        # Test tool availability
        available_tools = agent.get_available_tools()

        # Test tool retrieval
        for tool_name in agent.get_available_tools():
            tool = agent.get_tool_by_name(tool_name)

        # Test actual capability execution
        try:
            instruction = 'Search logs for service "user-management" containing errors, failures, login, or auth issues from 2025-11-06T17:28:33Z to 2025-11-11T17:28:04Z. Return up to 100 results.'
            result = await agent.execute_capability(instruction)
            if "messages" in result:
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
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
