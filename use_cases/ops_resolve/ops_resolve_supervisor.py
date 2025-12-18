"""
OpsResolve Supervisor for incident analysis using langgraph_supervisor.
Dynamically coordinates agents based on injected capabilities.
"""

from typing import List, Dict, Any, Optional
from langgraph_supervisor import create_supervisor
from fx_ai_reusables.agents.interfaces.base_agent import IAgent
from fx_ai_reusables.supervisors.interfaces.base_supervisor import ISupervisor
import os
import asyncio
from phoenix.otel import register
from use_cases.ops_resolve.system_prompt import build_supervisor_prompt


class OpsResolveSupervisor(ISupervisor):
    """
    Supervisor that orchestrates incident analysis by coordinating multiple agents.
    Uses dynamic prompt generation based on injected agent capabilities.
    """
    
    def __init__(self, llm, agents: List[IAgent]):
        """
        Initialize the OpsResolve supervisor with LLM and agents.
        
        Args:
            llm: Language model for supervisor decision making
            agents: List of IAgent instances to coordinate
        """
        # Call parent constructor first - this sets up self.agents dict and self.llm
        super().__init__(agents, llm)
        
        # Build dynamic system prompt from agent capabilities
        system_prompt = self._get_system_prompt()
        print("\n📝 Generated System Prompt for Supervisor:")

        # Extract the compiled LangGraph agents
        agent_apps = []
        for agent in self.agent_list:
            # Ensure agent is initialized
            if hasattr(agent, '_initialize_agent') and not hasattr(agent, 'agent'):
                agent._initialize_agent()
            
            # Get the compiled agent
            if hasattr(agent, 'agent') and agent.agent is not None:
                # Set the agent name using the service_name property
                agent_name = agent.service_name if hasattr(agent, 'service_name') else agent.__class__.__name__
                print(f"\nAgent Name: {agent_name}")
                # Store the agent with its name for supervisor
                agent.agent.name = agent_name
                agent_apps.append(agent.agent)
        
        if not agent_apps:
            raise ValueError("No valid agents found. Ensure agents are properly initialized.")        

        # Create the supervisor
        # Phoenix tracing is set up at the module level in main.py and test_ops_resolve_supervisor.py
        supervisor = create_supervisor(
            agent_apps,
            model=llm,
            supervisor_name="ops_resolve_supervisor",
            prompt=system_prompt,
            add_handoff_back_messages=True,
            output_mode="full_history"
        )
        
        # Phoenix tracing is already set up at the module level in main.py and test_ops_resolve_supervisor.py
        # No need to register again here as it's already handled by setup_phoenix_tracing("ops-resolve-system")
        
        # Compile the supervisor
        self.app = supervisor.compile()
    
    async def execute_workflow(self, workflow_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the main workflow using available agents (required by ISupervisor).
        
        Args:
            workflow_params: Parameters for workflow execution, should contain 'query' key
            
        Returns:
            dict: Complete analysis results
        """
        query = workflow_params.get('query', workflow_params.get('messages', [{'role': 'user', 'content': ''}])[-1].get('content', ''))
        return await self.run(query)
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the LangGraph agent (required by ISupervisor).
        
        Returns:
            str: System prompt describing the supervisor's role and available agents
        """
        return build_supervisor_prompt(self.agent_list)
    
    async def run(self, query: str) -> Dict[str, Any]:
        """
        Execute incident analysis for the given query.
        
        Args:
            query: The incident analysis request (e.g., "Analyze incident INC43951297")
            
        Returns:
            dict: Complete analysis results
        """
        # Phoenix tracing is handled at the module level
        result = await self.app.ainvoke(
            {"messages": [{"role": "user", "content": query}]}
        )
        return result
    
    def stream(self, query: str):
        """
        Stream the incident analysis process for real-time feedback.
        
        Args:
            query: The incident analysis request
            
        Yields:
            Chunks of the analysis as they're generated
        """
        # Phoenix tracing is handled at the module level
        for chunk in self.app.stream(
            {"messages": [{"role": "user", "content": query}]}
        ):
            yield chunk
    
    async def run_incident_agent(self, query: str):
        """
        Stream the incident analysis process and print results as they become available.

        This method processes the incident query through the agent workflow and
        displays the results incrementally as they are generated, providing
        real-time feedback on the analysis progress.

        Args:
            query (str): The incident analysis request, typically in the format
                         "Please find root cause for {incident_number}"

        Returns:
            None: Results are printed to the console as they become available
        """
        from langchain_core.messages import convert_to_messages

        def pretty_print_message(message, indent=False):
            """Print a formatted message with optional indentation.
            
            Formats and displays agent messages in a readable format with consistent
            styling and optional indentation for nested content.
            
            Args:
                message: The message object to format and print.
                indent (bool): Whether to apply indentation to the output.
                
            Returns:
                None: Prints directly to stdout.
            """
            pretty_message = message.pretty_repr(html=True)
            if not indent:
                print(pretty_message)
                return

            indented = "\n".join("\t" + c for c in pretty_message.split("\n"))
            print(indented)

        def pretty_print_messages(update, last_message=False):
            """Print formatted agent workflow updates with proper styling.
            
            Processes and displays agent workflow updates including node changes,
            messages, and final results with consistent formatting.
            
            Args:
                update: The workflow update containing node and message information.
                last_message (bool): Whether this is the final message in the workflow.
                
            Returns:
                None: Prints directly to stdout with formatted output.
            """
            is_subgraph = False
            if isinstance(update, tuple):
                ns, update = update
                # skip parent graph updates in the printouts
                if len(ns) == 0:
                    return

                graph_id = ns[-1].split(":")[0]
                print(f"Update from subgraph {graph_id}:")
                print("\n")
                is_subgraph = True

            for node_name, node_update in update.items():
                update_label = f"Update from node {node_name}:"
                if is_subgraph:
                    update_label = "\t" + update_label

                print(update_label)
                print("\n")

                messages = convert_to_messages(node_update["messages"])
                if last_message:
                    messages = messages[-1:]

                for m in messages:
                    pretty_print_message(m, indent=is_subgraph)
                print("\n")
        
        # Use a timeout to prevent the agent from getting stuck
        try:
            # Create a generator for streaming results
            stream_generator = self.app.stream({"messages": [{"role": "user", "content": query}]})
            
            # Set a maximum execution time (in seconds)
            MAX_EXECUTION_TIME = 300  # 5 minutes
            start_time = asyncio.get_event_loop().time()
            
            # Process each chunk as it arrives with timeout protection
            for chunk in stream_generator:
                # Check if we've exceeded the maximum execution time
                current_time = asyncio.get_event_loop().time()
                if current_time - start_time > MAX_EXECUTION_TIME:
                    print(f"\n⚠️ Analysis exceeded maximum execution time of {MAX_EXECUTION_TIME} seconds. Stopping.")
                    break
                    
                pretty_print_messages(chunk, last_message=True)
                
            print("\n✅ Analysis completed successfully")
            
        except asyncio.TimeoutError:
            print("\n⚠️ Analysis timed out. The operation took too long to complete.")
        except Exception as e:
            print(f"\n❌ Error during analysis: {str(e)}")
            raise
    

    
    @classmethod
    async def initialize(cls, llm, agents: List[IAgent]):
        """
        Factory method to create and initialize an OpsResolveSupervisor.
        
        Args:
            llm: Language model instance
            agents: List of IAgent instances
            
        Returns:
            OpsResolveSupervisor: Initialized supervisor instance
        """
        return cls(llm, agents)
