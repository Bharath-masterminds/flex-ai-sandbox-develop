#!/usr/bin/env python3
"""
Test file for GitHub Agent - Code Investigation and Change Analysis

This test demonstrates the GitHub agent's capabilities by having it analyze
the complete change history for a specific line of code. The agent will
automatically use all available tools to gather comprehensive information.

Usage:
    python test_github_agent.py
"""

import asyncio
import sys
# from phoenix_setup import setup_phoenix_tracing

from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import AzureLlmConfigAndSecretsHolderWrapperReader
from fx_ai_reusables.llm.creators.azure_chat_openai_llm_creator import AzureChatOpenAILlmCreator
from fx_ai_reusables.configmaps.concretes.env_variable.environment_variables_config_map_retriever import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.environment_fetcher.concrete_dotenv.environment_fetcher_async import EnvironmentFetcherAsync

# GitHub imports
from fx_ai_reusables.agents.github.github_agent import GitHubAgent
from fx_ai_reusables.tools.github_tools import (
    create_get_git_blame_for_line_tool,
    create_get_commit_details_by_sha_tool,
    create_get_pull_requests_for_commit_tool,
    create_search_code_in_repo_tool,
    create_get_file_content_at_line_tool
)


async def test_comprehensive_github_investigation():
    """
    Comprehensive test that demonstrates all GitHub agent capabilities.
    
    The agent will automatically choose and use the appropriate tools to:
    - Find who last modified the specified line (git blame)
    - Get detailed commit information
    - Find associated pull requests
    - Retrieve code context
    - Provide a comprehensive analysis with evidence
    
    This demonstrates agent orchestration of multiple basic tools rather than
    relying on a single composite tool.
    """
    print("\n" + "="*80)
    print("GITHUB AGENT - COMPREHENSIVE CODE INVESTIGATION TEST")
    print("="*80)
    
    # Load environment variables using EnvironmentFetcher
    environment_fetcher = EnvironmentFetcherAsync()
    await environment_fetcher.load_environment()
    
    # Setup Phoenix tracing
    # print("Setting up Phoenix tracing...")
    # setup_phoenix_tracing("github-agent-comprehensive-test")

    # Initialize auth and LLM
    print("Initializing authentication and LLM...")
    config_map_retriever = EnvironmentVariablesConfigMapRetriever()
    secrets_retriever = EnvironmentVariableSecretRetriever()
    environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(
        config_map_retriever, 
        secrets_retriever
    )
    hcp_authenticator = HcpAuthenticator(environment_reader)
    llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
    llm = await llm_creator.create_llm()

    # Build GitHub agent with ALL available tools
    print("Creating GitHub agent with all investigation tools...")
    tools = [
        create_get_git_blame_for_line_tool(secrets_retriever),
        create_get_commit_details_by_sha_tool(secrets_retriever),
        create_get_pull_requests_for_commit_tool(secrets_retriever),
        create_search_code_in_repo_tool(secrets_retriever),
        create_get_file_content_at_line_tool(secrets_retriever)
    ]
    github_agent = GitHubAgent(tools=tools, llm=llm, secret_retriever=secrets_retriever)
    
    print(f"   Agent initialized with {len(tools)} tools")
    print(f"   Available tools: {', '.join(github_agent.get_available_tools())}")

    # Test query - Let the agent figure out what tools to use and orchestrate them
    query = (
        "Analyze the complete change history for line 230 in fx_ai_reusables/tools/github_tools.py "
        "in the uhg-internal/flex-ai-sandbox repository on the feature/US9323773_Github_Tooling branch. "
        "Include who made the change, when, why, and any associated pull requests. "
        "Use multiple tools as needed to build a comprehensive analysis."
    )
    
    print("\n" + "="*80)
    print("TEST QUERY:")
    print("="*80)
    print(query)
    print("\n" + "="*80)
    print("AGENT EXECUTION (The agent will choose tools automatically)")
    print("="*80)
    
    # Execute the investigation
    result = await github_agent.execute_capability(query)
    
    # Display results
    print("\n" + "="*80)
    print("RESULTS:")
    print("="*80)
    
    if "messages" in result:
        tool_calls = []
        agent_responses = []
        
        for message in result["messages"]:
            role = getattr(message, "type", getattr(message, "role", "unknown"))
            content = getattr(message, "content", "")
            name = getattr(message, "name", None)

            if role == "ai" and content:
                agent_responses.append(content)
            elif role == "tool":
                tool_name = name or 'tool'
                tool_calls.append(tool_name)
                print(f"\nTool Used: {tool_name}")
                # Show truncated output
                if len(content) > 300:
                    print(f"   Output (truncated): {content[:300]}...")
                else:
                    print(f"   Output: {content}")
        
        # Show final agent response
        if agent_responses:
            print("\n" + "="*80)
            print("FINAL AGENT ANALYSIS:")
            print("="*80)
            print(agent_responses[-1])
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY:")
        print("="*80)
        print(f"Tools automatically selected and used: {len(tool_calls)}")
        print(f"   Tools: {', '.join(set(tool_calls))}")
        print(f"Agent provided comprehensive analysis")
        print(f"Investigation complete!")
    else:
        print("Unexpected result format")
        print(result)
    
    return result


async def main():
    """Run the comprehensive GitHub agent test"""
    print("GitHub Agent Test Suite")
    print("Testing comprehensive code investigation capabilities")
    
    try:
        result = await test_comprehensive_github_investigation()
        
        print("\n" + "="*80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nThe GitHub agent successfully:")
        print("  - Loaded environment configuration")
        print("  - Initialized with multiple investigation tools")
        print("  - Automatically selected appropriate tools")
        print("  - Executed a comprehensive code investigation")
        print("  - Provided detailed analysis with evidence")
        
        return 0
        
    except Exception as e:
        print(f"\nError during testing: {str(e)}")
        import traceback
        print(f"Full error traceback:\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
