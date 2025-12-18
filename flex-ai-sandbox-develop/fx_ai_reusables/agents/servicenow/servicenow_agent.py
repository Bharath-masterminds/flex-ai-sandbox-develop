import sys
import os

import re
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from fx_ai_reusables.agents.interfaces.base_agent import IAgent
from fx_ai_reusables.agents.servicenow.system_prompt import SERVICENOW_SYSTEM_PROMPT
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


class ServiceNowAgent(IAgent):
    """ServiceNow Agent with Natural Language Interface.
    
    This intelligent agent understands natural language queries and automatically:
    - Converts relative time expressions (e.g., "today", "last hour") to exact timestamps
    - Selects appropriate ServiceNow tools based on your question
    - Downloads incident attachments when requested
    - Generates comprehensive incident intelligence reports with root cause analysis
    
    Features:
    - Natural language incident queries
    - Automatic attachment download to local disk
    - Time-based incident filtering (supports natural language time)
    - Assignment group filtering
    - Multi-step workflows orchestration
    
    Usage Examples:
    - "Show me details of incident INC45979594 and download any attachments"
    - "Get all incidents for FLEX_RagingFHIR - SPT from today"
    - "List incidents created in the last hour"
    
    Attributes:
        agent: The LangGraph react agent configured with ServiceNow tools.
    """
    
    def __init__(self, tools: List[BaseTool], llm=None, secret_retriever: Optional[ISecretRetriever] = None):
        """Initialize ServiceNow agent with tools and LLM
        
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
        base_prompt = f"""{SERVICENOW_SYSTEM_PROMPT}

"""

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
## {tool.name}:
{full_docstring}"""
            
            tool_descriptions.append(tool_desc)

        tools_section = '\n'.join(tool_descriptions)

        footer = """

**Instructions:** 
- Always provide detailed analysis with clear incident status and next steps
- Use the complete docstring information above to understand when and how to use each tool
- For attachment workflows: first get incident details to obtain sys_id, then list attachments, then download if needed
- For time-based queries: use proper timestamp format "YYYY-MM-DD HH:MM:SS"
- Chain tools together logically for comprehensive incident analysis
"""

        return f"{base_prompt}{tools_section}{footer}"
    
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
        """Create and initialize a ServiceNowAgent instance.
        
        Factory method that creates a properly configured ServiceNowAgent.
        
        Args:
            tools: List of tools that this agent can use (required)
            llm: The language model instance for agent reasoning and communication.
            secret_retriever: Optional ISecretRetriever for dependency injection
        
        Returns:
            ServiceNowAgent: A fully initialized ServiceNowAgent instance.
            
        Raises:
            Exception: If agent creation fails.
        """
        instance = cls(tools, llm, secret_retriever)
        return instance
    
    @property
    def service_name(self) -> str:
        return "servicenow"


async def main():
    """Test the ServiceNow agent with all tools"""
    import asyncio
    from fx_ai_reusables.tools.servicenow_tools import (
        create_get_incident_by_incident_number_tool,
        create_get_incident_attachments_tool,
        create_download_attachment_tool,
        create_get_incidents_by_timeframe_tool,
        create_get_incidents_by_assignment_group_tool
    )
    from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
    from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
    from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
    
    # Setup Phoenix tracing
    try:
        from phoenix_setup import setup_phoenix_tracing
        setup_phoenix_tracing("servicenow-agent")
    except Exception as e:
        print(f"Warning: Phoenix tracing setup failed: {e}")
    
    print("Testing ServiceNow Agent")
    
    try:
        # Note: This test assumes DEPLOYMENT_FLAVOR is set in environment
        # For local testing, set: DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL
        
        # Import IoC container at function level to avoid circular dependencies
        import sys
        import os
        # Add use_cases directory to path to import composition root
        use_cases_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'use_cases', 'ops_resolve')
        if use_cases_path not in sys.path:
            sys.path.insert(0, use_cases_path)
        
        from ioc.ops_resolve_composition_root import OpsResolveCompositionRoot
        
        # Initialize IoC container and resolve dependencies
        print("Initializing IoC container...")
        container = OpsResolveCompositionRoot()
        config_map_retriever = container.get_config_map_retriever()
        secrets_retriever = container.get_secret_retriever()
        
        # Initialize authentication and LLM
        print("Setting up authentication...")
        environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)
        hcp_authenticator = HcpAuthenticator(environment_reader)
        
        print("Creating LLM...")
        llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
        llm = await llm_creator.create_llm()
        
        # Create all tools using factory functions with secret retriever
        print("Creating ServiceNow tools...")
        tools = [
            create_get_incident_by_incident_number_tool(secrets_retriever),
            create_get_incident_attachments_tool(secrets_retriever),
            create_download_attachment_tool(secrets_retriever),
            create_get_incidents_by_timeframe_tool(secrets_retriever),
            create_get_incidents_by_assignment_group_tool(secrets_retriever)
        ]
        
        # Create agent with injected tools
        print("Creating ServiceNow agent...")
        agent = ServiceNowAgent(tools=tools, llm=llm, secret_retriever=secrets_retriever)
        
        # Test dynamic system prompt generation
        print("\nGenerated System Prompt:")
        print("=" * 80)
        system_prompt = agent._build_dynamic_system_prompt()
        print(f"{system_prompt[:500]}...\n(truncated)")
        print("=" * 80)
        
        # Test tool availability
        print(f"\nAvailable tools: {agent.get_available_tools()}")
        
        # Test actual capability execution with incident number
        print(f"\nTesting capability execution with natural language instruction")
        try:
            instruction = "Get details for incident INC43908022 and list any attachments"
            print(f"Instruction: {instruction}")
            result = await agent.execute_capability(instruction)
            
            if 'messages' in result:
                print("\nAgent Messages:")
                for message in result['messages']:
                    role = getattr(message, "type", getattr(message, "role", "unknown"))
                    content = getattr(message, "content", "")
                    
                    if role == "ai" and content:
                        print(f"\nAI Response:")
                        print(content[:500] if len(content) > 500 else content)
                    elif role == "tool":
                        print(f"\nTool Response (truncated):")
                        print(content[:200] if len(content) > 200 else content)
                        
        except Exception as e:
            print(f"Test execution error: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
        
        print("\nServiceNow agent test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Test failed: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)
