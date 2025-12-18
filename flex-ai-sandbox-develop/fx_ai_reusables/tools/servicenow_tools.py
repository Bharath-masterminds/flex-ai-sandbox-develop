import os
import asyncio
import requests
from langchain_core.tools import StructuredTool
from requests.auth import HTTPBasicAuth
from typing import Dict, Any, Optional
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


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


def create_get_incident_by_incident_number_tool(secret_retriever: ISecretRetriever):
    """Factory function to create ServiceNow incident retrieval tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the LLM invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching ServiceNow credentials
        
    Returns:
        Configured tool instance that the LLM can call with (incident_number, timeout)
    """
    async def get_incident_by_incident_number(incident_number: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Retrieve comprehensive incident details from ServiceNow by incident number.
        
        This function queries the ServiceNow incidents table using the REST API to fetch
        detailed information about a specific incident. It uses HTTP Basic Authentication
        and implements proper error handling for network issues and authentication failures.
        
        The function constructs a ServiceNow Table API query with the incident number as
        a filter parameter, limiting results to exactly one record for efficiency. It
        returns the complete incident record including all fields such as state, priority,
        description, assignment information, and timestamps.
        
        Authentication is handled via HTTP Basic Auth using ServiceNow username and password
        credentials fetched via the secret retriever. The function validates that all required
        credentials are present before making the API call.
        
        Args:
            incident_number: The ServiceNow incident number to search for.
            timeout: Request timeout in seconds. Defaults to 30.
        
        Returns:
            Optional[Dict[str, Any]]: Complete incident details dictionary if found, None otherwise.
        
        Raises:
            ValueError: If any required ServiceNow secrets are missing:
                       - SN_INSTANCE: ServiceNow instance name (without .service-now.com)
                       - SN_USERNAME: ServiceNow username for API access
                       - SN_PASSWORD: ServiceNow password for API access
            requests.exceptions.HTTPError: If the HTTP request fails due to:
                                          - 401: Invalid credentials
                                          - 403: Insufficient permissions
                                          - 404: Invalid instance or endpoint
                                          - 500: ServiceNow server error
            requests.exceptions.ConnectionError: If network connectivity issues occur
            requests.exceptions.Timeout: If the request exceeds the timeout duration
            requests.exceptions.RequestException: For other request-related errors
        
        Note:
            - Requires SN_INSTANCE, SN_USERNAME, and SN_PASSWORD secrets
            - The SN_INSTANCE should be just the instance name (e.g., 'dev12345'),
              not the full URL
            - Uses ServiceNow Table API v1 (api/now/table/incident)
            - Query parameter uses exact match on the 'number' field
            - Results are limited to 1 record for performance
            - All ServiceNow field names are returned as-is (use ServiceNow documentation
              for field reference)
            - Reference fields (like assigned_to) include both display_value and link
            - Date/time fields are in ServiceNow's internal format
        """
        # Fetch credentials via secret_retriever (from closure)
        instance = await secret_retriever.retrieve_optional_secret_value("SN_INSTANCE")
        username = await secret_retriever.retrieve_optional_secret_value("SN_USERNAME")
        password = await secret_retriever.retrieve_optional_secret_value("SN_PASSWORD")

        if not all([instance, username, password]):
            raise ValueError("ServiceNow credentials not found in secrets")
        
        # Type assertions after validation - we know these are not None
        assert username is not None
        assert password is not None
        assert instance is not None
        
        base_url = f"https://{instance}.service-now.com/api/now/table/incident"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        params = {
            "sysparm_query": f"number={incident_number}",
            "sysparm_limit": "1"
        }

        try:
            response = requests.get(
                base_url,
                headers=headers,
                params=params,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            result = data.get("result", [])
            
            if result:
                return result[0]
            else:
                return None
                
        except requests.exceptions.HTTPError as e:
            raise
        except requests.exceptions.Timeout as e:
            raise
        except requests.exceptions.ConnectionError as e:
            raise
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(incident_number: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Sync wrapper that runs the async function."""
        return _run_async(get_incident_by_incident_number(incident_number, timeout))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_incident_by_incident_number.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=get_incident_by_incident_number,  # Async version
        name="get_incident_by_incident_number",
        description=get_incident_by_incident_number.__doc__ or "Retrieve comprehensive incident details from ServiceNow",
    )
    return tool


