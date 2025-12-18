from typing import Dict, Any
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from ..interfaces.base_agent import IAgent
from .system_prompt import SPLUNK_SYSTEM_PROMPT
from ...tools.splunk_tools import (
    search_splunk_logs,
    get_splunk_job_status,
    get_splunk_results,
    cancel_splunk_job
)


class SplunkAgent(IAgent):
    """Agent responsible for searching and analyzing log data from Splunk.
    
    This agent handles all interactions with Splunk REST API to execute
    searches, monitor job status, and retrieve log analysis results needed for
    comprehensive incident troubleshooting.
    
    Attributes:
        splunk_agent: The LangGraph react agent configured with Splunk tools.
    """
    
    def __init__(self, llm=None):
        """Initialize the Splunk agent with required components.
        
        Args:
            llm: The language model instance for agent reasoning and communication.
        """
        tools = [
            search_splunk_logs,
            get_splunk_job_status,
            get_splunk_results,
            cancel_splunk_job
        ]
        super().__init__(tools)
        
        if llm:
            self.splunk_agent = create_react_agent(
                name="Splunk_Agent",
                model=llm,
                tools=tools,
                prompt=SystemMessage(self._get_splunk_prompt()),
            )
    
    def _get_splunk_prompt(self) -> str:
        """Get the system prompt for the Splunk agent"""
        return SPLUNK_SYSTEM_PROMPT
    
    async def execute_capability(self, capability: str, params: Dict[str, Any]) -> Any:
        """Execute a Splunk capability using appropriate tools"""
        if capability in self.tools:
            tool = self.tools[capability]
            return await tool.ainvoke(params)
        else:
            raise ValueError(f"Capability {capability} not supported by Splunk agent")
    
    @classmethod
    async def initialize(cls, llm):
        """Create and initialize a SplunkAgent instance.
        
        Factory method that creates a properly configured SplunkAgent.
        
        Args:
            llm: The language model instance for agent reasoning and communication.
        
        Returns:
            SplunkAgent: A fully initialized SplunkAgent instance.
            
        Raises:
            Exception: If agent creation fails.
        """
        return cls(llm)
    
    @property
    def service_name(self) -> str:
        return "splunk"
