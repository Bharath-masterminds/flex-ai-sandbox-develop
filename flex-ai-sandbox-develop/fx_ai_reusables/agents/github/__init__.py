"""
GitHub Agent Module

This module provides an AI agent specialized in investigating code changes,
analyzing pull requests, and tracing development history in GitHub repositories.

The GitHubAgent integrates with GitHub's APIs through a suite of tools to provide
comprehensive code investigation capabilities including git blame, commit analysis,
PR discovery, and code search.

Example Usage:
    ```python
    from fx_ai_reusables.agents.github import GitHubAgent
    from fx_ai_reusables.tools.github_tools import (
        create_get_git_blame_for_line_tool,
        create_get_commit_details_by_sha_tool
    )
    
    # Create tools with secret retriever
    tools = [
        create_get_git_blame_for_line_tool(secrets_retriever),
        create_get_commit_details_by_sha_tool(secrets_retriever)
    ]
    
    # Initialize agent
    github_agent = GitHubAgent(tools=tools, llm=llm, secret_retriever=secrets_retriever)
    
    # Execute investigation
    result = await github_agent.execute_capability(
        "Find who last modified line 150 in src/main.py"
    )
    ```
"""

from fx_ai_reusables.agents.github.github_agent import GitHubAgent
from fx_ai_reusables.agents.github.system_prompt import GITHUB_SYSTEM_PROMPT

__all__ = [
    "GitHubAgent",
    "GITHUB_SYSTEM_PROMPT"
]
