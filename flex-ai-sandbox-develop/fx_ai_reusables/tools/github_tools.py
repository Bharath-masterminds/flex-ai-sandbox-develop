"""
GitHub Tools for AI Agents - Basic Repository Analysis and PR Investigation

This module provides AI agents with fundamental GitHub integration tools for investigating code changes,
tracking PR information, analyzing commits, and performing code analysis. Each tool provides a single,
focused capability following the single responsibility principle. Agents should orchestrate multiple
tools to perform complex analysis tasks.

DESIGN PHILOSOPHY:
    - Each tool performs ONE specific task with clear inputs/outputs
    - Tools return raw, structured data without interpretation
    - Complex workflows should be orchestrated by the agent, not baked into tools
    - Tools are composable building blocks, not end-to-end solutions

PRIMARY USE CASES:
    1. Git Blame Analysis: Find out who last modified a specific line of code and why
    2. Commit Investigation: Get detailed information about any commit including changed files and statistics
    3. PR Discovery: Find all PRs associated with a specific commit
    4. Code Search: Search for code patterns, classes, functions across repositories
    5. File Content Analysis: Extract specific lines of code with surrounding context

AVAILABLE TOOLS (Use these factory functions to create tools):
    
    1. create_get_git_blame_for_line_tool()
       - Finds who last modified a specific line and why (includes associated PRs)
       - Use when: Agent needs to know "who wrote this code?" or "when was this line changed?"
    
    2. create_get_commit_details_by_sha_tool()
       - Gets complete commit information including all changed files
       - Use when: Agent has a commit SHA and needs full details
    
    3. create_get_pull_requests_for_commit_tool()
       - Finds all PRs associated with a specific commit
       - Use when: Agent needs to understand PR context for a commit
    
    4. create_search_code_in_repo_tool()
       - Searches for code patterns in a repository
       - Use when: Agent needs to find where specific code exists
    
    5. create_get_file_content_at_line_tool()
       - Gets file content around a specific line number
       - Use when: Agent needs to see code context around a line

FOR AI AGENTS:
    - All tools return structured dictionaries with clear keys
    - Error messages are descriptive and actionable
    - Repository can be specified as "owner/repo" or full GitHub URL
    - All tools handle authentication automatically using secrets
    - Results include direct GitHub URLs for evidence/verification
    - Agents should chain tools together to build complex workflows

REQUIRED SECRETS:
    - GITHUB_TOKEN or GITHUB_PAT: GitHub Personal Access Token with repo:read permissions
    - Get token from: https://github.com/settings/tokens

EXAMPLE AGENT ORCHESTRATION:
    ```python
    # Create individual tools with secret retriever
    blame_tool = create_get_git_blame_for_line_tool(secret_retriever)
    commit_tool = create_get_commit_details_by_sha_tool(secret_retriever)
    pr_tool = create_get_pull_requests_for_commit_tool(secret_retriever)
    content_tool = create_get_file_content_at_line_tool(secret_retriever)
    
    # Agent orchestrates tools to build complete picture:
    # 1. Get blame info
    blame_result = blame_tool.invoke({
        "repo": "microsoft/vscode",
        "file_path": "src/vs/editor/editor.main.ts",
        "line_number": 42
    })
    
    # 2. Agent decides: need more info about the commit
    commit_sha = blame_result["commit"]["sha"]
    commit_result = commit_tool.invoke({"repo": "microsoft/vscode", "commit_sha": commit_sha})
    
    # 3. Agent decides: want to see associated PRs
    pr_result = pr_tool.invoke({"repo": "microsoft/vscode", "commit_sha": commit_sha})
    
    # Agent synthesizes results and responds to user
    ```
"""

import warnings
import asyncio
import requests
import time
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_core.tools import StructuredTool
from github import Github
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from urllib.parse import urlparse
from fx_ai_reusables.helpers import run_async_in_sync_context
from fx_ai_reusables.helpers.retry_decorator import retry_api_call

