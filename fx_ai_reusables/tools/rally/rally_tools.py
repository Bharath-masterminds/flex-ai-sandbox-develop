import asyncio
import certifi
import ssl

from typing import Dict, Any, Optional
from pyral import Rally
from langchain_core.tools import StructuredTool
from requests.exceptions import Timeout, ConnectionError

from fx_ai_reusables.environment_loading.interfaces.rally_config_reader_interface import IRallyConfigReader
from fx_ai_reusables.helpers.retry_decorator import retry_api_call


def _run_async(coroutine):
    """Helper to run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, we can't use run_until_complete
            raise RuntimeError("Cannot run async function in already running event loop")
        return loop.run_until_complete(coroutine)
    except RuntimeError:
        # Create new event loop if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()


# Helper functions
def _get_rally_connection(server: str, apikey: str, workspace: str, project: Optional[str] = None, verify_ssl: bool = True) -> Rally:
    """Initialize and return a Rally connection
    
    Args:
        server: Rally server URL
        apikey: Rally API key
        workspace: Rally workspace name
        project: Optional Rally project name
        verify_ssl: Whether to verify SSL certificates (default: True, can be overridden via RALLY_VERIFY_SSL config)
    
    Returns:
        Rally connection instance
    """
    # Prepare Rally connection parameters
    rally_params = {
        "server": server,
        "apikey": apikey,
        "workspace": workspace,
    }
    
    if project:
        rally_params["project"] = project
    
    if verify_ssl:
        cert_path = certifi.where()
        print(f"ℹ️ Using SSL verification with certificate bundle: {cert_path}")
        rally_params["verify_ssl_cert"] = True
        rally_params["ca_cert_file"] = cert_path
    else:
        print("⚠️ SSL verification disabled for Rally connection (set via RALLY_VERIFY_SSL config)")
        rally_params["verify_ssl_cert"] = False
    
    rally = Rally(**rally_params)
    rally.enableLogging()
    return rally


def create_fetch_rally_artifact_details_tool(rally_config_reader: IRallyConfigReader):
    """Factory function to create Rally artifact details fetcher tool.
    
    This tool fetches specific details (description, acceptance criteria and discussions)
    for a Rally artifact, filtering out images and focusing on textual content.
    
    Args:
        rally_config_reader: IRallyConfigReader instance for fetching all Rally settings
        
    Returns:
        StructuredTool: Configured tool that fetches artifact details
    """
    
    async def fetch_rally_artifact_details(artifact_id: str, project_name: str) -> Dict[str, Any]:
        """Fetch description, acceptance criteria, and discussion history for a Rally artifact.
        
        Retrieves content from a Rally User Story or Defect including the main
        description, acceptance criteria, and all discussion history.
        Images and attachments are excluded, focusing only on text-based information.
        
        This is useful for understanding the context, requirements, and conversation
        history around a specific work item without loading unnecessary binary data.
        
        Args:
            artifact_id: Rally FormattedID of the artifact to fetch
                        Format examples:
                        - "US12345" (User Story)
                        - "DE678" (Defect)
                        Case-insensitive, whitespace is trimmed
            project_name: Name of the Rally project
        
        Returns:
            Dict[str, Any]: Dictionary containing artifact textual details:
            {
                "artifact_id": "US12345",
                "name": "Implement user authentication",
                "artifact_type": "HierarchicalRequirement",
                "creation_date": "2024-01-10T08:30:00.000Z",
                "last_update_date": "2024-01-16T15:45:00.000Z",
                "description": "Full HTML/text description of the work item...",
                "acceptance_criteria": "Notes field containing acceptance criteria...",
                "discussion": [
                    {
                        "author": "John Doe",
                        "created_at": "2024-01-15T10:30:00.000Z",
                        "text": "This is a discussion comment..."
                    },
                    {
                        "author": "Jane Smith",
                        "created_at": "2024-01-16T14:20:00.000Z",
                        "text": "Response to previous comment..."
                    }
                ]
            }
        
        Raises:
            ValueError: If required Rally secrets are missing (RALLY_SERVER, RALLY_API_KEY, etc.)
            Exception: For Rally API errors (artifact not found, network issues, auth failures)
        
        Note:
            - Only fetches text content
            - Images in description/discussion are excluded from response
            - HTML tags in description are preserved as-is
            - Discussion items are returned in chronological order (oldest first)
            - Empty fields return empty strings, not None
            - Works with User Stories and Defects
            - Discussion/Conversation posts limited to text content only
        
        """
        # Fetch Rally config
        rally_config = await rally_config_reader.read_rally_config()
        apikey = rally_config.RALLY_API_KEY
        server = rally_config.RALLY_SERVER
        workspace = rally_config.RALLY_WORKSPACE
        verify_ssl = rally_config.RALLY_VERIFY_SSL
        
        # Extract retry configuration
        rally_retry_attempts = rally_config.RALLY_RETRY_ATTEMPTS
        rally_retry_delay = rally_config.RALLY_RETRY_DELAY
        rally_retry_backoff = rally_config.RALLY_RETRY_BACKOFF

        # Normalize artifact_id
        artifact_id = artifact_id.strip().upper()

        import ssl
        TRANSIENT_EXCEPTIONS = (Timeout, ConnectionError, ssl.SSLError)
        
        try:
            # Wrap Rally connection with retry logic
            @retry_api_call(
                max_retries=rally_retry_attempts,
                delay=rally_retry_delay,
                backoff=rally_retry_backoff,
                exceptions=TRANSIENT_EXCEPTIONS,
                verbose=True
            )
            def connect_to_rally():
                return _get_rally_connection(server, apikey, workspace, project_name, verify_ssl)
            
            rally = connect_to_rally()
            print(f"\n Fetching details for Rally artifact: {artifact_id}")
            
            # Determine artifact type from FormattedID prefix
            artifact_types_map = {
                "US": "HierarchicalRequirement",
                "DE": "Defect"
            }
            artifact_types = []
            for key, value in artifact_types_map.items():
                if artifact_id.startswith(key):
                    artifact_types = [value]
                    break
            if not artifact_types:
                artifact_types = list(set(artifact_types_map.values()))
            
            artifact = None
            artifact_type_found = None
            
            # Wrap artifact search with retry logic
            @retry_api_call(
                max_retries=rally_retry_attempts,
                delay=rally_retry_delay,
                backoff=rally_retry_backoff,
                exceptions=TRANSIENT_EXCEPTIONS,
                verbose=True
            )
            def search_artifact(artifact_type):
                query = f'(FormattedID = "{artifact_id}")'
                print(f"Searching in {artifact_type}...")
                
                response = rally.get(
                    artifact_type,
                    fetch='FormattedID,Name,Description,AcceptanceCriteria,Discussion,CreationDate,LastUpdateDate',
                    query=query,
                    limit=1
                )
                return response
            
            # Search for the artifact with retry
            for artifact_type in artifact_types:
                response = search_artifact(artifact_type)
                
                if response and response.resultCount > 0:
                    artifact = next(iter(response))
                    artifact_type_found = artifact_type
                    print(f" Found {artifact_type}: {artifact.Name}")
                    break
            
            if not artifact:
                error_msg = f"Artifact '{artifact_id}' not found in Rally workspace '{workspace}'"
                print(error_msg)
                return {
                    "error": error_msg,
                    "artifact_id": artifact_id,
                    "workspace": workspace
                }
            
            # Extract description, acceptance criteria, and timestamps
            description = getattr(artifact, 'Description', '') or ''
            acceptance_criteria = getattr(artifact, 'AcceptanceCriteria', '') or ''
            creation_date = str(getattr(artifact, 'CreationDate', '')) if getattr(artifact, 'CreationDate', None) else ''
            last_update_date = str(getattr(artifact, 'LastUpdateDate', '')) if getattr(artifact, 'LastUpdateDate', None) else ''
            
            # Wrap discussion fetch with retry logic
            discussion_list = []
            discussion_obj = getattr(artifact, 'Discussion', None)
            
            if discussion_obj:
                try:
                    @retry_api_call(
                        max_retries=rally_retry_attempts,
                        delay=rally_retry_delay,
                        backoff=rally_retry_backoff,
                        exceptions=TRANSIENT_EXCEPTIONS,
                        verbose=True
                    )
                    def fetch_discussion():
                        return rally.get(
                            'ConversationPost',
                            fetch='User,CreationDate,Text',
                            query=f'(Discussion = "{discussion_obj._ref}")',
                            order='CreationDate ASC',
                            pagesize=200
                        )
                    
                    discussion_posts = fetch_discussion()
                    
                    for post in discussion_posts:
                        post_text = getattr(post, 'Text', '') or ''
                        
                        # Get author info
                        user_obj = getattr(post, 'User', None)
                        author_name = "Unknown"
                        if user_obj and hasattr(user_obj, 'DisplayName'):
                            author_name = user_obj.DisplayName or "Unknown"
                        elif user_obj and hasattr(user_obj, '_refObjectName'):
                            author_name = user_obj._refObjectName or "Unknown"
                        
                        created_date = getattr(post, 'CreationDate', '') or ''
                        
                        if post_text.strip():
                            discussion_list.append({
                                "author": author_name,
                                "created_at": str(created_date),
                                "text": post_text
                            })
                    
                except Exception as disc_error:
                    print(f"Could not fetch discussion: {str(disc_error)}")
                    discussion_list = []
            
            # Build response
            result = {
                "artifact_id": artifact_id,
                "name": artifact.Name,
                "artifact_type": artifact_type_found,
                "creation_date": creation_date,
                "last_update_date": last_update_date,
                "description": description,
                "acceptance_criteria": acceptance_criteria,
                "discussion": discussion_list
            }
            
            print(f"\n Successfully fetched details for {artifact_id}")
            return result
            
        except ValueError as e:
            print(f" Validation error: {e}")
            raise
        except ssl.SSLError as ssl_err:
            error_msg = f"SSL certificate verification failed for Rally server. Error: {str(ssl_err)}"
            print(f"❌ {error_msg}")
            print(f"💡 Tip: Check your Rally server certificate or try disabling SSL verification in Rally connection settings")
            return {
                "error": error_msg,
                "artifact_id": artifact_id,
                "ssl_error": True
            }
        except Exception as e:
            error_msg = f"Error fetching artifact details for '{artifact_id}': {str(e)}"
            print(f"{error_msg}")
            return {
                "error": error_msg,
                "artifact_id": artifact_id
            }
        
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(artifact_id: str, project_name: str) -> Dict[str, Any]:
        """Synchronous wrapper for async artifact details fetch."""
        return _run_async(fetch_rally_artifact_details(artifact_id, project_name))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = fetch_rally_artifact_details.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=fetch_rally_artifact_details,  # Async version
        name="fetch_rally_artifact_details",
        description=(
            "Fetch description, acceptance criteria, and discussion history for a Rally artifact "
            "(User Story and Defect) by FormattedID and project name. "
            "Returns only text content, excluding images and attachments. "
            "Useful for understanding requirements, acceptance criteria, and conversation context around work items. "
            "Input: FormattedID (e.g., 'US12345', 'DE678') and project_name. "
            "Returns: Dictionary with description, acceptance_criteria, and discussion array."
        ),
    )
    return tool