def create_get_incident_attachments_tool(secret_retriever: ISecretRetriever):
    """Factory function to create ServiceNow attachment retrieval tool with injected secret retriever.
    
    This factory creates a tool that can list all attachments associated with a ServiceNow incident.
    It uses the sys_attachment table to retrieve metadata about attachments (filename, size, content type).
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching ServiceNow credentials
        
    Returns:
        Configured tool instance that the LLM can call with (incident_sys_id, timeout)
    """
    async def get_incident_attachments(incident_sys_id: str, timeout: int = 30) -> Optional[list[Dict[str, Any]]]:
        """Retrieve all attachment metadata for a ServiceNow incident.
        
        This function queries the ServiceNow sys_attachment table to get information about
        all files attached to a specific incident. It returns metadata including filename,
        file size, content type, and when the attachment was created.
        
        Note: This function returns attachment METADATA only (filenames, sizes, etc.).
        To download the actual file content, you need the attachment sys_id and would
        use a separate download function with the sys_attachment_doc table.
        
        Args:
            incident_sys_id: The ServiceNow sys_id (unique identifier) of the incident.
                            This is NOT the incident number (like INC0001234), but the
                            internal sys_id GUID that you get from incident details.
            timeout: Request timeout in seconds. Defaults to 30.
        
        Returns:
            Optional[list[Dict[str, Any]]]: List of attachment metadata dictionaries, or None if error.
            Each dictionary contains:
                - sys_id: Unique ID of the attachment
                - file_name: Name of the attached file
                - size_bytes: File size in bytes
                - content_type: MIME type (e.g., 'image/png', 'application/pdf')
                - created_on: Timestamp when attachment was added
                - created_by: User who added the attachment
        
        Raises:
            ValueError: If any required ServiceNow secrets are missing
            requests.exceptions.HTTPError: If the HTTP request fails
            requests.exceptions.ConnectionError: If network connectivity issues occur
            requests.exceptions.Timeout: If the request exceeds the timeout duration
        
        Note:
            - Requires the incident's sys_id, not the incident number
            - Use get_incident_by_incident_number first to get the sys_id from incident number
            - Returns empty list if incident has no attachments
            - Does NOT download actual file content (only metadata)
        """
        # Fetch credentials via secret_retriever (from closure)
        instance = await secret_retriever.retrieve_optional_secret_value("SN_INSTANCE")
        username = await secret_retriever.retrieve_optional_secret_value("SN_USERNAME")
        password = await secret_retriever.retrieve_optional_secret_value("SN_PASSWORD")

        if not all([instance, username, password]):
            raise ValueError("ServiceNow credentials not found in secrets")
        
        # Type assertions after validation
        assert username is not None
        assert password is not None
        assert instance is not None
        
        base_url = f"https://{instance}.service-now.com/api/now/table/sys_attachment"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        params = {
            "sysparm_query": f"table_name=incident^table_sys_id={incident_sys_id}",
            "sysparm_fields": "sys_id,file_name,size_bytes,content_type,created_on,created_by"
        }

        try:
            response = requests.get(
                base_url,
                headers=headers,
                params=params,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            result = data.get("result", [])
            
            return result if result else []
                
        except requests.exceptions.HTTPError as e:
            raise
        except requests.exceptions.Timeout as e:
            raise
        except requests.exceptions.ConnectionError as e:
            raise
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(incident_sys_id: str, timeout: int = 30) -> Optional[list[Dict[str, Any]]]:
        """Sync wrapper that runs the async function."""
        return _run_async(get_incident_attachments(incident_sys_id, timeout))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_incident_attachments.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_incident_attachments,
        name="get_incident_attachments",
        description=get_incident_attachments.__doc__ or "Retrieve attachment metadata from ServiceNow incident",
    )
    return tool


