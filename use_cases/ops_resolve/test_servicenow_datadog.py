#!/usr/bin/env python3
"""
Test file for ServiceNow + DataDog incident analysis workflow.

This test demonstrates the integration between ServiceNow (for incident data) 
and DataDog (for service monitoring and error analysis) to provide comprehensive
incident root cause analysis with service health monitoring.

Usage:
    python test_servicenow_datadog.py [incident_id] [--stream]
"""

from pprint import pprint
import asyncio
import sys
import argparse
from typing import Dict, Any
from pathlib import Path

from dotenv import load_dotenv
from phoenix_setup import setup_phoenix_tracing

from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever

# ServiceNow imports
from fx_ai_reusables.agents.servicenow.servicenow_agent import ServiceNowAgent
from fx_ai_reusables.tools.servicenow_tools import get_incident_by_incident_number

# DataDog imports
from fx_ai_reusables.agents.datadog.datadog_agent import DataDogAgent
from fx_ai_reusables.tools.datadog_tools import (
    get_datadog_service_dependencies,
    find_service_errors_and_traces,
)

from use_cases.ops_resolve.ops_resolve_supervisor import OpsResolveSupervisor


async def analyze_incident_with_datadog(incident_id: str) -> Dict[str, Any]:
    """Analyze an incident end-to-end using ServiceNow + DataDog and return the full result."""
    # Load env and setup tracing
    load_dotenv()
    setup_phoenix_tracing("ops-resolve-servicenow-datadog")

    # Initialize auth and LLM
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()
    environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)
    hcp_authenticator = HcpAuthenticator(environment_reader)
    llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
    llm = await llm_creator.create_llm()

    # Build agents (ServiceNow + DataDog)
    servicenow_agent = ServiceNowAgent([get_incident_by_incident_number], llm)
    datadog_agent = DataDogAgent([
        get_datadog_service_dependencies,
        find_service_errors_and_traces,
    ], llm)

    # Supervisor with ServiceNow + DataDog
    supervisor = OpsResolveSupervisor(llm, [servicenow_agent, datadog_agent])

    # Query
    query = (
        f"Please analyze incident {incident_id} to identify root cause with supporting "
        f"evidence from both ServiceNow and DataDog monitoring data. Provide resolution steps."
    )
    result = await supervisor.run(query)
    return result


def _print_result(result: Dict[str, Any]) -> None:
    """Print the analysis result in a formatted way."""
    print("\n" + "="*60)
    print("✅ SERVICENOW + DATADOG ANALYSIS COMPLETE")
    print("="*60)

    # Extract and display key information from messages (supports LangChain message objects)
    if "messages" in result:
        for message in result["messages"]:
            role = getattr(message, "type", getattr(message, "role", "unknown"))
            content = getattr(message, "content", "")
            name = getattr(message, "name", None)

            if role == "ai" and content:
                print(f"\n🤖 SUPERVISOR Response:")
                print(content)
            elif role == "tool":
                tool_name = name or 'tool'
                if 'servicenow' in tool_name.lower():
                    print(f"\n📋 SERVICENOW '{tool_name}' Output:")
                elif 'datadog' in tool_name.lower():
                    print(f"\n🐕 DATADOG '{tool_name}' Output:")
                else:
                    print(f"\n🛠️ TOOL '{tool_name}' Output:")
                # Truncate long tool outputs for readability
                if len(content) > 1000:
                    print(content[:1000] + "\n... (truncated)")
                else:
                    print(content)
            elif role == "human" and content:
                print(f"\n👤 USER:")
                print(content)
    else:
        print(result)


async def stream_incident_with_datadog(incident_id: str) -> None:
    """Stream the incident analysis for live inspection (testing utility)."""
    # Load env and setup tracing
    load_dotenv()
    setup_phoenix_tracing("ops-resolve-servicenow-datadog-stream")

    # Initialize auth and LLM
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()
    environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)
    hcp_authenticator = HcpAuthenticator(environment_reader)
    llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
    llm = await llm_creator.create_llm()

    # Build agents
    servicenow_agent = ServiceNowAgent([get_incident_by_incident_number], llm)
    datadog_agent = DataDogAgent([
        get_datadog_service_dependencies,
        find_service_errors_and_traces,
    ], llm)

    supervisor = OpsResolveSupervisor(llm, [servicenow_agent, datadog_agent])

    query = (
        f"Please analyze incident {incident_id} to identify root cause with supporting "
        f"evidence from both ServiceNow and DataDog monitoring data. Provide resolution steps."
    )

    print(f"\n🔄 Streaming analysis for {incident_id} with ServiceNow + DataDog...")
    print("="*60)
    await supervisor.run_incident_agent(query)


async def main(incident_id):
    """CLI entry point for ServiceNow + DataDog incident analysis"""
    print(f"🚀 ServiceNow + DataDog Incident Analysis")
    print(f"Incident ID: {incident_id}")
    
    try:
        await stream_incident_with_datadog(incident_id)
        return 0
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        import traceback
        print(f"Full error traceback:\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    # exit_code = asyncio.run(main("INC36124053"))
    exit_code = asyncio.run(main("INC43908022"))
    sys.exit(exit_code)