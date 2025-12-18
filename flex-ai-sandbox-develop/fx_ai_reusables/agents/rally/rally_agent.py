import sys
import os

import re
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from fx_ai_reusables.agents.interfaces.base_agent import IAgent
from fx_ai_reusables.agents.rally.system_prompt import RALLY_SYSTEM_PROMPT


class RallyAgent(IAgent):
    """Agent responsible for monitoring and analyzing Rally project management data.

    This agent interacts with Rally APIs and tools to retrieve project information,
    user stories, defects, sprint metrics, and other artifacts for comprehensive
    project tracking, reporting, and agile workflow analysis.

    Attributes:
        agent: The LangGraph ReAct agent configured with Rally project management tools.
    """

    def __init__(self, tools: List[BaseTool], llm=None):
        """Initialize Rally agent with tools and LLM

        Args:
            tools: List of tools that this agent can use (required)
            llm: The language model instance for agent reasoning and communication
        """
        super().__init__(tools)
        self.llm = llm
        self.agent = None
        if llm:
            self._initialize_agent()

    def _extract_tool_info(self, tool: BaseTool) -> Dict[str, Any]:
        """Extract comprehensive information from a tool"""
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": self._get_tool_parameters(tool),
            "when_to_use": self._extract_usage_context(tool)
        }

    def _get_tool_parameters(self, tool: BaseTool) -> List[Dict]:
        """Extract parameter information from tool schema"""
        if tool.args_schema:
            schema = tool.args_schema.model_json_schema()
            return [
                {
                    "name": param_name,
                    "type": param_info.get("type"),
                    "description": param_info.get("description"),
                    "required": param_name in schema.get("required", [])
                }
                for param_name, param_info in schema.get("properties", {}).items()
            ]
        return []

    def _extract_usage_context(self, tool: BaseTool) -> str:
        """Parse docstring to extract 'when to use' information"""
        docstring = tool.description or ""

        # Look for specific sections in docstring
        usage_patterns = [
            r"When to use:(.+?)(?=\n\n|\n[A-Z]|$)",
            r"Use this tool when:(.+?)(?=\n\n|\n[A-Z]|$)",
            r"Best for:(.+?)(?=\n\n|\n[A-Z]|$)"
        ]

        for pattern in usage_patterns:
            match = re.search(pattern, docstring, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        # Fallback: extract first sentence of description
        return docstring.split('.')[0] if docstring else "General purpose Rally project management tool"
    
    def _build_dynamic_system_prompt(self) -> str:
        """Build system prompt based on available tools"""

        # Use the constant from system_prompt.py
        base_prompt = RALLY_SYSTEM_PROMPT

        # Extract tool information
        tool_descriptions = []
        for tool_name, tool in self.tools.items():
            tool_info = self._extract_tool_info(tool)

            # Format parameters
            params = [f"{p['name']} ({p['type']})" for p in tool_info['parameters']]
            params_str = ", ".join(params) if params else "No parameters"

            tool_desc = f"""
            - {tool_info['name']}: {tool_info['description']}
              Parameters: {params_str}
              When to use: {tool_info['when_to_use']}"""
            tool_descriptions.append(tool_desc)

        tools_section = '\n'.join(tool_descriptions)

        footer = "\nAlways provide detailed Rally project analysis with specific artifacts, sprint metrics, and actionable recommendations."

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
    async def initialize(cls, tools: List[BaseTool], llm):
        """Create and initialize a Rally instance.

        Factory method that creates a properly configured Rally instance.

        Args:
            tools: List of tools that this agent can use (required)
            llm: The language model instance for agent reasoning and communication.

        Returns:
            RallyAgent: A fully initialized RallyAgent instance.

        Raises:
            Exception: If agent creation fails.
        """
        instance = cls(tools, llm)
        return instance

    @property
    def service_name(self) -> str:
        # Must be a safe identifier (no spaces or special chars) for supervisor compatibility
        return "rally"


async def main():
    """Test the Rally agent with dynamic tool injection"""
    import asyncio
    import os
    from dotenv import load_dotenv
    from phoenix.otel import register
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
        setup_phoenix_tracing("rally-agent")
    except Exception as e:
        print(f"⚠️  Phoenix tracing setup failed: {e}")

    print("🧪 Testing Rally Agent")

    try:
        config_map_retriever = EnvironmentVariablesConfigMapRetriever()
        secrets_retriever = EnvironmentVariableSecretRetriever()
        environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)

        # Initialize authentication and LLM
        print("🔐 Setting up authentication...")
        hcp_authenticator = HcpAuthenticator(environment_reader)

        print("🤖 Creating LLM...")
        llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
        llm = await llm_creator.create_llm()

        # Import the available Rally tools
        from fx_ai_reusables.tools.rally.rally_tools import create_fetch_rally_artifact_details_tool
        from fx_ai_reusables.environment_loading.concretes.rally_config_reader import RallyConfigReader

        # Create Rally config reader for tools
        rally_config_reader = RallyConfigReader(config_map_retriever, secrets_retriever)

        # Create Rally tools using factory function
        print("🔧 Creating Rally agent with tool...")
        tool = create_fetch_rally_artifact_details_tool(rally_config_reader)
        tools = [tool]

        # Create agent with injected tool
        print("🔧 Creating Rally agent with tool...")
        agent = RallyAgent(tools=tools, llm=llm)

        # Test dynamic system prompt generation
        print("\n📝 Generated System Prompt:")
        print("=" * 60)
        system_prompt = agent._build_dynamic_system_prompt()
        print(system_prompt)
        print("=" * 60)

        # Test tool availability
        print(f"\n Available tools: {[tool.name for tool in tools]}")

        # Test actual capability execution
        print(f"\n Testing capability execution with natural language instruction")
        try:
            # Test fetch_rally_artifact_details tool
            instruction = "Fetch details for artifact with ID US9198881 in project Team FHIDGET"
            result = await agent.execute_capability(instruction)
            print(f" Rally artifact details retrieved successfully!")
            print(f"Result type: {type(result)}")
            print("\n" + "="*80)
            print("FULL ARTIFACT DETAILS RESPONSE:")
            print("="*80)
            if 'messages' in result:
                last_message = result['messages'][-1]
                if hasattr(last_message, 'content'):
                    print(f"Agent response:\n{last_message.content}")
            print("="*80)

        except Exception as e:
            print(f"  Capability execution failed: {str(e)}")
            import traceback
            print(f"Full error traceback:\n{traceback.format_exc()}")

        print("\n Rally agent test completed successfully!")

    except Exception as e:
        print(f" Test failed: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)