def create_download_attachment_tool(secret_retriever: ISecretRetriever):
    """Factory function to create ServiceNow attachment download tool with injected secret retriever.
    
    This factory creates a tool that can download the actual file content of a ServiceNow attachment.
    Use this after getting attachment metadata from get_incident_attachments.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching ServiceNow credentials
        
    Returns:
        Configured tool instance that the LLM can call with (attachment_sys_id, timeout)
    """
    async def download_attachment(attachment_sys_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Download the actual file content of a ServiceNow attachment and save it to disk.
        
        This function downloads the binary content of an attachment from ServiceNow,
        saves it to the 'downloads' directory, and returns metadata about the download.
        
        Args:
            attachment_sys_id: The sys_id of the attachment to download.
                              Get this from get_incident_attachments.
            timeout: Request timeout in seconds. Defaults to 30.
        
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing:
                - file_name: Name of the file
                - content_type: MIME type
                - size_bytes: File size
                - saved_path: Absolute path where file was saved
                - status: "success" or "failed"
            Returns None if attachment not found.
        
        Raises:
            ValueError: If any required ServiceNow secrets are missing
            requests.exceptions.HTTPError: If the HTTP request fails
            requests.exceptions.ConnectionError: If network connectivity issues occur
            requests.exceptions.Timeout: If the request exceeds the timeout duration
        
        Note:
            - Files are saved to the 'downloads' directory in the workspace root
            - The directory is created automatically if it doesn't exist
            - For large files, this may take time
        """
        import base64
        import os
        from pathlib import Path
        
        # Fetch credentials via secret_retriever (from closure)
        instance = await secret_retriever.retrieve_optional_secret_value("SN_INSTANCE")
        username = await secret_retriever.retrieve_optional_secret_value("SN_USERNAME")
        password = await secret_retriever.retrieve_optional_secret_value("SN_PASSWORD")

        if not all([instance, username, password]):
            raise ValueError("ServiceNow credentials not found in secrets")
        
        # Type assertions after validation
        assert username is not None
        assert password is not None
        assert instance is not None
        
        # First get the attachment metadata
        metadata_url = f"https://{instance}.service-now.com/api/now/table/sys_attachment/{attachment_sys_id}"
        headers = {
            "Accept": "application/json"
        }

        try:
            # Get metadata
            metadata_response = requests.get(
                metadata_url,
                headers=headers,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout
            )
            metadata_response.raise_for_status()
            
            metadata = metadata_response.json().get("result", {})
            
            if not metadata:
                return None
            
            # Download actual file content
            download_url = f"https://{instance}.service-now.com/api/now/attachment/{attachment_sys_id}/file"
            
            file_response = requests.get(
                download_url,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout
            )
            file_response.raise_for_status()
            
            # Create downloads directory if it doesn't exist
            downloads_dir = Path("downloads")
            downloads_dir.mkdir(exist_ok=True)
            
            # Save file to downloads directory
            file_name = metadata.get("file_name", f"attachment_{attachment_sys_id}")
            file_path = downloads_dir / file_name
            
            try:
                # Write binary content to file
                with open(file_path, 'wb') as f:
                    f.write(file_response.content)
                
                return {
                    "file_name": file_name,
                    "content_type": metadata.get("content_type"),
                    "size_bytes": metadata.get("size_bytes"),
                    "saved_path": str(file_path.absolute()),
                    "status": "success"
                }
            except Exception as e:
                return {
                    "file_name": file_name,
                    "content_type": metadata.get("content_type"),
                    "size_bytes": metadata.get("size_bytes"),
                    "saved_path": "",
                    "status": f"failed: {str(e)}"
                }
                
        except requests.exceptions.HTTPError as e:
            raise
        except requests.exceptions.Timeout as e:
            raise
        except requests.exceptions.ConnectionError as e:
            raise
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(attachment_sys_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Sync wrapper that runs the async function."""
        return _run_async(download_attachment(attachment_sys_id, timeout))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = download_attachment.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=download_attachment,
        name="download_attachment",
        description=download_attachment.__doc__ or "Download file content from ServiceNow attachment",
    )
    return tool


