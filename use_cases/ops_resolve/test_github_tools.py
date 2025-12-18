"""

GitHub Tools Testing Script

This script demonstrates actual usage of GitHub tools AND tests them with real API calls.
All GitHub functionality including GraphQL blame analysis is integrated into github_tool_compressed.py.

Prerequisites:
    - GITHUB_TOKEN environment variable must be set
    - Install dependencies: pip install -r requirements.txt

Usage:
    python -m fx_ai_reusables.tools.test_github_tools

Configuration:
    Before running, update the TODO placeholders in each test function with your:
    - Repository name (e.g., "owner/repo" or full GitHub URL)
    - File paths relative to repository root
    - Line numbers you want to investigate
    - Search queries and file extensions
"""

import os
import json
import asyncio
import functools

# ==============================================================================
# CONFIGURATION - Update these values for your testing
# ==============================================================================
# TODO: Customize these test parameters for your repository
# ==============================================================================

TEST_PARAMS = {
    "repo": "uhg-internal/flex-ai-sandbox",  # TODO: Replace with your repository (e.g., "microsoft/vscode")
    "branch": "feature/US9323773_Github_Tooling",  # TODO: Replace with branch name (or use "main"/"master" for default)
    "file_path": "fx_ai_reusables/tools/github_pr_tool.py",  # TODO: Replace with file path relative to repo root
    "line_number": 230,  # TODO: Replace with line number to investigate
}

# ==============================================================================

from fx_ai_reusables.tools.github_pr_tool import (
    create_get_git_blame_for_line_tool,
    create_get_commit_details_by_sha_tool,
    create_get_pull_requests_for_commit_tool,
    create_search_code_in_repo_tool,
    create_get_file_content_at_line_tool
)
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever

# IoC Container imports and setup
try:
    # Set DEPLOYMENT_FLAVOR before importing IocConfig (if not already set)
    if not os.getenv("DEPLOYMENT_FLAVOR"):
        os.environ["DEPLOYMENT_FLAVOR"] = "DEVELOPMENTLOCAL"
    
    from fx_ai_reusables.ioc.configuration.ioc_configuration import IocConfig
    from dependency_injector import containers, providers
    from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
    from fx_ai_reusables.secrets.concretes.file_mount.volume_mount_secret_retriever import VolumeMountSecretRetriever
    
    # Define CompositionRoot inline for this test module
    class GitHubToolsCompositionRoot(containers.DeclarativeContainer):
        """IoC container for GitHub tools - proper DI instead of service locator pattern."""
        
        _config = providers.Configuration()
        _config.from_dict({"DeploymentFlavor": IocConfig.DeploymentFlavor})
        
        # Proper DI: Container decides which implementation based on deployment flavor
        _secret_retriever = providers.Selector(
            _config.DeploymentFlavor,
            DEVELOPMENTLOCAL=providers.Factory(EnvironmentVariableSecretRetriever),
            K8DEPLOYED=providers.Factory(VolumeMountSecretRetriever),
            GITWORKFLOWDEPLOYED=providers.Factory(VolumeMountSecretRetriever),
        )
        
        get_secret_retriever = providers.Callable(
            lambda retriever: retriever,
            retriever=_secret_retriever
        )
    
    IOC_AVAILABLE = True
except (ImportError, ValueError) as e:
    IOC_AVAILABLE = False
    GitHubToolsCompositionRoot = None
    print(f"Warning: IoC container not available ({e}), falling back to direct instantiation")


