#!/usr/bin/env python3
"""
`ServiceNow Agent - Natural Language Interface Test Suite

This test demonstrates an intelligent ServiceNow agent that understands natural language queries.

What it does:
- Understands plain English questions about ServiceNow incidents
- Automatically converts relative time ("today", "last hour") to exact timestamps
- Intelligently selects and orchestrates the right ServiceNow tools
- Downloads incident attachments to local disk when requested
- Generates comprehensive incident intelligence reports with root cause analysis

Natural Language Usage:
    python test_servicenow.py "Show me details of incident INC45979594"
    python test_servicenow.py "Get all incidents for FLEX_RagingFHIR - SPT from today"
    python test_servicenow.py "Download attachments for INC45979594"
    python test_servicenow.py "List incidents created in the last hour"

Features:
- Natural language query processing with LLM
- Automatic time conversion (relative → absolute timestamps)
- Smart tool selection and multi-step workflows
- Attachment download with progress tracking
- Structured incident analysis with root cause identification

Files are saved to: ./downloads/
"""

# Add project root to Python path
import sys
import os
from pathlib import Path

# Get the project root (2 levels up from this file)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pprint import pprint
import asyncio
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, InternalServerError, APITimeoutError

# Optional Phoenix tracing
try:
    from phoenix_setup import setup_phoenix_tracing
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    def setup_phoenix_tracing(name):
        """Dummy function when Phoenix is not available"""
        pass

from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.environment_fetcher.concrete_dotenv.environment_fetcher import EnvironmentFetcher

# ServiceNow agent import
from fx_ai_reusables.agents.servicenow.servicenow_agent import ServiceNowAgent

# ServiceNow tools imports
from fx_ai_reusables.tools.servicenow_tools import (
    create_get_incident_by_incident_number_tool,
    create_get_incident_attachments_tool,
    create_download_attachment_tool,
    create_get_incidents_by_timeframe_tool,
    create_get_incidents_by_assignment_group_tool
)


def _print_result(result: Dict[str, Any]) -> None:
    """Print the analysis result in a formatted way."""
    print("\n" + "="*80)
    print("SERVICENOW ANALYSIS COMPLETE")
    print("="*80)

    # Extract and display key information from messages (supports LangChain message objects)
    if "messages" in result:
        for message in result["messages"]:
            role = getattr(message, "type", getattr(message, "role", "unknown"))
            content = getattr(message, "content", "")
            name = getattr(message, "name", None)

            if role == "ai" and content:
                print(f"\nAGENT Response:")
                print(content)
            elif role == "tool":
                tool_name = name or 'tool'
                print(f"\nTOOL '{tool_name}' Output:")
                # Truncate long tool outputs for readability
                if len(content) > 1000:
                    print(content[:1000] + "\n... (truncated)")
                else:
                    print(content)
            elif role == "human" and content:
                print(f"\nUSER:")
                print(content)
    else:
        print(result)


async def main_natural_language(query: str):
    """CLI entry point for natural language queries"""
    print(f"ServiceNow Natural Language Query")
    print(f"Query: {query}")
    print("="*80)
    
    # Load environment variables from .env file FIRST
    env_fetcher = EnvironmentFetcher()
    env_fetcher.load_environment()
    
    # Setup tracing
    setup_phoenix_tracing("ops-resolve-servicenow-natural")

    # Initialize environment retrievers directly
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()

    # Initialize auth and LLM
    environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)
    hcp_authenticator = HcpAuthenticator(environment_reader)
    llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
    llm = await llm_creator.create_llm()

    # Create all tools
    tools = [
        create_get_incident_by_incident_number_tool(secrets_retriever),
        create_get_incident_attachments_tool(secrets_retriever),
        create_download_attachment_tool(secrets_retriever),
        create_get_incidents_by_timeframe_tool(secrets_retriever),
        create_get_incidents_by_assignment_group_tool(secrets_retriever)
    ]

    # Build ServiceNow agent
    servicenow_agent = ServiceNowAgent(tools, llm, secrets_retriever)

    # Define the query execution with retry logic using tenacity
    @retry(
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APITimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=10, max=60),
        before_sleep=lambda retry_state: print(
            f"\n{'Rate limit' if isinstance(retry_state.outcome.exception(), RateLimitError) else 'Timeout/Server error'} encountered. "
            f"Waiting before retry {retry_state.attempt_number + 1}/3..."
        )
    )
    async def execute_with_retry():
        return await servicenow_agent.execute_capability(query)
    
    try:
        result = await execute_with_retry()
        _print_result(result)
        return 0
    except RateLimitError as e:
        print(f"\nRate limit exceeded after 3 attempts.")
        print(f"\nSuggestion: Wait 60 seconds and try again, or upgrade your Azure OpenAI quota.")
        print(f"Error: {str(e)}")
        return 1
    except (InternalServerError, APITimeoutError) as e:
        print(f"\nAzure OpenAI service timeout after 3 attempts.")
        print(f"\nSuggestions:")
        print(f"  1. Simplify your query (ask for fewer fields or shorter time range)")
        print(f"  2. Try breaking the query into smaller parts")
        print(f"  3. Check Azure OpenAI service health status")
        print(f"Error: {str(e)}")
        return 1
    except Exception as e:
        print(f"\nError during query: {str(e)}")
        import traceback
        print(f"Full error traceback:\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # All arguments treated as natural language query
        query = " ".join(sys.argv[1:])
        exit_code = asyncio.run(main_natural_language(query))
    else:
        # Show usage and run default test
        print("="*80)
        print("ServiceNow Agent - Natural Language Interface")
        print("="*80)
        print("\nUsage: Just ask in plain English!")
        print("\n  python test_servicenow.py \"<your question>\"")
        print("\nExample Queries:")
        print("\n  Incident Details & Attachments:")
        print('     python test_servicenow.py "Show me details of incident INC45979594"')
        print('     python test_servicenow.py "Get incident INC43908022 and download any attachments"')
        print('     python test_servicenow.py "Download attachments for INC45979594"')
        print("\n  Time-Based Queries (LLM converts relative time!):")
        print('     python test_servicenow.py "Get all incidents from today"')
        print('     python test_servicenow.py "Show me incidents from last hour"')
        print('     python test_servicenow.py "List incidents created yesterday"')
        print('     python test_servicenow.py "Show incidents from last 2 hours"')
        print("\n  Assignment Group Queries:")
        print('     python test_servicenow.py "Get incidents for FLEX_RagingFHIR - SPT from today"')
        print('     python test_servicenow.py "Show all incidents assigned to my team"')
        print('     python test_servicenow.py "List incidents for FLEX_RagingFHIR - SPT from yesterday"')
        print("\n  Combined Queries:")
        print('     python test_servicenow.py "Get high priority incidents from last week"')
        print('     python test_servicenow.py "Show critical incidents for my team from today"')
        print("\n  The AI Agent will:")
        print("     • Convert relative time expressions to exact timestamps")
        print("     • Choose the appropriate ServiceNow tools automatically")
        print("     • Download attachments when requested")
        print("     • Generate comprehensive incident reports with root cause analysis")
        print("\n" + "="*80)
        print("\nNo query provided. Running default test...")
        print("="*80)
        
        # Run default test with natural language
        exit_code = asyncio.run(main_natural_language("Show me details of incident INC43908022"))
    
    sys.exit(exit_code)
