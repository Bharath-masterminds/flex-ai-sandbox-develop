from abc import ABC, abstractmethod
from typing import List, Dict, Any
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from ...agents.interfaces.base_agent import IAgent


class ISupervisor(ABC):
    """Base interface for supervisors that orchestrate agents"""
    
    def __init__(self, agents: List[IAgent], llm: BaseChatModel):
        """Initialize supervisor with list of agents and LLM"""
        self.agents = {agent.service_name: agent for agent in agents}
        self.llm = llm
        
        # Collect all tools from all agents
        all_tools = []
        for agent in agents:
            all_tools.extend(agent.tools.values())
        
        # Create LangGraph agent with all tools
        self.graph_agent = create_react_agent(
            model=llm,
            tools=all_tools,
            prompt=self._get_system_prompt()
        )
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LangGraph agent"""
        pass
    
    @abstractmethod
    async def execute_workflow(self, workflow_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the main workflow using available agents"""
        pass
    
    def stream_workflow(self, workflow_params: Dict[str, Any]):
        """
        Stream the workflow execution for real-time feedback.
        Default implementation can be overridden for custom streaming behavior.
        
        Args:
            workflow_params: Parameters for the workflow execution
            
        Yields:
            Chunks of the workflow execution as they're generated
        """
        # Default implementation - can be overridden
        if hasattr(self.graph_agent, 'stream'):
            for chunk in self.graph_agent.stream(workflow_params):
                yield chunk
        else:
            # Fallback: convert async execution to single yield
            import asyncio
            result = asyncio.run(self.execute_workflow(workflow_params))
            yield result
    
    def get_available_agents(self) -> List[str]:
        """Get list of available agent names"""
        return list(self.agents.keys())
    
    def get_agent_by_name(self, agent_name: str) -> IAgent:
        """Get a specific agent by name"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not found")
        return self.agents[agent_name]
    
    @property
    def agent_list(self) -> List[IAgent]:
        """Get the list of all agents managed by this supervisor"""
        return list(self.agents.values())