def create_get_incidents_by_timeframe_tool(secret_retriever: ISecretRetriever):
    """Factory function to create ServiceNow incident retrieval tool for a specific timeframe.
    
    This factory creates a tool that can retrieve all incidents created within a specified
    time range. Useful for getting all tickets created during a specific period.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching ServiceNow credentials
        
    Returns:
        Configured tool instance that the LLM can call with (start_time, end_time, timeout)
    """
    async def get_incidents_by_timeframe(start_time: str, end_time: str, timeout: int = 30) -> Optional[list[Dict[str, Any]]]:
        """Retrieve all incidents created within a specific timeframe from ServiceNow.
        
        This function queries the ServiceNow incidents table to fetch all incidents
        created between the specified start and end times. It's useful for analyzing
        incidents during a specific period, such as during an outage or maintenance window.
        
        The function uses ServiceNow's encoded query syntax to filter incidents by
        their creation timestamp (sys_created_on field). It returns a list of all
        matching incidents with their complete details.
        
        Args:
            start_time: Start of the time range in ServiceNow format.
                       Required format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDT HH:MM:SS"
                       Example: "2025-11-12 12:00:00"
                       
            end_time: End of the time range in ServiceNow format.
                     Required format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDT HH:MM:SS"
                     Example: "2025-11-12 13:00:00"
                     
            timeout: Request timeout in seconds. Defaults to 30.
        
        Returns:
            Optional[list[Dict[str, Any]]]: List of incident dictionaries if found, empty list if none found.
            Each incident dictionary contains all standard ServiceNow incident fields:
                - sys_id: Unique identifier
                - number: Incident number (e.g., INC0010001)
                - short_description: Brief description
                - description: Full description
                - state: Incident state
                - priority: Priority level
                - sys_created_on: Creation timestamp
                - sys_updated_on: Last update timestamp
                - assigned_to: Assigned user
                - assignment_group: Assigned group
                - And all other incident table fields
        
        Raises:
            ValueError: If any required ServiceNow secrets are missing:
                       - SN_INSTANCE: ServiceNow instance name (without .service-now.com)
                       - SN_USERNAME: ServiceNow username for API access
                       - SN_PASSWORD: ServiceNow password for API access
            requests.exceptions.HTTPError: If the HTTP request fails due to:
                                          - 401: Invalid credentials
                                          - 403: Insufficient permissions
                                          - 404: Invalid instance or endpoint
                                          - 500: ServiceNow server error
            requests.exceptions.ConnectionError: If network connectivity issues occur
            requests.exceptions.Timeout: If the request exceeds the timeout duration
        
        Examples:
            # Get incidents created between 12:00 PM and 1:00 PM on Nov 12, 2025
            incidents = await get_incidents_by_timeframe(
                "2025-11-12 12:00:00",
                "2025-11-12 13:00:00"
            )
            
            # Get incidents created during November 12, 2025
            incidents = await get_incidents_by_timeframe(
                "2025-11-12 00:00:00",
                "2025-11-12 23:59:59"
            )
        
        Note:
            - Requires SN_INSTANCE, SN_USERNAME, and SN_PASSWORD secrets
            - Times are typically in the ServiceNow instance's timezone
            - The query uses sys_created_on field for filtering
            - Results are ordered by creation time (newest first)
            - Consider using pagination for large result sets (this returns all matches)
            - Maximum results returned is 10000 by default (ServiceNow limit)
            - For more than 10000 results, you'll need to implement pagination
        """
        
        # Fetch credentials via secret_retriever (from closure)
        instance = await secret_retriever.retrieve_optional_secret_value("SN_INSTANCE")
        username = await secret_retriever.retrieve_optional_secret_value("SN_USERNAME")
        password = await secret_retriever.retrieve_optional_secret_value("SN_PASSWORD")

        if not all([instance, username, password]):
            raise ValueError("ServiceNow credentials not found in secrets")
        
        # Type assertions after validation
        assert username is not None
        assert password is not None
        assert instance is not None
        
        base_url = f"https://{instance}.service-now.com/api/now/table/incident"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Build the query to filter by time range
        # sys_created_on >= start_time AND sys_created_on <= end_time
        query = f"sys_created_onBETWEENjavascript:gs.dateGenerate('{start_time}')@javascript:gs.dateGenerate('{end_time}')"
        
        params = {
            "sysparm_query": query,
            "sysparm_order_by": "sys_created_on",
            "sysparm_order": "DESC"  # Most recent first
        }

        try:
            response = requests.get(
                base_url,
                headers=headers,
                params=params,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            result = data.get("result", [])
            
            return result if result else []
                
        except requests.exceptions.HTTPError as e:
            raise
        except requests.exceptions.Timeout as e:
            raise
        except requests.exceptions.ConnectionError as e:
            raise
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(start_time: str, end_time: str, timeout: int = 30) -> Optional[list[Dict[str, Any]]]:
        """Sync wrapper that runs the async function."""
        return _run_async(get_incidents_by_timeframe(start_time, end_time, timeout))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_incidents_by_timeframe.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_incidents_by_timeframe,
        name="get_incidents_by_timeframe",
        description=get_incidents_by_timeframe.__doc__ or "Retrieve all incidents created within a specific timeframe from ServiceNow",
    )
    return tool