# Suppress deprecation warnings from PyGithub
warnings.filterwarnings('ignore', category=DeprecationWarning)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _make_graphql_request(endpoint: str, headers: Dict[str, str], query: str, variables: Dict[str, Any], 
                         timeout: int = 60, retry_attempts: int = 3) -> Dict[str, Any]:
    """
    Make a GraphQL request to GitHub API with automatic retry using retry_api_call decorator.
    
    Retries on:
    - HTTP errors (including 502, 503, 504)
    - Request exceptions
    
    Uses exponential backoff with configurable retry attempts.
    
    Args:
        endpoint: GraphQL API endpoint URL
        headers: Request headers including authentication
        query: GraphQL query string
        variables: Query variables
        timeout: Request timeout in seconds (default: 60)
        retry_attempts: Number of retry attempts (default: 3)
    
    Returns:
        Parsed JSON response
    
    Raises:
        requests.exceptions.HTTPError: If request fails after all retries
        requests.exceptions.RequestException: If request fails after all retries
    """
    # Define the actual request function with retry decorator
    @retry_api_call(
        max_retries=retry_attempts,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.exceptions.HTTPError, requests.exceptions.RequestException),
        verbose=True
    )
    def _do_request():
        response = requests.post(
            endpoint,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    
    return _do_request()


def _parse_repo_identifier(repo_identifier: str) -> str:
    """Parse repository identifier from URL or owner/repo format."""
    parsed = urlparse(repo_identifier)
    if parsed.hostname and parsed.hostname.lower() == "github.com":
        path_parts = [p for p in parsed.path.rstrip("/").split("/") if p]
        if len(path_parts) >= 2:
            return f"{path_parts[-2]}/{path_parts[-1]}"
        else:
            raise ValueError(f"Invalid GitHub repository URL (not enough path segments): {repo_identifier}")
    return repo_identifier

def _parse_repo_to_owner_repo(repo_identifier: str) -> tuple:
    """
    Parse GitHub repository identifier to extract owner and repo name.
    
    Args:
        repo_identifier: GitHub repository URL or owner/repo format
    
    Returns:
        Tuple of (owner, repo)
    """
    parsed = urlparse(repo_identifier)
    if parsed.scheme and parsed.netloc:  # likely a URL
        # Accept only exact 'github.com' host (case-insensitive)
        if parsed.netloc.lower() == "github.com":
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
            else:
                raise ValueError("URL does not contain owner/repo")
        else:
            raise ValueError("URL does not point to github.com")
    elif "/" in repo_identifier:
        parts = repo_identifier.strip("/").split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            raise ValueError("Owner/repo format must be 'owner/repo'")
    else:
        raise ValueError("Invalid repository URL format")

def _get_graphql_blame_for_line(token: str, owner: str, repo: str, file_path: str, 
                                line_number: int, branch: str, timeout: int = 60) -> Optional[Dict]:
    """
    Get git blame information for a specific line using GitHub GraphQL API.
    Uses a two-step approach to avoid complexity limits:
    1. Get blame commit
    2. Query PR separately
    
    Args:
        token: GitHub authentication token
        owner: Repository owner (username or org)
        repo: Repository name
        file_path: Path to file in repository
        line_number: Line number to blame (1-indexed)
        branch: Branch name (default: main)
        timeout: Request timeout in seconds (default: 60)
    
    Returns:
        Dictionary containing blame information or None if error
    """
    endpoint = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Step 1: Get blame information with minimal fields
    blame_query = """
    query($owner: String!, $repo: String!, $branch: String!, $path: String!) {
        repository(owner: $owner, name: $repo) {
            ref(qualifiedName: $branch) {
                target {
                    ... on Commit {
                        blame(path: $path) {
                            ranges {
                                startingLine
                                endingLine
                                age
                                commit {
                                    oid
                                    message
                                    messageHeadline
                                    messageBody
                                    committedDate
                                    pushedDate
                                    author {
                                        name
                                        email
                                        user {
                                            login
                                            url
                                        }
                                    }
                                    committer {
                                        name
                                        email
                                    }
                                    additions
                                    deletions
                                    changedFilesIfAvailable
                                    url
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "owner": owner,
        "repo": repo,
        "branch": f"refs/heads/{branch}",
        "path": file_path
    }
    
    try:
        # Make GraphQL request with automatic retry (using Tenacity)
        data = _make_graphql_request(endpoint, headers, blame_query, variables, timeout=timeout)
        
        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            return None
        
        # Get blame ranges from response
        repo_data = data.get("data", {}).get("repository")
        if not repo_data:
            print(f"Repository not found: {owner}/{repo}")
            return None
        
        ref_data = repo_data.get("ref")
        if not ref_data:
            print(f"Branch not found: {branch}")
            return None
        
        target_data = ref_data.get("target")
        if not target_data:
            print(f"Target commit not found")
            return None
        
        blame_data = target_data.get("blame")
        if not blame_data:
            print(f"No blame data found for {file_path}")
            return None
        
        ranges = blame_data.get("ranges", [])
        
        # Find the range that contains our target line
        for blame_range in ranges:
            start = blame_range["startingLine"]
            end = blame_range["endingLine"]
            
            if start <= line_number <= end:
                commit = blame_range["commit"]
                commit_sha = commit["oid"]
                
                # Step 2: Get associated PRs separately
                prs = _get_prs_for_commit_graphql(token, owner, repo, commit_sha, timeout=timeout)
                
                # Format and return the result
                return _format_blame_info(blame_range, line_number, prs)
        
        print(f"Line {line_number} not found in blame ranges")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None

def _get_prs_for_commit_graphql(token: str, owner: str, repo: str, commit_sha: str, 
                                timeout: int = 60,
                                pr_fetch_limit: int = 10,
                                pr_labels_limit: int = 10,
                                pr_reviews_limit: int = 5) -> List[Dict]:
    """
    Get associated PRs for a commit using a separate GraphQL query.
    This avoids hitting complexity limits when combined with blame query.
    
    Args:
        token: GitHub authentication token
        owner: Repository owner
        repo: Repository name
        commit_sha: Commit SHA
        timeout: Request timeout in seconds (default: 60)
        pr_fetch_limit: Maximum number of PRs to fetch (default: 10)
        pr_labels_limit: Maximum number of labels per PR to fetch (default: 10)
        pr_reviews_limit: Maximum number of reviews to fetch (default: 5)
    
    Returns:
        List of PR dictionaries
    """
    endpoint = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    pr_query = """
    query($owner: String!, $repo: String!, $sha: GitObjectID!, $prLimit: Int!, $labelsLimit: Int!, $reviewsLimit: Int!) {
        repository(owner: $owner, name: $repo) {
            object(oid: $sha) {
                ... on Commit {
                    associatedPullRequests(first: $prLimit) {
                        nodes {
                            number
                            title
                            state
                            merged
                            mergedAt
                            url
                            author {
                                login
                            }
                            baseRefName
                            headRefName
                            additions
                            deletions
                            changedFiles
                            createdAt
                            updatedAt
                            closedAt
                            labels(first: $labelsLimit) {
                                nodes {
                                    name
                                    color
                                }
                            }
                            reviews(first: $reviewsLimit) {
                                totalCount
                            }
                            commits {
                                totalCount
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "owner": owner,
        "repo": repo,
        "sha": commit_sha,
        "prLimit": pr_fetch_limit,
        "labelsLimit": pr_labels_limit,
        "reviewsLimit": pr_reviews_limit
    }
    
    try:
        # Make GraphQL request with automatic retry (using Tenacity)
        data = _make_graphql_request(endpoint, headers, pr_query, variables, timeout=timeout)
        
        if "errors" in data:
            print(f"Error getting PRs: {data['errors']}")
            return []
        
        pr_nodes = (
            data.get("data", {})
            .get("repository", {})
            .get("object", {})
            .get("associatedPullRequests", {})
            .get("nodes", [])
        )
        
        prs = []
        for pr in pr_nodes:
            prs.append({
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "merged": pr["merged"],
                "merged_at": pr.get("mergedAt"),
                "created_at": pr.get("createdAt"),
                "updated_at": pr.get("updatedAt"),
                "closed_at": pr.get("closedAt"),
                "url": pr["url"],
                "author": pr["author"]["login"] if pr.get("author") else "Unknown",
                "base_branch": pr.get("baseRefName", "N/A"),
                "head_branch": pr.get("headRefName", "N/A"),
                "additions": pr["additions"],
                "deletions": pr["deletions"],
                "changed_files": pr["changedFiles"],
                "labels": [{"name": label["name"], "color": label.get("color", "")} for label in pr.get("labels", {}).get("nodes", [])],
                "review_count": pr.get("reviews", {}).get("totalCount", 0),
                "commit_count": pr.get("commits", {}).get("totalCount", 0)
            })
        
        return prs
        
    except Exception as e:
        print(f"Error fetching PRs: {str(e)}")
        return []

def _format_blame_info(blame_range: Dict, line_number: int, pull_requests: List[Dict] = None) -> Dict:
    """Format GraphQL blame range into structured information"""
    
    commit = blame_range["commit"]
    author = commit.get("author", {})
    user = author.get("user") if author else None
    
    # Calculate age in days from commit date
    commit_date_str = commit.get("committedDate", "")
    if commit_date_str:
        commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
        age_days = (datetime.now(commit_date.tzinfo) - commit_date).days
    else:
        age_days = 0
    
    # Use provided PRs or empty list
    prs = pull_requests if pull_requests is not None else []
    
    return {
        "line_number": line_number,
        "line_range": {
            "start": blame_range["startingLine"],
            "end": blame_range["endingLine"]
        },
        "age": age_days,
        "age_category": blame_range.get("age", 0),
        "commit": {
            "sha": commit["oid"],
            "short_sha": commit["oid"][:7],
            "message": commit["message"],
            "headline": commit["messageHeadline"],
            "body": commit.get("messageBody", ""),
            "committed_date": commit.get("committedDate", ""),
            "pushed_date": commit.get("pushedDate"),
            "url": commit["url"],
            "author": {
                "name": author.get("name", "Unknown") if author else "Unknown",
                "email": author.get("email", "") if author else "",
                "github_username": user.get("login", "N/A") if user else "N/A",
                "github_url": user.get("url") if user else None
            },
            "committer": {
                "name": commit.get("committer", {}).get("name", ""),
                "email": commit.get("committer", {}).get("email", "")
            },
            "stats": {
                "additions": commit.get("additions", 0),
                "deletions": commit.get("deletions", 0),
                "files_changed": commit.get("changedFilesIfAvailable", 0)
            }
        },
        "pull_requests": prs
    }

# ============================================================================
# TOOL 1: Git Blame Analysis
# ============================================================================

def create_get_git_blame_for_line_tool(secret_retriever: ISecretRetriever):
    """Factory function to create git blame tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the AI agent invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching GitHub credentials
        
    Returns:
        Configured tool instance that AI agents can call with (repo, file_path, line_number, branch)
    """
    async def get_git_blame_for_line(repo: str, file_path: str, line_number: int, branch: Optional[str] = None) -> Dict[str, Any]:
        """Find who last modified a specific line of code and get the associated pull request information.
        
        This tool uses GitHub's GraphQL API to perform git blame analysis on a specific line in a file.
        It tells you WHO changed the line, WHEN they changed it, WHY they changed it (commit message),
        and WHICH pull request the change came from (if any).
        
        Perfect for answering questions like:
        - "Who wrote this line of code?"
        - "When was this code last changed?"
        - "What pull request introduced this change?"
        - "Why was this code modified?"
        
        The tool automatically handles complex git histories including merges and rebases, and provides
        complete context including commit details, author information, and associated PRs.
        
        Args:
            repo: Repository identifier. Can be either:
                  - "owner/repo" format (e.g., "microsoft/vscode")
                  - Full GitHub URL (e.g., "https://github.com/microsoft/vscode")
            file_path: Path to the file from the repository root.
                       Example: "src/main/java/com/example/App.java"
            line_number: The line number to investigate (1-indexed, so first line = 1).
                        Must be a valid line number within the file.
            branch: Optional branch name to check. If not provided, defaults to the
                   'develop' branch.
        
        Returns:
            Dict[str, Any]: Comprehensive blame information including:
            
            Success response structure:
            {
                "status": "success",
                "repo": "microsoft/vscode",
                "file_path": "src/editor.ts",
                "line_number": 42,
                "branch": "main",
                "commit": {
                    "sha": "abc123...",
                    "short_sha": "abc123",
                    "author": {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "github_username": "johndoe"
                    },
                    "date": "2024-01-15T10:30:00Z",
                    "message": {
                        "headline": "Fix editor scrolling issue",
                        "body": "Detailed explanation..."
                    },
                    "url": "https://github.com/...",
                    "stats": {
                        "additions": 15,
                        "deletions": 8,
                        "files_changed": 3
                    }
                },
                "line_range": {"start": 40, "end": 45},
                "age_days": 30,
                "pull_requests": [
                    {
                        "number": 1234,
                        "title": "Fix scrolling performance",
                        "state": "MERGED",
                        "merged": true,
                        "author": "johndoe",
                        "url": "https://github.com/..."
                    }
                ]
            }
            
            Error response structure:
            {
                "error": "Description of what went wrong",
                "error_type": "ValueError",
                "repo": "microsoft/vscode",
                "file_path": "src/editor.ts",
                "line_number": 42
            }
        
        Common Errors:
            - "GitHub token not found": Missing GITHUB_TOKEN or GITHUB_PAT secret
            - "File not found": The file_path doesn't exist in the repository
            - "Line number out of range": The line_number is invalid for this file
            - "Branch not found": The specified branch doesn't exist
            - "Repository not found": Invalid repository name or no access
        
        Note:
            - Requires GITHUB_TOKEN or GITHUB_PAT secret with repo:read permissions
            - Line numbers are 1-indexed (first line = 1, not 0)
            - The tool shows the most recent change to the line
            - Pull request information is included automatically when available
            - Works with both public and private repositories (with proper access)
            - Automatically retries on transient API failures
        """
        try:
            # Get GitHub token from secrets
            token = await secret_retriever.retrieve_optional_secret_value("GITHUB_TOKEN")
            if not token:
                token = await secret_retriever.retrieve_optional_secret_value("GITHUB_PAT")
            
            if not token:
                return {"error": "GitHub token not found. Required: GITHUB_TOKEN or GITHUB_PAT", 
                        "repo": repo, "file_path": file_path, "line_number": line_number}
            
            repo_name = _parse_repo_identifier(repo)
            owner, repo_short = _parse_repo_to_owner_repo(repo_name)
            
            # Use 'develop' branch if not specified
            if not branch:
                branch = "develop"
            
            # Validate file exists
            try:
                github = Github(token)
                repo_obj = github.get_repo(repo_name)
                repo_obj.get_contents(file_path, ref=branch)
            except Exception as file_error:
                if "404" in str(file_error):
                    return {"error": f"File '{file_path}' not found in repository: {str(file_error)}", 
                            "repo": repo_name, "file_path": file_path, "line_number": line_number}
                raise
            
            # Execute GraphQL blame query
            blame_info = _get_graphql_blame_for_line(token, owner, repo_short, 
                                                     file_path, line_number, branch)
            
            if not blame_info:
                return {"error": "Could not retrieve blame information", "repo": repo_name, 
                        "file_path": file_path, "line_number": line_number}
            
            commit = blame_info["commit"]
            author = commit["author"]
            
            return {
                "status": "success", "repo": repo_name, "file_path": file_path, "line_number": line_number, "branch": branch,
                "commit": {
                    "sha": commit["sha"], "short_sha": commit["short_sha"],
                    "author": {"name": author["name"], "email": author["email"], "github_username": author["github_username"]},
                    "date": commit["committed_date"],
                    "message": {"headline": commit["headline"], "body": commit["body"]},
                    "url": commit["url"],
                    "stats": {"additions": commit["stats"]["additions"], "deletions": commit["stats"]["deletions"], 
                             "files_changed": commit["stats"]["files_changed"]}
                },
                "line_range": blame_info["line_range"], "age_days": blame_info["age"], 
                "pull_requests": blame_info["pull_requests"]
            }
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__, "repo": repo, 
                    "file_path": file_path, "line_number": line_number}
    
    def sync_wrapper(repo: str, file_path: str, line_number: int, branch: Optional[str] = None) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return run_async_in_sync_context(get_git_blame_for_line, repo, file_path, line_number, branch)
    
    sync_wrapper.__doc__ = get_git_blame_for_line.__doc__
    
    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_git_blame_for_line,
        name="get_git_blame_for_line",
        description=get_git_blame_for_line.__doc__ or "Get git blame information for a specific line",
    )

# ============================================================================
# TOOL 2: Commit Details Analysis
# ============================================================================

def create_get_commit_details_by_sha_tool(secret_retriever: ISecretRetriever):
    """Factory function to create commit details tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the AI agent invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching GitHub credentials
        
    Returns:
        Configured tool instance that AI agents can call with (repo, commit_sha)
    """
    async def get_commit_details_by_sha(repo: str, commit_sha: str) -> Dict[str, Any]:
        """Get complete information about a specific GitHub commit including all changed files and statistics.
        
        This tool retrieves comprehensive details about any commit in a GitHub repository using the
        commit's SHA hash. It provides complete metadata including who made the commit, when it was made,
        the full commit message, all files that were changed, and detailed statistics.
        
        Perfect for answering questions like:
        - "What files were changed in this commit?"
        - "What was the purpose of commit abc123?"
        - "How many lines were added/deleted in this commit?"
        - "Who authored this commit and when?"
        
        The tool works with both full 40-character SHAs and abbreviated 7+ character SHAs, and includes
        patch previews for each changed file.
        
        Args:
            repo: Repository identifier. Can be either:
                  - "owner/repo" format (e.g., "facebook/react")
                  - Full GitHub URL (e.g., "https://github.com/facebook/react")
            commit_sha: The commit SHA hash to investigate. Can be either:
                       - Full 40-character SHA: "abc123def456..."
                       - Abbreviated 7+ character SHA: "abc123d"
        
        Returns:
            Dict[str, Any]: Comprehensive commit information including:
            
            Success response structure:
            {
                "status": "success",
                "repo": "facebook/react",
                "sha": "abc123def456...",
                "short_sha": "abc123d",
                "author": {
                    "name": "Jane Smith",
                    "email": "jane@example.com",
                    "github": "janesmith",
                    "date": "2024-01-15T14:30:00Z"
                },
                "committer": {
                    "name": "GitHub",
                    "email": "noreply@github.com",
                    "date": "2024-01-15T14:30:00Z"
                },
                "message": {
                    "subject": "Fix memory leak in hooks",
                    "body": "Detailed explanation of the fix..."
                },
                "stats": {
                    "additions": 25,
                    "deletions": 10,
                    "total": 35,
                    "files_changed": 4
                },
                "files": [
                    {
                        "filename": "src/hooks/useState.js",
                        "status": "modified",
                        "additions": 15,
                        "deletions": 5,
                        "changes": 20,
                        "patch": "@@ -10,7 +10,7 @@ function useState..."
                    }
                ],
                "total_files": 4,
                "parents": ["parent_sha1", "parent_sha2"],
                "url": "https://github.com/facebook/react/commit/abc123",
                "verified": true
            }
            
            Error response structure:
            {
                "error": "Description of what went wrong",
                "error_type": "ValueError",
                "repo": "facebook/react",
                "commit_sha": "abc123"
            }
        
        Common Errors:
            - "GitHub token not found": Missing GITHUB_TOKEN or GITHUB_PAT secret
            - "Commit not found": Invalid commit SHA or commit doesn't exist
            - "Repository not found": Invalid repository name or no access
            - "Bad credentials": Invalid or expired GitHub token
        
        Note:
            - Requires GITHUB_TOKEN or GITHUB_PAT secret with repo:read permissions
            - Works with both full and abbreviated commit SHAs
            - Patch previews are truncated to first 500 characters per file
            - Only first 20 files are included (total_files shows complete count)
            - Verified flag indicates if commit has a verified GPG signature
            - Parent commits are listed (multiple parents = merge commit)
            - Works with both public and private repositories (with proper access)
        """
        try:
            token = await secret_retriever.retrieve_optional_secret_value("GITHUB_TOKEN")
            if not token:
                token = await secret_retriever.retrieve_optional_secret_value("GITHUB_PAT")
            
            if not token:
                return {"error": "GitHub token not found. Required: GITHUB_TOKEN or GITHUB_PAT", 
                        "repo": repo, "commit_sha": commit_sha}
            
            repo_name = _parse_repo_identifier(repo)
            github = Github(token)
            repo_obj = github.get_repo(repo_name)
            commit = repo_obj.get_commit(commit_sha)
            
            files_list = [{"filename": f.filename, "status": f.status, "additions": f.additions, 
                          "deletions": f.deletions, "changes": f.changes, 
                          "patch": f.patch[:500] if f.patch else None} for f in commit.files]
            
            return {
                "status": "success", "repo": repo_name, "sha": commit.sha, "short_sha": commit.sha[:7],
                "author": {"name": commit.commit.author.name, "email": commit.commit.author.email,
                          "github": commit.author.login if commit.author else None, 
                          "date": commit.commit.author.date.isoformat()},
                "committer": {"name": commit.commit.committer.name, "email": commit.commit.committer.email,
                             "date": commit.commit.committer.date.isoformat()},
                "message": {"subject": commit.commit.message.split("\n")[0],
                           "body": "\n".join(commit.commit.message.split("\n")[1:]).strip()},
                "stats": {"additions": commit.stats.additions, "deletions": commit.stats.deletions,
                         "total": commit.stats.total, "files_changed": len(files_list)},
                "files": files_list[:20], "total_files": len(files_list),
                "parents": [p.sha for p in commit.parents], "url": commit.html_url,
                "verified": commit.commit.verification.verified if hasattr(commit.commit, 'verification') else False
            }
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__, "repo": repo, "commit_sha": commit_sha}
    
    def sync_wrapper(repo: str, commit_sha: str) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return run_async_in_sync_context(get_commit_details_by_sha, repo, commit_sha)
    
    sync_wrapper.__doc__ = get_commit_details_by_sha.__doc__
    
    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_commit_details_by_sha,
        name="get_commit_details_by_sha",
        description=get_commit_details_by_sha.__doc__ or "Get comprehensive commit details",
    )

# ============================================================================
# TOOL 3: Pull Request Discovery
# ============================================================================

def create_get_pull_requests_for_commit_tool(secret_retriever: ISecretRetriever):
    """Factory function to create PR discovery tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the AI agent invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching GitHub credentials
        
    Returns:
        Configured tool instance that AI agents can call with (repo, commit_sha)
    """
    async def get_pull_requests_for_commit(repo: str, commit_sha: str) -> List[Dict[str, Any]]:
        """Find all pull requests associated with a specific commit.
        
        This tool discovers all pull requests (PRs) that are related to a given commit. A commit
        can be associated with a PR in several ways: it could be part of the PR branch, the merge
        commit of the PR, or cherry-picked into another PR. This tool finds all of these relationships.
        
        Perfect for answering questions like:
        - "Which pull request introduced this commit?"
        - "What was the review process for this code change?"
        - "Was this commit merged via a PR or pushed directly?"
        - "What PRs reference this commit?"
        
        The tool provides complete PR metadata including titles, descriptions, review status, labels,
        and merge information. This is essential for understanding the context and approval process
        behind code changes.
        
        Args:
            repo: Repository identifier. Can be either:
                  - "owner/repo" format (e.g., "angular/angular")
                  - Full GitHub URL (e.g., "https://github.com/angular/angular")
            commit_sha: The commit SHA hash to find PRs for. Can be either:
                       - Full 40-character SHA: "abc123def456..."
                       - Abbreviated 7+ character SHA: "abc123d"
        
        Returns:
            Dict[str, Any]: PR discovery results including:
            
            Success response structure (with PRs):
            {
                "status": "success",
                "repo": "angular/angular",
                "commit_sha": "abc123",
                "pull_requests": [
                    {
                        "number": 5678,
                        "title": "feat: Add new component lifecycle hook",
                        "state": "MERGED",
                        "merged": true,
                        "author": "contributor123",
                        "created_at": "2024-01-10T09:00:00Z",
                        "merged_at": "2024-01-15T15:30:00Z",
                        "closed_at": "2024-01-15T15:30:00Z",
                        "url": "https://github.com/angular/angular/pull/5678",
                        "body": "This PR adds a new lifecycle hook...",
                        "labels": ["feature", "needs-review"],
                        "base_branch": "main",
                        "head_branch": "feature/new-hook",
                        "stats": {
                            "commits": 5,
                            "additions": 120,
                            "deletions": 45,
                            "changed_files": 8
                        },
                        "review_count": 3
                    }
                ],
                "count": 1
            }
            
            Success response structure (no PRs):
            {
                "status": "success",
                "repo": "angular/angular",
                "commit_sha": "abc123",
                "pull_requests": [],
                "count": 0
            }
            
            Error response structure:
            {
                "error": "Description of what went wrong",
                "error_type": "ValueError",
                "repo": "angular/angular",
                "commit_sha": "abc123",
                "pull_requests": []
            }
        
        Common Errors:
            - "GitHub token not found": Missing GITHUB_TOKEN or GITHUB_PAT secret
            - "Commit not found": Invalid commit SHA or commit doesn't exist
            - "Repository not found": Invalid repository name or no access
            - "Bad credentials": Invalid or expired GitHub token
        
        Understanding PR States:
            - "MERGED": PR was accepted and merged into the base branch
            - "CLOSED": PR was closed without merging
            - "OPEN": PR is still open and under review
        
        Note:
            - Requires GITHUB_TOKEN or GITHUB_PAT secret with repo:read permissions
            - Returns empty list if commit was pushed directly (not via PR)
            - Works with both full and abbreviated commit SHAs
            - PR descriptions are truncated to first 500 characters
            - Review count shows number of formal reviews submitted
            - Labels help understand PR categorization (feature, bug, etc.)
            - Handles merge commits, squash merges, and rebase merges
            - Works with both public and private repositories (with proper access)
        """
        try:
            token = await secret_retriever.retrieve_optional_secret_value("GITHUB_TOKEN")
            if not token:
                token = await secret_retriever.retrieve_optional_secret_value("GITHUB_PAT")
            
            if not token:
                return {"error": "GitHub token not found. Required: GITHUB_TOKEN or GITHUB_PAT", 
                        "repo": repo, "commit_sha": commit_sha, "pull_requests": []}
            
            repo_name = _parse_repo_identifier(repo)
            github = Github(token)
            repo_obj = github.get_repo(repo_name)
            commit = repo_obj.get_commit(commit_sha)
            pulls = commit.get_pulls()
            
            pr_list = [{
                "number": pr.number, "title": pr.title, "state": pr.state, "merged": pr.merged,
                "author": pr.user.login if pr.user else "Unknown",
                "created_at": pr.created_at.isoformat(),
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                "url": pr.html_url, "body": pr.body[:500] if pr.body else "No description",
                "labels": [l.name for l in pr.labels],
                "base_branch": pr.base.ref, "head_branch": pr.head.ref,
                "stats": {"commits": pr.commits, "additions": pr.additions, 
                         "deletions": pr.deletions, "changed_files": pr.changed_files},
                "review_count": pr.get_reviews().totalCount if hasattr(pr, 'get_reviews') else 0
            } for pr in pulls]
            
            return {"status": "success", "repo": repo_name, "commit_sha": commit_sha, 
                    "pull_requests": pr_list, "count": len(pr_list)}
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__, 
                    "repo": repo, "commit_sha": commit_sha, "pull_requests": []}
    
    def sync_wrapper(repo: str, commit_sha: str) -> List[Dict[str, Any]]:
        """Sync wrapper that runs the async function."""
        return run_async_in_sync_context(get_pull_requests_for_commit, repo, commit_sha)
    
    sync_wrapper.__doc__ = get_pull_requests_for_commit.__doc__
    
    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_pull_requests_for_commit,
        name="get_pull_requests_for_commit",
        description=get_pull_requests_for_commit.__doc__ or "Get pull requests for a commit",
    )

# ============================================================================
# TOOL 4: Advanced Code Search
# ============================================================================

def create_search_code_in_repo_tool(secret_retriever: ISecretRetriever):
    """Factory function to create code search tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the AI agent invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching GitHub credentials
        
    Returns:
        Configured tool instance that AI agents can call with (repo, query, file_extension, path)
    """
    async def search_code_in_repo(repo: str, query: str, file_extension: Optional[str] = None, 
                                  path: Optional[str] = None) -> Dict[str, Any]:
        """Search for code patterns, classes, functions, or text across a GitHub repository.
        
        This tool uses GitHub's powerful code search engine to find specific code patterns within
        a repository. You can search for class names, function names, variable names, comments,
        or any text that appears in the code. Optional filters allow you to narrow down results
        by file type or directory path.
        
        Perfect for answering questions like:
        - "Where is class UserService defined?"
        - "Find all files that import React"
        - "Where is the function calculateTotal used?"
        - "Find all TODO comments in the Java files"
        - "Search for 'deprecated' in the src/api directory"
        
        The tool returns file paths, names, and direct URLs to each match, making it easy to
        locate and investigate specific code.
        
        Args:
            repo: Repository identifier. Can be either:
                  - "owner/repo" format (e.g., "nodejs/node")
                  - Full GitHub URL (e.g., "https://github.com/nodejs/node")
            query: The search query. Can be:
                   - Class name: "UserService"
                   - Function name: "calculateTotal"
                   - Import statement: "import React"
                   - Comment text: "TODO"
                   - Any code pattern or text
            file_extension: Optional file type filter (WITHOUT the dot). Examples:
                           - "java" (finds .java files)
                           - "py" (finds .py files)
                           - "xml" (finds .xml files)
                           - "ts" (finds .ts files)
            path: Optional directory path filter to limit search scope. Examples:
                  - "src/main/java" (only search in this directory)
                  - "src/api" (only search in src/api)
                  - "tests" (only search in tests directory)
        
        Returns:
            Dict[str, Any]: Search results including:
            
            Success response structure:
            {
                "status": "success",
                "repo": "nodejs/node",
                "query": "EventEmitter",
                "filters": {
                    "file_extension": "js",
                    "path": "lib"
                },
                "total_count": 45,
                "returned_count": 20,
                "results": [
                    {
                        "name": "events.js",
                        "path": "lib/events.js",
                        "sha": "abc123",
                        "url": "https://github.com/nodejs/node/blob/main/lib/events.js",
                        "repository": "nodejs/node"
                    },
                    {
                        "name": "stream.js",
                        "path": "lib/stream.js",
                        "sha": "def456",
                        "url": "https://github.com/nodejs/node/blob/main/lib/stream.js",
                        "repository": "nodejs/node"
                    }
                ]
            }
            
            Error response structure:
            {
                "error": "Description of what went wrong",
                "error_type": "ValueError",
                "repo": "nodejs/node",
                "query": "EventEmitter"
            }
        
        Common Errors:
            - "GitHub token not found": Missing GITHUB_TOKEN or GITHUB_PAT secret
            - "Repository not found": Invalid repository name or no access
            - "Bad credentials": Invalid or expired GitHub token
            - "Validation Failed": Query syntax error or invalid filter
        
        Search Tips:
            - Be specific: Search for unique class/function names rather than common words
            - Use filters: Combine file_extension and path to narrow results
            - Case-insensitive: Searches ignore case by default
            - Exact matches: Use quotes for exact phrase matching: '"exact phrase"'
            - Boolean: Use "AND", "OR", "NOT" for complex queries
        
        Note:
            - Requires GITHUB_TOKEN or GITHUB_PAT secret with repo:read permissions
            - Results are limited to first 20 matches (total_count shows all matches)
            - Each result includes a direct URL to view the file on GitHub
            - File extension should NOT include the dot (use "java" not ".java")
            - Path filters should use forward slashes (Unix-style)
            - Search covers all branches but returns default branch URLs
            - Works with both public and private repositories (with proper access)
        """
        try:
            token = await secret_retriever.retrieve_optional_secret_value("GITHUB_TOKEN")
            if not token:
                token = await secret_retriever.retrieve_optional_secret_value("GITHUB_PAT")
            
            if not token:
                return {"error": "GitHub token not found. Required: GITHUB_TOKEN or GITHUB_PAT", 
                        "repo": repo, "query": query}
            
            repo_name = _parse_repo_identifier(repo)
            github = Github(token)
            
            search_query = f"{query} repo:{repo_name}"
            if file_extension: search_query += f" extension:{file_extension}"
            if path: search_query += f" path:{path}"
            
            results = github.search_code(query=search_query)
            items = [{"name": item.name, "path": item.path, "sha": item.sha, 
                     "url": item.html_url, "repository": item.repository.full_name} 
                    for item in list(results)[:20]]
            
            return {"status": "success", "repo": repo_name, "query": query,
                    "filters": {"file_extension": file_extension, "path": path},
                    "total_count": results.totalCount, "returned_count": len(items), "results": items}
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__, "repo": repo, "query": query}
    
    def sync_wrapper(repo: str, query: str, file_extension: Optional[str] = None, 
                    path: Optional[str] = None) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return run_async_in_sync_context(search_code_in_repo, repo, query, file_extension, path)
    
    sync_wrapper.__doc__ = search_code_in_repo.__doc__
    
    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=search_code_in_repo,
        name="search_code_in_repo",
        description=search_code_in_repo.__doc__ or "Search for code in a repository",
    )