def print_separator(title):
    """Print a nice separator with title."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_json_pretty(data, max_lines=50):
    """Print JSON data in a pretty format with optional line limit."""
    json_str = json.dumps(data, indent=2, default=str)
    lines = json_str.split('\n')
    
    if max_lines and len(lines) > max_lines:
        print('\n'.join(lines[:max_lines]))
        print(f"... (truncated, showing first {max_lines} lines of {len(lines)} total)")
    else:
        print(json_str)


async def check_github_token(secret_retriever):
    """Check if GitHub token is configured using secret retriever."""
    token = await secret_retriever.retrieve_optional_secret_value("GITHUB_TOKEN")
    
    print_separator("GitHub Token Check")
    print(f"GITHUB_TOKEN: {'✓ Set' if token else '✗ Not set'}")
    
    if not token:
        print("\nWARNING: GitHub token not found!")
        print("Please set your GITHUB_TOKEN environment variable:")
        print("  export GITHUB_TOKEN=your_github_token_here  # Linux/Mac")
        print("  set GITHUB_TOKEN=your_github_token_here     # Windows CMD")
        print("  $env:GITHUB_TOKEN='your_github_token_here'  # Windows PowerShell")
        return False
    return True


async def test_git_blame(secret_retriever):
    """Test 1: Git Blame for a specific line"""
    print_separator("Test 1: Git Blame for Line")
    
    # Create the tool using the shared secret retriever
    blame_tool = create_get_git_blame_for_line_tool(secret_retriever)
    
    # Use shared test parameters
    test_params = {
        "repo": TEST_PARAMS["repo"],
        "file_path": TEST_PARAMS["file_path"],
        "line_number": TEST_PARAMS["line_number"],
        "branch": TEST_PARAMS["branch"]
    }
    
    print(f"Repository: {test_params['repo']}")
    print(f"File: {test_params['file_path']}, Line: {test_params['line_number']}")
    print("\nExecuting git blame...")
    
    try:
        # Use ainvoke for async execution
        result = await blame_tool.ainvoke(test_params)
        
        if result.get("status") == "success":
            commit = result.get("commit", {})
            author = commit.get("author", {})
            
            print("\n" + "=" * 80)
            print("GIT BLAME")
            print("=" * 80)
            print(f"Commit: {commit.get('sha', 'N/A')}")
            print(f"Author: {author.get('name', 'N/A')} <{author.get('email', 'N/A')}>")
            print(f"GitHub: @{author.get('github_username', 'N/A')}")
            print(f"Date: {commit.get('date', 'N/A')}")
            print(f"Message: {commit.get('message', {}).get('headline', 'N/A')}")
            print(f"Line Range: {result.get('line_range', {}).get('start', 'N/A')}-{result.get('line_range', {}).get('end', 'N/A')}")
            print(f"Age: {result.get('age_days', 0)} days")
            print(f"URL: {commit.get('url', 'N/A')}")
        else:
            print(f"\n Error: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"\nTest failed: {e}")
        return {"error": str(e)}


async def test_commit_details(secret_retriever, commit_sha=None):
    """Test 2: Get commit details"""
    print_separator("Test 2: Commit Details")
    
    # Skip this test if no commit SHA is available from previous test
    if not commit_sha:
        print("No commit SHA available from previous test. Skipping this test.")
        print("   (This test depends on Test 1: Git Blame)")
        return {"status": "skipped", "message": "No commit SHA available"}
    
    commit_tool = create_get_commit_details_by_sha_tool(secret_retriever)
    
    # Use shared test parameters
    test_params = {
        "repo": TEST_PARAMS["repo"],
        "commit_sha": commit_sha  # SHA from the git blame test
    }
    
    print(f"Fetching commit details for: {commit_sha}")
    
    try:
        result = await commit_tool.ainvoke(test_params)
        
        if result.get("status") == "success":
            print("\n" + "=" * 80)
            print("COMMIT DETAILS")
            print("=" * 80)
            
            author = result.get("author", {})
            print(f"\nAuthor: {author.get('name', 'N/A')} (@{author.get('github', 'N/A')})")
            print(f"   Email: {author.get('email', 'N/A')}")
            print(f"   Date: {author.get('date', 'N/A')}")
            
            message = result.get("message", {})
            print(f"\nMessage: {message.get('subject', 'N/A')}")
            if message.get('body'):
                print(f"\n{message.get('body')}")
            
            stats = result.get("stats", {})
            print(f"\nChanges: {stats.get('files_changed', 0)} files, +{stats.get('additions', 0)}/-{stats.get('deletions', 0)} lines")
            print(f"URL: {result.get('url', 'N/A')}")
        else:
            print(f"\nError: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"\nTest failed: {e}")
        return {"error": str(e)}


async def test_search_code(secret_retriever):
    """Test 3: Search code in repository"""
    print_separator("Test 3: Code Search")
    
    search_tool = create_search_code_in_repo_tool(secret_retriever)
    
    # Test parameters - TODO: CUSTOMIZE THESE VALUES
    test_params = {
        "repo": TEST_PARAMS["repo"],
        "query": "function_name_to_search",  # TODO: Replace with search query
        "file_extension": "py",  # TODO: Replace with file extension (e.g., "py", "js", "java")
        "path": "path/to/search"  # TODO: Replace with path to search within (optional)
    }
    
    print(f"Testing with: {json.dumps(test_params, indent=2)}")
    print("\nSearching code...")
    
    try:
        result = await search_tool.ainvoke(test_params)
        print("\nCode Search Result:")
        print_json_pretty(result, max_lines=30)
        return result
    except Exception as e:
        print(f"\nTest failed: {e}")
        return {"error": str(e)}


async def test_file_content(secret_retriever):
    """Test 4: Get file content with context"""
    print_separator("Test 4: File Content at Line")
    
    content_tool = create_get_file_content_at_line_tool(secret_retriever)
    
    # Use shared test parameters
    test_params = {
        "repo": TEST_PARAMS["repo"],
        "file_path": TEST_PARAMS["file_path"],
        "line_number": TEST_PARAMS["line_number"],
        "context_lines": 5,  # Number of lines before and after to show (default: 5)
        "branch": TEST_PARAMS["branch"]
    }
    
    print(f"Fetching content for line {test_params['line_number']}...")
    
    try:
        result = await content_tool.ainvoke(test_params)
        
        if result.get("status") == "success":
            print("\n" + "=" * 80)
            print("FILE INFORMATION")
            print("=" * 80)
            print(f"File: {result.get('file_path', 'N/A')}")
            print(f"Line {result.get('line_number', 'N/A')}: {result.get('target_line', 'N/A')}")
            
            # Show context lines
            context = result.get("context", [])
            if context:
                print("\nContext:")
                for line_info in context:
                    line_num = line_info.get("line_number")
                    content = line_info.get("content")
                    is_target = line_info.get("is_target", False)
                    marker = ">>> " if is_target else "    "
                    print(f"{marker}{line_num}: {content}")
        else:
            print(f"\nError: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"\nTest failed: {e}")
        return {"error": str(e)}


async def test_comprehensive_analysis(secret_retriever):
    """Test 5: Comprehensive code change analysis (manually orchestrates multiple tools)
    
    This test demonstrates how an agent should orchestrate multiple tools to build
    a comprehensive analysis, rather than relying on a single composite tool.
    """
    print_separator("Test 5: Comprehensive Code Change Analysis (Tool Orchestration)")
    
    # Create individual tools
    blame_tool = create_get_git_blame_for_line_tool(secret_retriever)
    commit_tool = create_get_commit_details_by_sha_tool(secret_retriever)
    pr_tool = create_get_pull_requests_for_commit_tool(secret_retriever)
    content_tool = create_get_file_content_at_line_tool(secret_retriever)
    
    # Use shared test parameters
    test_params = {
        "repo": TEST_PARAMS["repo"],
        "file_path": TEST_PARAMS["file_path"],
        "line_number": TEST_PARAMS["line_number"],
        "branch": TEST_PARAMS["branch"]
    }
    
    print(f"\nStarting investigation...")
    print(f"Repository: {test_params['repo']}")
    print(f"File: {test_params['file_path']}, Line: {test_params['line_number']}")
    print("\nOrchestrating multiple tools for comprehensive analysis...")
    
    try:
        # Step 1: Get blame information
        print("\n[1/4] Getting git blame information...")
        blame_result = await blame_tool.ainvoke(test_params)
        
        if "error" in blame_result:
            print(f"Error in blame: {blame_result['error']}")
            return blame_result
        
        commit_sha = blame_result["commit"]["sha"]
        print(f"   Found commit: {blame_result['commit']['short_sha']}")
        
        # Step 2: Get detailed commit information
        print(f"[2/4] Getting commit details for {commit_sha[:7]}...")
        commit_result = await commit_tool.ainvoke({
            "repo": test_params["repo"],
            "commit_sha": commit_sha
        })
        
        # Step 3: Get associated pull requests
        print(f"[3/4] Finding associated pull requests...")
        pr_result = await pr_tool.ainvoke({
            "repo": test_params["repo"],
            "commit_sha": commit_sha
        })
        
        # Step 4: Get code context
        print(f"[4/4] Getting code context...")
        context_result = await content_tool.ainvoke({
            "repo": test_params["repo"],
            "file_path": test_params["file_path"],
            "line_number": test_params["line_number"],
            "context_lines": 5,
            "branch": test_params["branch"]
        })
        
        # Build comprehensive result
        result = {
            "status": "success",
            "repo": test_params["repo"],
            "file_info": {
                "path": test_params["file_path"],
                "line_number": test_params["line_number"],
                "branch": test_params["branch"]
            },
            "code_context": {
                "target_line": context_result.get("target_line", ""),
                "context": context_result.get("context", [])
            },
            "blame": blame_result.get("commit", {}),
            "commit": commit_result if commit_result.get("status") == "success" else {},
            "pull_requests": pr_result.get("pull_requests", []),
            "timeline": {
                "age_days": blame_result.get("age_days", 0),
                "commit_date": blame_result["commit"].get("committed_date", ""),
                "line_range": blame_result.get("line_range", {})
            }
        }
        
        # Display results (same format as before)
        if result.get("status") == "success":
            # File Information
            code_context = result.get("code_context", {})
            file_info = result.get("file_info", {})
            
            print("\n" + "=" * 80)
            print("FILE INFORMATION")
            print("=" * 80)
            print(f"File: {file_info.get('path', 'N/A')}")
            print(f"Line {file_info.get('line_number', 'N/A')}: {code_context.get('target_line', 'N/A')}")
            
            # Git Blame
            blame = result.get("blame", {})
            author = blame.get("author", {})
            
            print("\n" + "=" * 80)
            print("GIT BLAME")
            print("=" * 80)
            print(f"Commit: {blame.get('sha', 'N/A')}")
            print(f"Author: {author.get('name', 'N/A')} <{author.get('email', 'N/A')}>")
            print(f"GitHub: @{author.get('github_username', 'N/A')}")
            print(f"Date: {blame.get('date', 'N/A')}")
            print(f"Message: {blame.get('message', {}).get('headline', 'N/A')}")
            timeline = result.get("timeline", {})
            print(f"Line Range: {timeline.get('line_range', {}).get('start', 'N/A')}-{timeline.get('line_range', {}).get('end', 'N/A')}")
            print(f"Age: {timeline.get('age_days', 0)} days")
            print(f"URL: {blame.get('url', 'N/A')}")
            
            # Commit Details
            commit_details = result.get("commit", {})
            commit_author = commit_details.get("author", {})
            commit_message = commit_details.get("message", {})
            commit_stats = commit_details.get("stats", {})
            
            print("\n" + "=" * 80)
            print("COMMIT DETAILS")
            print("=" * 80)
            print(f"\nAuthor: {commit_author.get('name', 'N/A')} (@{commit_author.get('github', 'N/A')})")
            print(f"   Email: {commit_author.get('email', 'N/A')}")
            print(f"   Date: {commit_author.get('date', 'N/A')}")
            print(f"\nMessage: {commit_message.get('subject', 'N/A')}")
            if commit_message.get('body'):
                print(f"\n{commit_message.get('body')}")
            print(f"\nChanges: {commit_stats.get('files_changed', 0)} files, +{commit_stats.get('additions', 0)}/-{commit_stats.get('deletions', 0)} lines")
            print(f"URL: {commit_details.get('url', 'N/A')}")
            
            # Pull Requests
            pull_requests = result.get("pull_requests", [])
            if pull_requests:
                print("\n" + "=" * 80)
                print("PULL REQUESTS")
                print("=" * 80)
                for pr in pull_requests:
                    print(f"\nPR #{pr.get('number', 'N/A')}: {pr.get('title', 'N/A')}")
                    # Handle author - it might be a string or a dict
                    author_info = pr.get('author', {})
                    if isinstance(author_info, dict):
                        author_login = author_info.get('login', 'N/A')
                    else:
                        author_login = author_info if author_info else 'N/A'
                    print(f"Author: @{author_login}")
                    print(f"State: {pr.get('state', 'N/A')} | Merged: {'Yes' if pr.get('merged') else 'No'}")
                    
                    # Handle head and base branches
                    head_branch = pr.get('head_branch', pr.get('head', {}).get('ref', 'N/A') if isinstance(pr.get('head'), dict) else 'N/A')
                    base_branch = pr.get('base_branch', pr.get('base', {}).get('ref', 'N/A') if isinstance(pr.get('base'), dict) else 'N/A')
                    print(f"Branch: {head_branch} → {base_branch}")
                    
                    if pr.get('merged_at'):
                        print(f"Merged: {pr.get('merged_at', 'N/A')}")
                    print(f"Created: {pr.get('created_at', 'N/A')}")
                    if pr.get('closed_at'):
                        print(f"Closed: {pr.get('closed_at', 'N/A')}")
                    
                    # Get URL - try multiple possible keys
                    pr_url = pr.get('url', pr.get('html_url', 'N/A'))
                    print(f"URL: {pr_url}")
                    
                    stats = pr.get('stats', {})
                    if stats and (stats.get('additions') or stats.get('deletions')):
                        print(f"Stats: +{stats.get('additions', 0)}/-{stats.get('deletions', 0)} lines, {stats.get('changed_files', 0)} files")
                    
                    review_count = pr.get('review_count', pr.get('review_comments', 0))
                    if review_count:
                        print(f"Reviews: {review_count}")
            
            print("\n" + "=" * 80)
        else:
            print(f"\nError: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"\nTest failed: {e}")
        return {"error": str(e)}


@functools.lru_cache(maxsize=1)
def get_ioc_container() -> GitHubToolsCompositionRoot:
    """
    Create and cache the IoC container to ensure singletons work across test runs.
    This prevents the container from being recreated for each test.
    
    Returns:
        GitHubToolsCompositionRoot: The cached IoC container instance
        
    Raises:
        RuntimeError: If dependency-injector is not installed
    """
    if not IOC_AVAILABLE or GitHubToolsCompositionRoot is None:
        raise RuntimeError(
            "IoC container is not available. Please ensure 'dependency-injector' is installed.\n"
            "Run: pip install -r requirements.txt"
        )
    
    return GitHubToolsCompositionRoot()


async def async_main():
    """Async main function to run all tests"""
    print("🔧 GitHub Tools Testing Suite")
    print("=" * 80)
    print("\nThis script tests all GitHub tools with real API call. Pls use wisely.")
    
    # Get cached IoC container (created only once across all tests)
    container = get_ioc_container()
    
    deployment_flavor = os.getenv("DEPLOYMENT_FLAVOR", "DEVELOPMENTLOCAL")
    print(f"\n📦 Deployment Flavor: {deployment_flavor}")
    print("✅ Using CompositionRoot (proper IoC pattern)")
    
    # Get secret retriever from container
    secret_retriever = container.get_secret_retriever()
    
    # Check for GitHub token using secret retriever
    if not await check_github_token(secret_retriever):
        print("\nCannot proceed without GitHub token. Exiting.")
        return
    
    print("\nRunning Tests...")
    
    # Test 1: Git Blame
    blame_result = await test_git_blame(secret_retriever)
    
    # Extract commit SHA for next test
    commit_sha = None
    if blame_result and "commit" in blame_result:
        commit_sha = blame_result["commit"].get("sha")
    
    # Test 2: Commit Details
    await test_commit_details(secret_retriever, commit_sha)
    
    # Test 3: Code Search
    await test_search_code(secret_retriever)
    
    # Test 4: File Content
    await test_file_content(secret_retriever)
    
    # Test 5: Comprehensive Analysis (combines multiple tools)
    await test_comprehensive_analysis(secret_retriever)
    
    print_separator("Testing Complete")
    print("All tests executed. Check results above for any errors.")
    print("\nTips:")
    print("   - These tools make real GitHub API calls")
    print("   - You can modify test parameters in the functions above")
    print("   - Rate limits apply (60 requests/hour for unauthenticated, 5000 for authenticated)")


def main():
    """Main entry point - runs async main"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
