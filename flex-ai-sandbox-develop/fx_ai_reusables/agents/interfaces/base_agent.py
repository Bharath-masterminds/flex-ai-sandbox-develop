from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool


class IAgent(ABC):
    """Base interface for agents that manage tool collections"""
    
    def __init__(self, tools: List[BaseTool]):
        """Initialize agent with list of decorated tool functions
        
        Args:
            tools: List of tools that this agent can use (required)
        """
        if not tools:
            raise ValueError(f"Agent {self.__class__.__name__} requires at least one tool")
        self.tools = {tool.name: tool for tool in tools}
        # Initialize agent attribute - will be set by _initialize_agent()
        self.agent: Optional[Any] = None
    
    @abstractmethod
    async def execute_capability(self, instruction: str) -> Any:
        """Execute a capability using appropriate tools
        
        Args:
            instruction: Natural language instruction for what the agent should do
        """
        pass
    
    @abstractmethod
    def _initialize_agent(self):
        """Initialize the agent with LLM and tools
        
        This method should set up the LangGraph agent or other execution framework
        needed for the agent to process instructions and use tools.
        Sets the self.agent attribute with the compiled agent.
        """
        pass
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Service this agent manages"""
        pass
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())
    
    def get_tool_by_name(self, tool_name: str) -> BaseTool:
        """Get a specific tool by name"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found in {self.service_name} agent")
        return self.tools[tool_name]