# ============================================================================
# TOOL 5: File Content Extraction
# ============================================================================

def create_get_file_content_at_line_tool(secret_retriever: ISecretRetriever):
    """Factory function to create file content tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the AI agent invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching GitHub credentials
        
    Returns:
        Configured tool instance that AI agents can call with (repo, file_path, line_number, context_lines, branch)
    """
    async def get_file_content_at_line(repo: str, file_path: str, line_number: int, 
                                      context_lines: int = 5, branch: Optional[str] = None) -> Dict[str, Any]:
        """Get file content around a specific line with configurable context window.
        
        This tool retrieves the content of a file at a specific line number and includes
        surrounding lines for context. This is useful when you need to see the actual code
        at a particular location, understand what's around it, or analyze the implementation.
        
        Perfect for answering questions like:
        - "What does the code look like at line 42?"
        - "Show me the function definition at line 150"
        - "What's the context around line 200?"
        - "Display the code with 10 lines of context"
        
        The tool returns the target line clearly marked, along with the specified number of
        lines before and after it, with line numbers included for easy reference.
        
        Args:
            repo: Repository identifier. Can be either:
                  - "owner/repo" format (e.g., "django/django")
                  - Full GitHub URL (e.g., "https://github.com/django/django")
            file_path: Path to the file from repository root.
                       Example: "django/core/handlers/wsgi.py"
            line_number: The target line number to retrieve (1-indexed, first line = 1).
                        Must be a valid line number within the file.
            context_lines: Number of lines to include before AND after the target line.
                          Default is 5 (shows 5 lines before + target line + 5 lines after).
                          Examples:
                          - context_lines=5: Shows 11 total lines (5 before, 1 target, 5 after)
                          - context_lines=10: Shows 21 total lines
                          - context_lines=0: Shows only the target line
            branch: Optional branch name to read from. If not provided, defaults to the
                   'develop' branch.
        
        Returns:
            Dict[str, Any]: File content with context including:
            
            Success response structure:
            {
                "status": "success",
                "repo": "django/django",
                "file_path": "django/core/handlers/wsgi.py",
                "branch": "main",
                "line_number": 100,
                "target_line": "    def get_response(self, request):",
                "context": [
                    {
                        "line_number": 95,
                        "content": "    class WSGIHandler(base.BaseHandler):",
                        "is_target": false
                    },
                    {
                        "line_number": 96,
                        "content": "        request_class = WSGIRequest",
                        "is_target": false
                    },
                    ...
                    {
                        "line_number": 100,
                        "content": "    def get_response(self, request):",
                        "is_target": true
                    },
                    {
                        "line_number": 101,
                        "content": "        \"\"\"Return an HttpResponse object for the given HttpRequest.\"\"\"",
                        "is_target": false
                    },
                    ...
                ],
                "start_line": 95,
                "end_line": 105,
                "total_lines": 500,
                "language": "py",
                "size": 15234,
                "url": "https://github.com/django/django/blob/main/django/core/handlers/wsgi.py"
            }
            
            Error response structure:
            {
                "error": "Description of what went wrong",
                "error_type": "ValueError",
                "repo": "django/django",
                "file_path": "django/core/handlers/wsgi.py",
                "line_number": 100
            }
        
        Common Errors:
            - "GitHub token not found": Missing GITHUB_TOKEN or GITHUB_PAT secret
            - "File not found": The file_path doesn't exist in the repository
            - "Line number out of range": line_number is invalid (too high or less than 1)
            - "Repository not found": Invalid repository name or no access
            - "Branch not found": Specified branch doesn't exist
        
        Understanding the Response:
            - "target_line": The exact content of the line you requested
            - "context": Array of lines with line numbers, the target is marked with is_target=true
            - "start_line" and "end_line": The range of lines included in the response
            - "total_lines": Total number of lines in the entire file
            - "language": File extension (helps with syntax highlighting)
            - "url": Direct link to view this file on GitHub
        
        Note:
            - Requires GITHUB_TOKEN or GITHUB_PAT secret with repo:read permissions
            - Line numbers are 1-indexed (first line = 1, not 0)
            - Context window is automatically adjusted if near file start/end
            - Maximum context_lines is not limited, but large values may return lots of data
            - Binary files cannot be read (will return error)
            - Very large files (>100MB) may timeout
            - Works with both public and private repositories (with proper access)
        """
        try:
            token = await secret_retriever.retrieve_optional_secret_value("GITHUB_TOKEN")
            if not token:
                token = await secret_retriever.retrieve_optional_secret_value("GITHUB_PAT")
            
            if not token:
                return {"error": "GitHub token not found. Required: GITHUB_TOKEN or GITHUB_PAT", 
                        "repo": repo, "file_path": file_path, "line_number": line_number}
            
            repo_name = _parse_repo_identifier(repo)
            github = Github(token)
            repo_obj = github.get_repo(repo_name)
            
            # Use 'develop' branch if not specified
            if not branch:
                branch = "develop"
            
            file_content_obj = repo_obj.get_contents(file_path, ref=branch)
            content = file_content_obj.decoded_content.decode('utf-8')
            lines = content.split('\n')
            
            if line_number < 1 or line_number > len(lines):
                return {"error": f"Line number {line_number} is out of range (1-{len(lines)})",
                        "repo": repo_name, "file_path": file_path, "line_number": line_number, "total_lines": len(lines)}
            
            start_line = max(1, line_number - context_lines)
            end_line = min(len(lines), line_number + context_lines)
            
            context = [{"line_number": i + 1, "content": lines[i], "is_target": (i + 1) == line_number}
                      for i in range(start_line - 1, end_line)]
            
            return {
                "status": "success", "repo": repo_name, "file_path": file_path, "branch": branch,
                "line_number": line_number, "target_line": lines[line_number - 1].strip(),
                "context": context, "start_line": start_line, "end_line": end_line, "total_lines": len(lines),
                "language": file_path.split('.')[-1] if '.' in file_path else "unknown",
                "size": file_content_obj.size, "url": file_content_obj.html_url
            }
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__, 
                    "repo": repo, "file_path": file_path, "line_number": line_number}
    
    def sync_wrapper(repo: str, file_path: str, line_number: int, 
                    context_lines: int = 5, branch: Optional[str] = None) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return run_async_in_sync_context(get_file_content_at_line, repo, file_path, line_number, context_lines, branch)
    
    sync_wrapper.__doc__ = get_file_content_at_line.__doc__
    
    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_file_content_at_line,
        name="get_file_content_at_line",
        description=get_file_content_at_line.__doc__ or "Get file content at a specific line",
    )

# ============================================================================
# TOOL EXPORTS FOR LANGCHAIN INTEGRATION
# ============================================================================

__all__ = [
    "create_get_git_blame_for_line_tool",
    "create_get_commit_details_by_sha_tool",
    "create_get_pull_requests_for_commit_tool",
    "create_search_code_in_repo_tool",
    "create_get_file_content_at_line_tool"
]