def create_get_incidents_by_assignment_group_tool(secret_retriever: ISecretRetriever):
    """Factory function to create ServiceNow incident retrieval tool filtered by assignment group.
    
    This factory creates a tool that can retrieve all incidents assigned to a specific
    assignment group. Useful for getting team-specific tickets.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching ServiceNow credentials
        
    Returns:
        Configured tool instance that the LLM can call with (assignment_group_name, start_time, end_time, timeout)
    """
    async def get_incidents_by_assignment_group(
        assignment_group_name: str, 
        start_time: str = None, 
        end_time: str = None, 
        timeout: int = 30
    ) -> Optional[list[Dict[str, Any]]]:
        """Retrieve all incidents assigned to a specific assignment group from ServiceNow.
        
        This function queries the ServiceNow incidents table to fetch all incidents
        assigned to a specific assignment group, optionally filtered by time range.
        
        Args:
            assignment_group_name: Name of the assignment group (e.g., "FLEX_RagingFHIR - SPT")
            start_time: Optional start of time range in ServiceNow format.
                       Format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDT HH:MM:SS"
                       Example: "2025-11-12 12:00:00"
                       If not provided, retrieves all incidents regardless of creation time.
            end_time: Optional end of time range in ServiceNow format.
                     Format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDT HH:MM:SS"
                     Example: "2025-11-12 13:00:00"
                     Required if start_time is provided.
            timeout: Request timeout in seconds. Defaults to 30.
        
        Returns:
            Optional[list[Dict[str, Any]]]: List of incident dictionaries matching the assignment group.
            Each incident contains all standard ServiceNow fields including:
                - sys_id: Unique identifier
                - number: Incident number (e.g., INC0010001)
                - short_description: Brief description
                - description: Full description
                - state: Incident state
                - priority: Priority level
                - assignment_group: The assignment group details
                - sys_created_on: Creation timestamp
                - And all other incident table fields
        
        Raises:
            ValueError: If required ServiceNow secrets are missing
            requests.exceptions.HTTPError: If the HTTP request fails
            requests.exceptions.ConnectionError: If network connectivity issues occur
            requests.exceptions.Timeout: If request exceeds timeout duration
        
        Examples:
            # Get all incidents for FLEX_RagingFHIR - SPT
            incidents = await get_incidents_by_assignment_group("FLEX_RagingFHIR - SPT")
            
            # Get incidents between specific dates for the group
            incidents = await get_incidents_by_assignment_group(
                "FLEX_RagingFHIR - SPT",
                "2025-11-12 00:00:00",
                "2025-11-12 23:59:59"
            )
            
            # Get incidents from November 1-15 for the group
            incidents = await get_incidents_by_assignment_group(
                "FLEX_RagingFHIR - SPT",
                "2025-11-01 00:00:00",
                "2025-11-15 23:59:59"
            )
        
        Note:
            - Assignment group name matching is case-sensitive and uses CONTAINS
            - Returns empty list if no incidents found for the group
            - Time filtering is optional - omit start_time to get all incidents
            - If start_time is provided, end_time is also required
            - Results ordered by creation time (newest first)
        """
        
        # Fetch credentials
        instance = await secret_retriever.retrieve_optional_secret_value("SN_INSTANCE")
        username = await secret_retriever.retrieve_optional_secret_value("SN_USERNAME")
        password = await secret_retriever.retrieve_optional_secret_value("SN_PASSWORD")

        if not all([instance, username, password]):
            raise ValueError("ServiceNow credentials not found in secrets")
        
        # Type assertions after validation
        assert username is not None
        assert password is not None
        assert instance is not None
        
        base_url = f"https://{instance}.service-now.com/api/now/table/incident"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Build query: assignment_group.name CONTAINS assignment_group_name
        query_parts = [f"assignment_group.nameLIKE{assignment_group_name}"]
        
        # Add time range filter if provided
        if start_time and end_time:
            time_query = f"sys_created_onBETWEENjavascript:gs.dateGenerate('{start_time}')@javascript:gs.dateGenerate('{end_time}')"
            query_parts.append(time_query)
        
        # Combine query parts with AND (^)
        query = "^".join(query_parts)
        
        params = {
            "sysparm_query": query,
            "sysparm_order_by": "sys_created_on",
            "sysparm_order": "DESC"  # Most recent first
        }

        try:
            response = requests.get(
                base_url,
                headers=headers,
                params=params,
                auth=HTTPBasicAuth(username, password),
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            result = data.get("result", [])
            
            return result if result else []
                
        except requests.exceptions.HTTPError as e:
            raise
        except requests.exceptions.Timeout as e:
            raise
        except requests.exceptions.ConnectionError as e:
            raise
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(
        assignment_group_name: str, 
        start_time: str = None, 
        end_time: str = None, 
        timeout: int = 30
    ) -> Optional[list[Dict[str, Any]]]:
        """Sync wrapper that runs the async function."""
        return _run_async(get_incidents_by_assignment_group(assignment_group_name, start_time, end_time, timeout))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_incidents_by_assignment_group.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_incidents_by_assignment_group,
        name="get_incidents_by_assignment_group",
        description=get_incidents_by_assignment_group.__doc__ or "Retrieve incidents assigned to a specific assignment group from ServiceNow",
    )
    return tool
