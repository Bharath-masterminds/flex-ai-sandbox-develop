import asyncio
from datetime import datetime, timedelta
import json
from langchain_core.tools import StructuredTool
from typing import Dict, Any, List, Optional, Union
from azure.monitor.query import LogsQueryClient, LogsQueryStatus, MetricsQueryClient
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


def _run_async(coroutine):
    """Helper to run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("Cannot run async function in already running event loop")
        return loop.run_until_complete(coroutine)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()


def _get_credential(tenant_id: Optional[str], client_id: Optional[str], client_secret: Optional[str]):
    """Helper to get Azure credential."""
    if client_id and client_secret and tenant_id:
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        return DefaultAzureCredential()


def _format_datetime(dt):
    """Helper to format datetime objects for JSON serialization."""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt


def _col_name(col) -> str:
    """Return the column name, whether `col` has a `name` attribute or is a string-like object."""
    return getattr(col, 'name', str(col))


def create_get_app_insights_operation_id_using_url_tool(secret_retriever: ISecretRetriever):
    """Factory function to create app insights operation ID tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the LLM invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching Azure credentials
        
    Returns:
        Configured tool instance that the LLM can call with (requesturl, start_date, end_date)
    """
    async def get_app_insights_operation_id_using_url(requesturl: str, start_date: str, end_date: str) -> list:
        """Retrieve Azure Application Insights operation IDs for failed requests matching a specific URL.
        
        This function queries Azure Application Insights to find operation IDs associated with
        HTTP 500 error responses for a specific URL within a given time range. Operation IDs
        are essential for correlating related log entries across different telemetry types
        (requests, exceptions, traces, etc.).
        
        The function uses Kusto Query Language (KQL) to filter the 'requests' table for:
        - Failed requests (resultCode == 500)
        - Matching the specified URL
        - Within the specified time range
        - Ordered by timestamp (most recent first)
        
        Authentication is handled via Azure Service Principal credentials if available,
        otherwise falls back to DefaultAzureCredential.
        
        Args:
            requesturl: The exact URL to search for in Application Insights logs.
            start_date: Start of the time range in ISO 8601 format with timezone.
            end_date: End of the time range in ISO 8601 format with timezone.
        
        Returns:
            list: List of operation ID strings if successful, or dict with error info if failed.
                  Success example: ["abc123def456", "ghi789jkl012"]
                  Error example: {"error": "Query failed: PartialError"}
        
        Raises:
            Exception: Captured and returned as error dict. Common causes include:
                      - Missing or invalid Azure credentials
                      - Network connectivity issues
                      - Invalid KQL query syntax
                      - Resource access permissions
        
        Note:
            - The function specifically filters for HTTP 500 errors only
            - Requires AZURE_APP_RESOURCE secret for the resource ID
            - Uses either Service Principal auth (AZURE_TENANT_ID, AZURE_CLIENT_ID, 
              AZURE_CLIENT_SECRET) or DefaultAzureCredential
        """
        # Initialize connection - fetch credentials via secret_retriever (from closure)
        tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
        client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
        client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
        
        if client_id and client_secret and tenant_id:
            # Use Service Principal authentication
            from azure.identity import ClientSecretCredential
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            # Use Default Azure credentials
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()


        # Initialize logs client
        
        logs_client = LogsQueryClient(credential=credential)
        resource_id = await secret_retriever.retrieve_optional_secret_value("AZURE_APP_RESOURCE")
        
        # Prepare KQL query
        
        query = f"""
            requests
            | where timestamp > datetime("{start_date}") and timestamp < datetime("{end_date}")
            | where url in ("{requesturl}")
            | where resultCode == 500
            | order by timestamp desc
            | project operation_Id
            """


        # Execute query


        try:
            response = logs_client.query_resource(resource_id, query, timespan=None)


            # Process results


            if response.status == LogsQueryStatus.SUCCESS:
                # Process query results
                
                results = []
                total_rows = 0
                for table in response.tables:
                    total_rows += len(table.rows)
                    for row in table.rows:
                        results.append(row[0])
                
                # Validate and deduplicate operation IDs
                
                # Remove duplicates while preserving order
                unique_results = list(dict.fromkeys(results))
                
                # Prepare for correlation
                
                # Success with detailed summary
                return unique_results


            else:
                # Query failed
                return {"error": f"Query failed: {response.status}"}
        except Exception as e:
            error_msg = f"Error retrieving operation IDs: {str(e)}"
            return {"error": error_msg}
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(requesturl: str, start_date: str, end_date: str) -> list:
        """Sync wrapper that runs the async function."""
        return _run_async(get_app_insights_operation_id_using_url(requesturl, start_date, end_date))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_app_insights_operation_id_using_url.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=get_app_insights_operation_id_using_url,  # Async version
        name="get_app_insights_operation_id_using_url",
        description=get_app_insights_operation_id_using_url.__doc__ or "Retrieve Azure Application Insights operation IDs for failed requests",
    )
    return tool


def create_get_app_insights_logs_using_operation_id_tool(secret_retriever: ISecretRetriever):
    """Factory function to create app insights logs tool with injected secret retriever.
    
    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the LLM invokes the tool.
    
    Args:
        secret_retriever: ISecretRetriever instance for fetching Azure credentials
        
    Returns:
        Configured tool instance that the LLM can call with (operation_id, start_date, end_date)
    """
    async def get_app_insights_logs_using_operation_id(operation_id: str, start_date: str, end_date: str):
        """Retrieve comprehensive log data from Azure Application Insights using an operation ID.
        
        This function performs a unified query across multiple Azure Application Insights
        telemetry tables (requests, exceptions, customEvents, availabilityResults) to
        gather all log entries associated with a specific operation ID. This provides
        a complete view of what happened during a particular operation, including any
        errors, custom events, and performance data.
        
        The function uses a KQL union query with 'isfuzzy=true' to combine data from
        different telemetry types, filters by operation ID and time range, then formats
        the results into structured dictionaries for easy analysis.
        
        Authentication follows the same pattern as the operation ID retrieval function,
        using Service Principal credentials when available or DefaultAzureCredential.
        
        Args:
            operation_id: The operation ID to search for across all telemetry tables.
            start_date: Start of the time range in ISO 8601 format with timezone.
            end_date: End of the time range in ISO 8601 format with timezone.
        
        Returns:
            list: List of dictionaries containing log entries if successful, or string with
                  error message if failed. Each dictionary contains:
                  - customDimensions: Custom properties and metadata
                  - details: Detailed information about the log entry
                  - innermostMessage: Core error or event message
                  - innermostType: Type of the innermost exception or event
                  
                  Success example:
                  [
                      {
                          "customDimensions": {"userId": "12345", "feature": "payment"},
                          "details": {"stackTrace": "...", "errorCode": "500"},
                          "innermostMessage": "Database connection timeout",
                          "innermostType": "SqlException"
                      },
                      {...}
                  ]
                  
                  Error example: "Query failed: PartialError"
        
        Raises:
            Exception: Captured and returned as error string. Common causes include:
                      - Invalid operation ID format
                      - Network connectivity issues
                      - Authentication failures
                      - Resource access permissions
                      - KQL query syntax errors
        
        Note:
            - The 'isfuzzy=true' union allows the query to succeed even if some tables
              don't contain the operation ID
            - Results are ordered by timestamp (most recent first)
            - The function queries multiple telemetry types for comprehensive coverage
            - Requires the same Azure secrets as the operation ID function
            - Time range should be wide enough to capture all related log entries
        """
        # Initialize for comprehensive log analysis


        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)


        def format_log_entry(log_entry):


            # Create a new dictionary with all the log entry data
            formatted_entry = {
                "timestamp": log_entry.get('timestamp', ''),
                "operation_id": log_entry.get('operation_Id', ''),
                "message": log_entry.get('message', ''),
                "severity_level": log_entry.get('severityLevel', ''),
                "item_type": log_entry.get('itemType', ''),
                "custom_dimensions": log_entry.get('customDimensions', {})
            }


            # Add exception-specific fields if they exist
            if log_entry.get('itemType') == 'exception':
                formatted_entry["exception"] = {
                    "problem_id": log_entry.get('problemId', ''),
                    "type": log_entry.get('type', ''),
                    "method": log_entry.get('method', ''),
                    "outer_message": log_entry.get('outerMessage', ''),
                    "details": log_entry.get('details', {})
                }


            # Return as formatted JSON string with indentation for readability
            return json.dumps(formatted_entry, indent=2, cls=DateTimeEncoder)


        # Initialize authentication - fetch credentials via secret_retriever (from closure)
        
        tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
        client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
        client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
        
        if client_id and client_secret and tenant_id:
            # Use Service Principal authentication
            from azure.identity import ClientSecretCredential
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            # Use Default Azure credentials
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()


        # Initialize logs client
        logs_client = LogsQueryClient(credential=credential)
        resource_id = await secret_retriever.retrieve_optional_secret_value("AZURE_APP_RESOURCE")
        
        # Prepare comprehensive query
        
        query = f"""
        union isfuzzy=true requests, exceptions, customEvents, availabilityResults
        | where timestamp > datetime("{start_date}") and timestamp < datetime("{end_date}")
        | where operation_Id has "{operation_id}"
        | order by timestamp desc
        | project customDimensions, details, innermostMessage, innermostType
        """


        # Execute comprehensive query


        try:
            response = logs_client.query_resource(resource_id, query, timespan=None)


            # Process comprehensive results


            if response.status == LogsQueryStatus.SUCCESS:
                # Process telemetry data
                
                results = []
                telemetry_counts = {"requests": 0, "exceptions": 0, "customEvents": 0, "availabilityResults": 0}
                
                for table in response.tables:
                    for row in table.rows:
                        log_entry = dict(zip(table.columns, row))
                        results.append(log_entry)
                        
                        # Count telemetry types for detailed analysis
                        if "itemType" in log_entry:
                            item_type = log_entry.get("itemType", "unknown")
                            if item_type in telemetry_counts:
                                telemetry_counts[item_type] += 1
                
                # Analyze log patterns
                
                # Analyze error patterns
                error_count = sum(1 for entry in results if "exception" in str(entry).lower() or "error" in str(entry).lower())
                
                # Correlate timeline
                
                # Prepare analysis summary
                
                # Success with comprehensive details
                telemetry_summary = ", ".join([f"{count} {type_name}" for type_name, count in telemetry_counts.items() if count > 0])
                return results


            else:
                # Comprehensive query failed
                return f"Query failed: {response.status}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(operation_id: str, start_date: str, end_date: str):
        """Sync wrapper that runs the async function."""
        return _run_async(get_app_insights_logs_using_operation_id(operation_id, start_date, end_date))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_app_insights_logs_using_operation_id.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=get_app_insights_logs_using_operation_id,  # Async version
        name="get_app_insights_logs_using_operation_id",
        description=get_app_insights_logs_using_operation_id.__doc__ or "Retrieve comprehensive log data from Azure Application Insights",
    )
    return tool

def create_search_requests_by_criteria_tool(secret_retriever: ISecretRetriever):
    """Factory function to create flexible request search tool with injected secret retriever."""
    
    async def search_requests_by_criteria(
        url_pattern: Optional[str] = None,
        status_code: Optional[int] = None,
        method: Optional[str] = None,
        min_duration_ms: Optional[int] = None,
        max_duration_ms: Optional[int] = None,
        start_date: str = None,
        end_date: str = None,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """Search Application Insights requests by multiple criteria for flexible investigation.
        
        This tool provides flexible request searching capabilities beyond specific URL lookup.
        It allows combining multiple search criteria to find requests of interest during RCA.
        Results include operation IDs for detailed investigation with other tools.
        
        Use this tool for:
        - Initial investigation when you have partial information
        - Finding patterns in failures (e.g., all slow requests, all 5xx errors)
        - Discovering which endpoints are affected
        - Getting operation IDs for detailed trace analysis
        
        Args:
            url_pattern: Optional substring to match in request URLs (case-insensitive).
                        Example: "/api/payment" matches "/api/payment/process", "/api/payment/status"
            status_code: Optional HTTP status code to filter by.
                        Example: 500 for server errors, 404 for not found
            method: Optional HTTP method to filter by.
                   Example: "GET", "POST", "PUT", "DELETE"
            min_duration_ms: Optional minimum request duration in milliseconds.
                            Example: 1000 for requests taking more than 1 second
            max_duration_ms: Optional maximum request duration in milliseconds.
            start_date: Start time in ISO 8601 format. Defaults to 1 hour ago if not provided.
            end_date: End time in ISO 8601 format. Defaults to now if not provided.
            max_results: Maximum number of results to return (default 100).
        
        Returns:
            Dict[str, Any]: Dictionary containing search results and summary.
            
            Success example:
            {
                "requests": [
                    {
                        "timestamp": "2024-01-15T10:30:00Z",
                        "operation_id": "abc123",
                        "url": "/api/payment/process",
                        "method": "POST",
                        "status_code": 500,
                        "duration_ms": 2500,
                        "success": false,
                        "name": "POST /api/payment/process",
                        "custom_dimensions": {...}
                    }
                ],
                "total_found": 45,
                "summary": {
                    "avg_duration_ms": 2300,
                    "failure_rate": 0.85,
                    "status_code_breakdown": {"500": 40, "502": 5}
                },
                "search_criteria": {...},
                "time_range": {"from": "...", "to": "..."},
                "status": "success"
            }
            
            Error example:
            {
                "error": "Query failed: Invalid KQL syntax",
                "error_type": "QueryError",
                "search_criteria": {...}
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Set default time range
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
            if not end_date:
                end_date = datetime.utcnow().isoformat() + "Z"
            
            # Build dynamic KQL query
            query_parts = ["requests"]
            query_parts.append(f"| where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')")
            
            if url_pattern:
                query_parts.append(f"| where url contains '{url_pattern}'")
            if status_code:
                query_parts.append(f"| where resultCode == {status_code}")
            
            # Extract method from name field if method filter is specified
            # In Application Insights, the method is typically part of the 'name' field (e.g., "POST /api/endpoint")
            if method:
                query_parts.append(f"| where name startswith '{method} '")
            
            if min_duration_ms:
                query_parts.append(f"| where duration >= {min_duration_ms}")
            if max_duration_ms:
                query_parts.append(f"| where duration <= {max_duration_ms}")
            
            # Extract method from name field for all results
            query_parts.append("| extend method = tostring(split(name, ' ')[0])")
            query_parts.append("| project timestamp, operation_Id, url, method, resultCode, duration, success, name, customDimensions")
            query_parts.append(f"| order by timestamp desc")
            query_parts.append(f"| limit {max_results}")
            
            query = "\n".join(query_parts)
            
            # Execute query
            response = logs_client.query_resource(resource_id, query, timespan=None)
            
            if response.status == LogsQueryStatus.SUCCESS:
                requests = []
                status_code_breakdown = {}
                total_duration = 0
                failed_count = 0
                
                for table in response.tables:
                    for row in table.rows:
                        request_data = dict(zip([_col_name(col) for col in table.columns], row))
                        
                        # Format the request data
                        formatted_request = {
                            "timestamp": _format_datetime(request_data.get("timestamp")),
                            "operation_id": request_data.get("operation_Id"),
                            "url": request_data.get("url"),
                            "method": request_data.get("method", "UNKNOWN"),
                            "status_code": request_data.get("resultCode"),
                            "duration_ms": request_data.get("duration"),
                            "success": request_data.get("success"),
                            "name": request_data.get("name"),
                            "custom_dimensions": request_data.get("customDimensions", {})
                        }
                        requests.append(formatted_request)
                        
                        # Collect summary statistics
                        status_code = str(request_data.get("resultCode", "unknown"))
                        status_code_breakdown[status_code] = status_code_breakdown.get(status_code, 0) + 1
                        
                        if request_data.get("duration"):
                            total_duration += request_data.get("duration")
                        
                        if not request_data.get("success", True):
                            failed_count += 1
                
                # Calculate summary
                summary = {
                    "avg_duration_ms": round(total_duration / len(requests)) if requests else 0,
                    "failure_rate": round(failed_count / len(requests), 2) if requests else 0,
                    "status_code_breakdown": status_code_breakdown
                }
                
                return {
                    "requests": requests,
                    "total_found": len(requests),
                    "summary": summary,
                    "search_criteria": {
                        "url_pattern": url_pattern,
                        "status_code": status_code,
                        "method": method,
                        "min_duration_ms": min_duration_ms,
                        "max_duration_ms": max_duration_ms
                    },
                    "time_range": {"from": start_date, "to": end_date},
                    "status": "success"
                }
            else:
                return {
                    "error": f"Query failed: {response.status}",
                    "error_type": "QueryError",
                    "search_criteria": {
                        "url_pattern": url_pattern,
                        "status_code": status_code,
                        "method": method
                    }
                }
                
        except Exception as e:
            return {
                "error": f"Failed to search requests: {str(e)}",
                "error_type": type(e).__name__,
                "search_criteria": {
                    "url_pattern": url_pattern,
                    "status_code": status_code,
                    "method": method
                }
            }
    
    def sync_wrapper(
        url_pattern: Optional[str] = None,
        status_code: Optional[int] = None,
        method: Optional[str] = None,
        min_duration_ms: Optional[int] = None,
        max_duration_ms: Optional[int] = None,
        start_date: str = None,
        end_date: str = None,
        max_results: int = 100
    ) -> Dict[str, Any]:
        return _run_async(search_requests_by_criteria(
            url_pattern, status_code, method, min_duration_ms, max_duration_ms,
            start_date, end_date, max_results
        ))
    
    sync_wrapper.__doc__ = search_requests_by_criteria.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=search_requests_by_criteria,
        name="search_requests_by_criteria",
        description=search_requests_by_criteria.__doc__ or "Search Application Insights requests by multiple criteria"
    )
    return tool


def create_get_failure_summary_by_timerange_tool(secret_retriever: ISecretRetriever):
    """Factory function to create failure summary tool with injected secret retriever."""
    
    async def get_failure_summary_by_timerange(
        start_date: str = None,
        end_date: str = None,
        group_by: str = "endpoint"
    ) -> Dict[str, Any]:
        """Get a comprehensive summary of failures within a time range for quick incident assessment.
        
        This tool provides a high-level overview of all failures in the system, helping to quickly
        understand the scope and nature of an incident. It groups failures by endpoint, error type,
        or status code to identify patterns.
        
        Use this tool for:
        - Initial incident triage to understand scope
        - Identifying which services/endpoints are most affected
        - Finding error patterns and commonalities
        - Determining incident severity based on failure volume
        
        Args:
            start_date: Start time in ISO 8601 format. Defaults to 1 hour ago.
            end_date: End time in ISO 8601 format. Defaults to now.
            group_by: How to group failures - "endpoint", "status_code", or "exception_type"
        
        Returns:
            Dict[str, Any]: Comprehensive failure summary.
            
            Success example:
            {
                "summary": {
                    "total_failures": 1523,
                    "failure_rate": 15.2,
                    "affected_endpoints": 5,
                    "time_range_minutes": 60
                },
                "top_failures": [
                    {
                        "group": "POST /api/payment/process",
                        "count": 823,
                        "percentage": 54.0,
                        "avg_duration_ms": 5200,
                        "sample_operation_ids": ["abc123", "def456", "ghi789"],
                        "common_error": "Timeout executing payment",
                        "first_seen": "2024-01-15T10:00:00Z",
                        "last_seen": "2024-01-15T11:00:00Z"
                    }
                ],
                "timeline": [
                    {"timestamp": "2024-01-15T10:00:00Z", "failure_count": 10},
                    {"timestamp": "2024-01-15T10:15:00Z", "failure_count": 250}
                ],
                "related_exceptions": ["SqlTimeoutException", "HttpRequestException"],
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Set default time range
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
            if not end_date:
                end_date = datetime.utcnow().isoformat() + "Z"
            
            # Main query for failure summary
            group_field = {
                "endpoint": "name",
                "status_code": "resultCode", 
                "exception_type": "exception_type"
            }.get(group_by, "name")
            
            summary_query = f"""
            let total_requests = requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            | count;
            let failures = requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            | where success == false
            | extend exception_type = tostring(customDimensions["Exception.Type"]);
            failures
            | summarize 
                count = count(),
                avg_duration = avg(duration),
                sample_operations = make_set(operation_Id, 5),
                first_seen = min(timestamp),
                last_seen = max(timestamp)
            by {group_field}
            | order by count desc
            | limit 20
            | project 
                group_key = {group_field},
                failure_count = count,
                avg_duration_ms = round(avg_duration),
                sample_operation_ids = sample_operations,
                first_seen,
                last_seen
            """
            
            # Timeline query for failure trend
            timeline_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            | where success == false
            | summarize failure_count = count() by bin(timestamp, 15m)
            | order by timestamp asc
            """
            
            # Execute queries
            summary_response = logs_client.query_resource(resource_id, summary_query, timespan=None)
            timeline_response = logs_client.query_resource(resource_id, timeline_query, timespan=None)
            
            if summary_response.status == LogsQueryStatus.SUCCESS and timeline_response.status == LogsQueryStatus.SUCCESS:
                # Process summary results
                top_failures = []
                total_failures = 0
                
                for table in summary_response.tables:
                    for row in table.rows:
                        failure_data = dict(zip([_col_name(col) for col in table.columns], row))
                        total_failures += failure_data.get("failure_count", 0)
                        
                        top_failures.append({
                            "group": failure_data.get("group_key"),
                            "count": failure_data.get("failure_count"),
                            "avg_duration_ms": failure_data.get("avg_duration_ms"),
                            "sample_operation_ids": failure_data.get("sample_operation_ids", []),
                            "first_seen": _format_datetime(failure_data.get("first_seen")),
                            "last_seen": _format_datetime(failure_data.get("last_seen"))
                        })
                
                # Calculate percentages
                for failure in top_failures:
                    failure["percentage"] = round((failure["count"] / total_failures * 100), 1) if total_failures > 0 else 0
                
                # Process timeline
                timeline = []
                for table in timeline_response.tables:
                    for row in table.rows:
                        timeline_data = dict(zip([_col_name(col) for col in table.columns], row))
                        timeline.append({
                            "timestamp": _format_datetime(timeline_data.get("timestamp")),
                            "failure_count": timeline_data.get("failure_count")
                        })
                
                # Get total request count for failure rate
                total_requests_query = f"""
                requests
                | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
                | count
                """
                total_response = logs_client.query_resource(resource_id, total_requests_query, timespan=None)
                total_requests = 0
                if total_response.status == LogsQueryStatus.SUCCESS:
                    for table in total_response.tables:
                        if table.rows:
                            total_requests = table.rows[0][0]
                
                # Calculate summary statistics
                time_range_minutes = int((datetime.fromisoformat(end_date.rstrip('Z')) - 
                                         datetime.fromisoformat(start_date.rstrip('Z'))).total_seconds() / 60)
                
                summary = {
                    "total_failures": total_failures,
                    "total_requests": total_requests,
                    "failure_rate": round((total_failures / total_requests * 100), 1) if total_requests > 0 else 0,
                    "affected_groups": len(top_failures),
                    "time_range_minutes": time_range_minutes
                }
                
                return {
                    "summary": summary,
                    "top_failures": top_failures,
                    "timeline": timeline,
                    "group_by": group_by,
                    "time_range": {"from": start_date, "to": end_date},
                    "status": "success"
                }
            else:
                return {
                    "error": "Failed to retrieve failure summary",
                    "error_type": "QueryError"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to get failure summary: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def sync_wrapper(
        start_date: str = None,
        end_date: str = None,
        group_by: str = "endpoint"
    ) -> Dict[str, Any]:
        return _run_async(get_failure_summary_by_timerange(start_date, end_date, group_by))
    
    sync_wrapper.__doc__ = get_failure_summary_by_timerange.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_failure_summary_by_timerange,
        name="get_failure_summary_by_timerange",
        description=get_failure_summary_by_timerange.__doc__ or "Get comprehensive failure summary"
    )
    return tool


def create_trace_distributed_transaction_tool(secret_retriever: ISecretRetriever):
    """Factory function to create distributed transaction tracing tool with injected secret retriever."""
    
    async def trace_distributed_transaction(
        operation_id: str,
        include_performance_details: bool = True
    ) -> Dict[str, Any]:
        """Trace a complete distributed transaction across all services and dependencies.
        
        This tool reconstructs the full execution path of a request as it flows through
        multiple services and dependencies. It provides timing breakdown, dependency calls,
        and identifies bottlenecks in the transaction flow. Essential for understanding
        cascading failures in microservices architectures.
        
        Use this tool for:
        - Understanding the complete flow of a failed request
        - Identifying which service or dependency caused delays
        - Analyzing cascading failures across services
        - Performance bottleneck identification
        - Correlating errors across service boundaries
        
        Args:
            operation_id: The operation ID to trace across all services
            include_performance_details: Include detailed timing breakdown (default True)
        
        Returns:
            Dict[str, Any]: Complete transaction trace with timing and dependencies.
            
            Success example:
            {
                "operation_id": "abc123",
                "start_time": "2024-01-15T10:30:00Z",
                "end_time": "2024-01-15T10:30:05Z", 
                "total_duration_ms": 5000,
                "success": false,
                "root_request": {
                    "name": "POST /api/order",
                    "url": "/api/order/create",
                    "duration_ms": 5000,
                    "status_code": 500
                },
                "service_calls": [
                    {
                        "timestamp": "2024-01-15T10:30:00.100Z",
                        "service": "order-service",
                        "operation": "CreateOrder",
                        "duration_ms": 100,
                        "success": true
                    },
                    {
                        "timestamp": "2024-01-15T10:30:00.200Z", 
                        "service": "inventory-service",
                        "operation": "CheckInventory",
                        "duration_ms": 50,
                        "success": true
                    },
                    {
                        "timestamp": "2024-01-15T10:30:00.300Z",
                        "service": "payment-service", 
                        "operation": "ProcessPayment",
                        "duration_ms": 4500,
                        "success": false,
                        "error": "Timeout calling payment gateway"
                    }
                ],
                "dependencies": [
                    {
                        "type": "SQL",
                        "target": "OrderDB",
                        "duration_ms": 20,
                        "success": true,
                        "query": "INSERT INTO orders..."
                    },
                    {
                        "type": "HTTP",
                        "target": "payment-gateway.com",
                        "duration_ms": 4400,
                        "success": false,
                        "status_code": 0,
                        "error": "Connection timeout"
                    }
                ],
                "critical_path": [
                    "order-service (100ms)",
                    "payment-service (4500ms) - BOTTLENECK",
                    "payment-gateway.com (4400ms) - FAILED"
                ],
                "error_details": {
                    "failed_at": "payment-gateway.com",
                    "error_type": "HttpRequestException",
                    "error_message": "Connection timeout after 4400ms"
                },
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Get all telemetry for this operation
            telemetry_query = f"""
            union 
                (requests | where operation_Id == "{operation_id}"),
                (dependencies | where operation_Id == "{operation_id}"),
                (exceptions | where operation_Id == "{operation_id}"),
                (traces | where operation_Id == "{operation_id}")
            | project 
                timestamp,
                itemType,
                name,
                url,
                target,
                type,
                success,
                resultCode,
                duration,
                message,
                severityLevel,
                customDimensions,
                operation_Id,
                operation_ParentId,
                cloud_RoleName
            | order by timestamp asc
            """
            
            response = logs_client.query_resource(resource_id, telemetry_query, timespan=None)
            
            if response.status == LogsQueryStatus.SUCCESS:
                # Process results
                root_request = None
                service_calls = []
                dependencies = []
                exceptions = []
                traces = []
                
                for table in response.tables:
                    for row in table.rows:
                        item = dict(zip([_col_name(col) for col in table.columns], row))
                        item_type = item.get("itemType")
                        
                        if item_type == "request":
                            if not root_request or not item.get("operation_ParentId"):
                                root_request = {
                                    "name": item.get("name"),
                                    "url": item.get("url"),
                                    "duration_ms": item.get("duration"),
                                    "status_code": item.get("resultCode"),
                                    "success": item.get("success"),
                                    "timestamp": _format_datetime(item.get("timestamp")),
                                    "service": item.get("cloud_RoleName")
                                }
                            else:
                                service_calls.append({
                                    "timestamp": _format_datetime(item.get("timestamp")),
                                    "service": item.get("cloud_RoleName"),
                                    "operation": item.get("name"),
                                    "duration_ms": item.get("duration"),
                                    "success": item.get("success"),
                                    "status_code": item.get("resultCode")
                                })
                        
                        elif item_type == "dependency":
                            dependencies.append({
                                "timestamp": _format_datetime(item.get("timestamp")),
                                "type": item.get("type"),
                                "target": item.get("target"),
                                "name": item.get("name"),
                                "duration_ms": item.get("duration"),
                                "success": item.get("success"),
                                "status_code": item.get("resultCode"),
                                "service": item.get("cloud_RoleName")
                            })
                        
                        elif item_type == "exception":
                            exceptions.append({
                                "timestamp": _format_datetime(item.get("timestamp")),
                                "message": item.get("message"),
                                "type": item.get("type", "Unknown"),
                                "service": item.get("cloud_RoleName")
                            })
                
                # Analyze critical path and bottlenecks
                critical_path = []
                bottleneck = None
                max_duration = 0
                
                # Combine all operations for critical path analysis
                all_operations = []
                if root_request:
                    all_operations.append({
                        "name": root_request["service"] or "root",
                        "duration_ms": root_request["duration_ms"],
                        "success": root_request["success"]
                    })
                
                for call in service_calls:
                    all_operations.append({
                        "name": call["service"],
                        "duration_ms": call["duration_ms"],
                        "success": call["success"]
                    })
                
                for dep in dependencies:
                    if dep["duration_ms"] and dep["duration_ms"] > max_duration:
                        max_duration = dep["duration_ms"]
                        bottleneck = f"{dep['type']} - {dep['target']}"
                
                # Build critical path
                for op in all_operations:
                    if op["duration_ms"]:
                        path_item = f"{op['name']} ({op['duration_ms']}ms)"
                        if not op["success"]:
                            path_item += " - FAILED"
                        elif bottleneck and op["name"] in bottleneck:
                            path_item += " - BOTTLENECK"
                        critical_path.append(path_item)
                
                # Determine error details
                error_details = None
                if exceptions:
                    error_details = {
                        "error_count": len(exceptions),
                        "first_error": exceptions[0] if exceptions else None
                    }
                
                # Failed dependency details
                failed_deps = [d for d in dependencies if not d.get("success", True)]
                if failed_deps and not error_details:
                    failed_dep = failed_deps[0]
                    error_details = {
                        "failed_at": f"{failed_dep['type']} - {failed_dep['target']}",
                        "error_type": "DependencyFailure",
                        "duration_before_failure": failed_dep.get("duration_ms")
                    }
                
                # Calculate total duration
                start_time = root_request["timestamp"] if root_request else None
                total_duration_ms = root_request["duration_ms"] if root_request else 0
                
                return {
                    "operation_id": operation_id,
                    "start_time": start_time,
                    "total_duration_ms": total_duration_ms,
                    "success": root_request["success"] if root_request else False,
                    "root_request": root_request,
                    "service_calls": sorted(service_calls, key=lambda x: x["timestamp"]),
                    "dependencies": sorted(dependencies, key=lambda x: x["timestamp"]),
                    "exceptions": exceptions,
                    "critical_path": critical_path,
                    "bottleneck": bottleneck,
                    "error_details": error_details,
                    "telemetry_count": {
                        "requests": len(service_calls) + (1 if root_request else 0),
                        "dependencies": len(dependencies),
                        "exceptions": len(exceptions)
                    },
                    "status": "success"
                }
            else:
                return {
                    "error": f"Failed to trace transaction: {response.status}",
                    "error_type": "QueryError",
                    "operation_id": operation_id
                }
                
        except Exception as e:
            return {
                "error": f"Failed to trace distributed transaction: {str(e)}",
                "error_type": type(e).__name__,
                "operation_id": operation_id
            }
    
    def sync_wrapper(
        operation_id: str,
        include_performance_details: bool = True
    ) -> Dict[str, Any]:
        return _run_async(trace_distributed_transaction(operation_id, include_performance_details))
    
    sync_wrapper.__doc__ = trace_distributed_transaction.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=trace_distributed_transaction,
        name="trace_distributed_transaction",
        description=trace_distributed_transaction.__doc__ or "Trace complete distributed transaction"
    )
    return tool


def create_analyze_dependency_failures_tool(secret_retriever: ISecretRetriever):
    """Factory function to create dependency failure analysis tool with injected secret retriever."""
    
    async def analyze_dependency_failures(
        service_name: Optional[str] = None,
        dependency_type: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        min_failure_count: int = 10
    ) -> Dict[str, Any]:
        """Analyze dependency failures to identify external service issues impacting the application.
        
        This tool focuses on failures in external dependencies (databases, APIs, message queues, etc.)
        that could be causing application errors. It groups failures by dependency to identify
        systemic issues with specific external services.
        
        Use this tool for:
        - Identifying if database is causing timeouts
        - Finding issues with external API integrations  
        - Detecting message queue connection problems
        - Understanding which dependencies are unreliable
        - Correlating application errors with dependency failures
        
        Args:
            service_name: Optional filter by calling service name
            dependency_type: Optional filter by type - "SQL", "HTTP", "Azure blob", etc.
            start_date: Start time in ISO 8601 format. Defaults to 1 hour ago.
            end_date: End time in ISO 8601 format. Defaults to now.
            min_failure_count: Minimum failures to include dependency (default 10)
        
        Returns:
            Dict[str, Any]: Analysis of dependency failures grouped by target.
            
            Success example:
            {
                "summary": {
                    "total_dependency_calls": 50000,
                    "total_failures": 2500,
                    "overall_failure_rate": 5.0,
                    "affected_dependencies": 3
                },
                "failed_dependencies": [
                    {
                        "type": "SQL",
                        "target": "orderdb.database.windows.net",
                        "failure_count": 1800,
                        "total_calls": 20000,
                        "failure_rate": 9.0,
                        "avg_duration_before_failure": 30000,
                        "common_errors": [
                            {"error": "Timeout expired", "count": 1500},
                            {"error": "Connection pool exhausted", "count": 300}
                        ],
                        "affected_operations": [
                            "GetOrderById", "CreateOrder", "UpdateOrderStatus"
                        ],
                        "sample_operation_ids": ["abc123", "def456"],
                        "trend": "increasing"
                    },
                    {
                        "type": "HTTP", 
                        "target": "payment-gateway.com",
                        "failure_count": 600,
                        "total_calls": 5000,
                        "failure_rate": 12.0,
                        "status_codes": {"0": 400, "503": 200},
                        "avg_duration_before_failure": 5000
                    }
                ],
                "timeline": {
                    "SQL|orderdb.database.windows.net": [
                        {"timestamp": "2024-01-15T10:00:00Z", "failures": 50},
                        {"timestamp": "2024-01-15T10:15:00Z", "failures": 450}
                    ]
                },
                "recommendations": [
                    "SQL database showing timeout errors - check connection pool settings",
                    "Payment gateway returning 503 - external service may be down"
                ],
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Set default time range
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
            if not end_date:
                end_date = datetime.utcnow().isoformat() + "Z"
            
            # Build query filters
            filters = [f"timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')"]
            if service_name:
                filters.append(f"cloud_RoleName == '{service_name}'")
            if dependency_type:
                filters.append(f"type == '{dependency_type}'")
            
            where_clause = " and ".join(filters)
            
            # Main dependency analysis query
            analysis_query = f"""
            dependencies
            | where {where_clause}
            | summarize 
                total_calls = count(),
                failure_count = countif(success == false),
                avg_duration = avg(duration),
                avg_duration_failed = avgif(duration, success == false),
                sample_operations = make_set(operation_Id, 5),
                affected_operations = make_set(name, 10),
                status_codes = make_bag(pack(tostring(resultCode), 1))
            by type, target
            | where failure_count >= {min_failure_count}
            | extend failure_rate = round(failure_count * 100.0 / total_calls, 1)
            | order by failure_count desc
            """
            
            # Timeline query for trend analysis
            timeline_query = f"""
            dependencies  
            | where {where_clause}
            | where success == false
            | summarize failures = count() by type, target, bin(timestamp, 15m)
            | order by timestamp asc
            """
            
            # Error message analysis
            error_query = f"""
            dependencies
            | where {where_clause}
            | where success == false
            | extend error_message = tostring(customDimensions["Error.Message"])
            | where isnotempty(error_message)
            | summarize error_count = count() by type, target, error_message
            | top-nested of type by sum(error_count),
              top-nested of target by sum(error_count),
              top-nested 5 of error_message by sum(error_count)
            """
            
            # Execute queries
            analysis_response = logs_client.query_resource(resource_id, analysis_query, timespan=None)
            timeline_response = logs_client.query_resource(resource_id, timeline_query, timespan=None)
            error_response = logs_client.query_resource(resource_id, error_query, timespan=None)
            
            if analysis_response.status == LogsQueryStatus.SUCCESS:
                # Process main analysis results
                failed_dependencies = []
                total_calls = 0
                total_failures = 0
                
                for table in analysis_response.tables:
                    for row in table.rows:
                        dep = dict(zip([_col_name(col) for col in table.columns], row))
                        total_calls += dep.get("total_calls", 0)
                        total_failures += dep.get("failure_count", 0)
                        
                        failed_dependencies.append({
                            "type": dep.get("type"),
                            "target": dep.get("target"),
                            "failure_count": dep.get("failure_count"),
                            "total_calls": dep.get("total_calls"),
                            "failure_rate": dep.get("failure_rate"),
                            "avg_duration_ms": round(dep.get("avg_duration", 0)),
                            "avg_duration_before_failure": round(dep.get("avg_duration_failed", 0)),
                            "affected_operations": dep.get("affected_operations", []),
                            "sample_operation_ids": dep.get("sample_operations", []),
                            "status_codes": dep.get("status_codes", {})
                        })
                
                # Process timeline for trends
                timeline = {}
                if timeline_response.status == LogsQueryStatus.SUCCESS:
                    for table in timeline_response.tables:
                        for row in table.rows:
                            timeline_item = dict(zip([_col_name(col) for col in table.columns], row))
                            key = f"{timeline_item['type']}|{timeline_item['target']}"
                            if key not in timeline:
                                timeline[key] = []
                            timeline[key].append({
                                "timestamp": _format_datetime(timeline_item["timestamp"]),
                                "failures": timeline_item["failures"]
                            })
                
                # Process error messages
                error_patterns = {}
                if error_response.status == LogsQueryStatus.SUCCESS:
                    for table in error_response.tables:
                        for row in table.rows:
                            error_item = dict(zip([_col_name(col) for col in table.columns], row))
                            key = f"{error_item.get('type')}|{error_item.get('target')}"
                            if key not in error_patterns:
                                error_patterns[key] = []
                            if error_item.get("error_message"):
                                error_patterns[key].append({
                                    "error": error_item["error_message"],
                                    "count": error_item.get("error_count", 0)
                                })
                
                # Add error patterns to dependencies
                for dep in failed_dependencies:
                    key = f"{dep['type']}|{dep['target']}"
                    dep["common_errors"] = error_patterns.get(key, [])
                    
                    # Determine trend
                    if key in timeline and len(timeline[key]) > 1:
                        recent_avg = sum(t["failures"] for t in timeline[key][-3:]) / min(3, len(timeline[key]))
                        older_avg = sum(t["failures"] for t in timeline[key][:-3]) / max(1, len(timeline[key]) - 3)
                        dep["trend"] = "increasing" if recent_avg > older_avg * 1.5 else "stable"
                
                # Generate recommendations
                recommendations = []
                for dep in failed_dependencies:
                    if dep["type"] == "SQL" and dep["avg_duration_before_failure"] > 25000:
                        recommendations.append(f"SQL timeout issues with {dep['target']} - check query performance and connection pool")
                    elif dep["type"] == "HTTP" and "503" in str(dep.get("status_codes", {})):
                        recommendations.append(f"External service {dep['target']} returning 503 - service may be down")
                    elif dep["failure_rate"] > 20:
                        recommendations.append(f"High failure rate ({dep['failure_rate']}%) for {dep['target']}")
                
                return {
                    "summary": {
                        "total_dependency_calls": total_calls,
                        "total_failures": total_failures,
                        "overall_failure_rate": round(total_failures / total_calls * 100, 1) if total_calls > 0 else 0,
                        "affected_dependencies": len(failed_dependencies)
                    },
                    "failed_dependencies": failed_dependencies,
                    "timeline": timeline,
                    "recommendations": recommendations,
                    "filters": {
                        "service_name": service_name,
                        "dependency_type": dependency_type,
                        "time_range": {"from": start_date, "to": end_date}
                    },
                    "status": "success"
                }
            else:
                return {
                    "error": f"Failed to analyze dependencies: {analysis_response.status}",
                    "error_type": "QueryError"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to analyze dependency failures: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def sync_wrapper(
        service_name: Optional[str] = None,
        dependency_type: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        min_failure_count: int = 10
    ) -> Dict[str, Any]:
        return _run_async(analyze_dependency_failures(
            service_name, dependency_type, start_date, end_date, min_failure_count
        ))
    
    sync_wrapper.__doc__ = analyze_dependency_failures.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=analyze_dependency_failures,
        name="analyze_dependency_failures",
        description=analyze_dependency_failures.__doc__ or "Analyze dependency failures"
    )
    return tool


def create_correlate_errors_and_metrics_tool(secret_retriever: ISecretRetriever):
    """Factory function to create error and metrics correlation tool with injected secret retriever."""
    
    async def correlate_errors_and_metrics(
        service_name: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        metrics_to_check: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Correlate application errors with system metrics to identify resource-related root causes.
        
        This tool analyzes the relationship between error spikes and system metrics like CPU,
        memory, response time, and request rate. It helps identify if errors are caused by
        resource exhaustion, overload, or performance degradation.
        
        Use this tool for:
        - Identifying if errors correlate with high CPU/memory usage
        - Finding if failures happen during traffic spikes
        - Detecting resource exhaustion patterns
        - Understanding performance degradation impacts
        - Validating if scaling would solve the issue
        
        Args:
            service_name: Optional service name to filter analysis
            start_date: Start time in ISO 8601 format. Defaults to 2 hours ago.
            end_date: End time in ISO 8601 format. Defaults to now.
            metrics_to_check: Optional list of metrics. Defaults to common performance metrics.
        
        Returns:
            Dict[str, Any]: Correlation analysis between errors and metrics.
            
            Success example:
            {
                "error_summary": {
                    "total_errors": 1523,
                    "error_rate": 15.2,
                    "peak_error_time": "2024-01-15T10:45:00Z",
                    "peak_error_rate": 45.5
                },
                "metric_correlations": [
                    {
                        "metric": "cpu_percentage",
                        "correlation_score": 0.89,
                        "correlation": "HIGH",
                        "finding": "Errors increase when CPU > 85%",
                        "peak_value": 94.5,
                        "normal_value": 45.0,
                        "threshold_breach_times": ["10:43", "10:44", "10:45"]
                    },
                    {
                        "metric": "response_time_ms",
                        "correlation_score": 0.92,
                        "correlation": "HIGH", 
                        "finding": "Response time spike precedes errors by ~2 minutes",
                        "peak_value": 5200,
                        "normal_value": 200
                    },
                    {
                        "metric": "request_rate",
                        "correlation_score": 0.45,
                        "correlation": "MEDIUM",
                        "finding": "Moderate traffic increase during errors",
                        "peak_value": 1200,
                        "normal_value": 800
                    }
                ],
                "timeline_analysis": {
                    "error_timeline": [...],
                    "cpu_timeline": [...],
                    "memory_timeline": [...],
                    "response_time_timeline": [...]
                },
                "root_cause_hypothesis": [
                    "CPU saturation is likely causing timeouts and errors",
                    "System needs vertical scaling or code optimization",
                    "Response time degradation starts before CPU peaks - possible inefficient code"
                ],
                "recommendations": [
                    "Enable autoscaling with CPU threshold at 70%",
                    "Investigate code optimization for high CPU operations",
                    "Add CPU and response time alerts for early warning"
                ],
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Set default time range (2 hours for better correlation)
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z"
            if not end_date:
                end_date = datetime.utcnow().isoformat() + "Z"
            
            # Default metrics to check
            if not metrics_to_check:
                metrics_to_check = ["cpu", "memory", "response_time", "request_rate"]
            
            # Build service filter
            service_filter = f"| where cloud_RoleName == '{service_name}'" if service_name else ""
            
            # Query for error timeline
            error_timeline_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            | summarize 
                total_requests = count(),
                failed_requests = countif(success == false),
                error_rate = round(countif(success == false) * 100.0 / count(), 1)
            by bin(timestamp, 1m)
            | order by timestamp asc
            """
            
            # Query for performance metrics
            perf_query = f"""
            performanceCounters
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            | where name in ("% Processor Time", "Available Bytes", "Request rate", "Requests per Second")
            | summarize 
                avg_value = avg(value),
                max_value = max(value),
                min_value = min(value)
            by bin(timestamp, 1m), name
            | order by timestamp asc
            """
            
            # Query for response time
            response_time_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            | summarize 
                avg_duration = avg(duration),
                p95_duration = percentile(duration, 95),
                max_duration = max(duration)
            by bin(timestamp, 1m)
            | order by timestamp asc
            """
            
            # Execute queries
            error_response = logs_client.query_resource(resource_id, error_timeline_query, timespan=None)
            perf_response = logs_client.query_resource(resource_id, perf_query, timespan=None)
            response_response = logs_client.query_resource(resource_id, response_time_query, timespan=None)
            
            if error_response.status == LogsQueryStatus.SUCCESS:
                # Process error timeline
                error_timeline = []
                max_error_rate = 0
                peak_error_time = None
                total_errors = 0
                
                for table in error_response.tables:
                    for row in table.rows:
                        data = dict(zip([_col_name(col) for col in table.columns], row))
                        error_timeline.append({
                            "timestamp": _format_datetime(data["timestamp"]),
                            "error_rate": data.get("error_rate", 0),
                            "failed_requests": data.get("failed_requests", 0)
                        })
                        total_errors += data.get("failed_requests", 0)
                        if data.get("error_rate", 0) > max_error_rate:
                            max_error_rate = data.get("error_rate", 0)
                            peak_error_time = _format_datetime(data["timestamp"])
                
                # Process performance metrics
                metric_timelines = {}
                if perf_response.status == LogsQueryStatus.SUCCESS:
                    for table in perf_response.tables:
                        for row in table.rows:
                            data = dict(zip([_col_name(col) for col in table.columns], row))
                            metric_name = data["name"]
                            if metric_name not in metric_timelines:
                                metric_timelines[metric_name] = []
                            metric_timelines[metric_name].append({
                                "timestamp": _format_datetime(data["timestamp"]),
                                "avg_value": data.get("avg_value", 0),
                                "max_value": data.get("max_value", 0)
                            })
                
                # Process response time
                response_timeline = []
                if response_response.status == LogsQueryStatus.SUCCESS:
                    for table in response_response.tables:
                        for row in table.rows:
                            data = dict(zip([_col_name(col) for col in table.columns], row))
                            response_timeline.append({
                                "timestamp": _format_datetime(data["timestamp"]),
                                "avg_duration": data.get("avg_duration", 0),
                                "p95_duration": data.get("p95_duration", 0)
                            })
                
                # Perform correlation analysis
                metric_correlations = []
                
                # Helper function to calculate correlation
                def calculate_correlation(error_rates, metric_values):
                    if len(error_rates) != len(metric_values) or len(error_rates) < 2:
                        return 0
                    
                    # Simple correlation calculation
                    avg_error = sum(error_rates) / len(error_rates)
                    avg_metric = sum(metric_values) / len(metric_values)
                    
                    numerator = sum((e - avg_error) * (m - avg_metric) for e, m in zip(error_rates, metric_values))
                    denominator_e = sum((e - avg_error) ** 2 for e in error_rates) ** 0.5
                    denominator_m = sum((m - avg_metric) ** 2 for m in metric_values) ** 0.5
                    
                    if denominator_e == 0 or denominator_m == 0:
                        return 0
                    
                    return numerator / (denominator_e * denominator_m)
                
                # Correlate each metric
                error_rates = [e["error_rate"] for e in error_timeline]
                
                # CPU correlation
                if "% Processor Time" in metric_timelines:
                    cpu_values = [m["avg_value"] for m in metric_timelines["% Processor Time"]]
                    if len(cpu_values) == len(error_rates):
                        correlation = calculate_correlation(error_rates, cpu_values)
                        finding = ""
                        if correlation > 0.7:
                            high_cpu_errors = [e for e, c in zip(error_timeline, cpu_values) if c > 80 and e["error_rate"] > 10]
                            if high_cpu_errors:
                                finding = f"Errors increase when CPU > 80%"
                        
                        metric_correlations.append({
                            "metric": "cpu_percentage",
                            "correlation_score": round(abs(correlation), 2),
                            "correlation": "HIGH" if abs(correlation) > 0.7 else "MEDIUM" if abs(correlation) > 0.4 else "LOW",
                            "finding": finding or "No clear pattern",
                            "peak_value": max(cpu_values) if cpu_values else 0,
                            "normal_value": sum(cpu_values[:10]) / min(10, len(cpu_values)) if cpu_values else 0
                        })
                
                # Response time correlation  
                if response_timeline:
                    response_values = [r["avg_duration"] for r in response_timeline]
                    if len(response_values) == len(error_rates):
                        correlation = calculate_correlation(error_rates, response_values)
                        finding = ""
                        if correlation > 0.7:
                            finding = "Response time spike correlates with errors"
                        
                        metric_correlations.append({
                            "metric": "response_time_ms",
                            "correlation_score": round(abs(correlation), 2),
                            "correlation": "HIGH" if abs(correlation) > 0.7 else "MEDIUM" if abs(correlation) > 0.4 else "LOW",
                            "finding": finding or "No clear pattern",
                            "peak_value": max(response_values) if response_values else 0,
                            "normal_value": sum(response_values[:10]) / min(10, len(response_values)) if response_values else 0
                        })
                
                # Generate root cause hypotheses
                root_cause_hypothesis = []
                recommendations = []
                
                high_correlations = [m for m in metric_correlations if m["correlation"] == "HIGH"]
                if any(m["metric"] == "cpu_percentage" for m in high_correlations):
                    root_cause_hypothesis.append("CPU saturation is likely causing timeouts and errors")
                    recommendations.append("Enable autoscaling with CPU threshold at 70%")
                    recommendations.append("Profile application to identify CPU-intensive operations")
                
                if any(m["metric"] == "response_time_ms" for m in high_correlations):
                    root_cause_hypothesis.append("Performance degradation is causing failures")
                    recommendations.append("Investigate slow queries and external API calls")
                
                if not high_correlations:
                    root_cause_hypothesis.append("Errors may be due to application logic or external factors")
                    recommendations.append("Check application logs for specific error messages")
                
                return {
                    "error_summary": {
                        "total_errors": total_errors,
                        "avg_error_rate": round(sum(error_rates) / len(error_rates), 1) if error_rates else 0,
                        "peak_error_time": peak_error_time,
                        "peak_error_rate": max_error_rate
                    },
                    "metric_correlations": metric_correlations,
                    "timeline_analysis": {
                        "error_timeline": error_timeline[:20],  # Limit for readability
                        "metrics_available": list(metric_timelines.keys())
                    },
                    "root_cause_hypothesis": root_cause_hypothesis,
                    "recommendations": recommendations,
                    "analysis_period": {"from": start_date, "to": end_date},
                    "status": "success"
                }
            else:
                return {
                    "error": f"Failed to retrieve error timeline: {error_response.status}",
                    "error_type": "QueryError"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to correlate errors and metrics: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def sync_wrapper(
        service_name: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        metrics_to_check: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        return _run_async(correlate_errors_and_metrics(
            service_name, start_date, end_date, metrics_to_check
        ))
    
    sync_wrapper.__doc__ = correlate_errors_and_metrics.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=correlate_errors_and_metrics,
        name="correlate_errors_and_metrics",
        description=correlate_errors_and_metrics.__doc__ or "Correlate errors with system metrics"
    )
    return tool


def create_get_error_trends_analysis_tool(secret_retriever: ISecretRetriever):
    """Factory function to create error trends analysis tool with injected secret retriever."""
    
    async def get_error_trends_analysis(
        service_name: Optional[str] = None,
        error_type: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        baseline_days: int = 7
    ) -> Dict[str, Any]:
        """Analyze error trends to determine if issues are increasing, stable, or improving.
        
        This tool compares current error rates with historical baselines to identify trends
        and anomalies. It helps determine the severity and progression of incidents by
        showing whether errors are new, increasing, or part of normal patterns.
        
        Use this tool for:
        - Determining if current errors are anomalous or normal
        - Identifying when an issue started
        - Understanding if problems are getting worse or better
        - Comparing with historical baselines
        - Detecting gradual degradation vs sudden failures
        
        Args:
            service_name: Optional service name to filter analysis
            error_type: Optional specific error type or exception to analyze
            start_date: Start of analysis period. Defaults to 4 hours ago.
            end_date: End of analysis period. Defaults to now.
            baseline_days: Number of days to use for baseline comparison (default 7)
        
        Returns:
            Dict[str, Any]: Comprehensive error trend analysis.
            
            Success example:
            {
                "current_period": {
                    "total_errors": 1523,
                    "error_rate": 15.2,
                    "unique_error_types": 5,
                    "most_common_errors": [
                        {"type": "SqlTimeoutException", "count": 823, "percentage": 54.0},
                        {"type": "HttpRequestException", "count": 400, "percentage": 26.3}
                    ]
                },
                "baseline_period": {
                    "avg_errors_per_hour": 45,
                    "avg_error_rate": 1.2,
                    "typical_error_types": ["ValidationException", "NotFoundException"]
                },
                "trend_analysis": {
                    "trend": "INCREASING",
                    "severity": "CRITICAL",
                    "change_percentage": 1169,
                    "standard_deviations": 8.5,
                    "is_anomaly": true,
                    "anomaly_start_time": "2024-01-15T10:00:00Z"
                },
                "hourly_comparison": [
                    {
                        "hour": "2024-01-15T10:00:00Z",
                        "errors": 523,
                        "baseline_avg": 45,
                        "deviation": "+1062%"
                    }
                ],
                "new_error_types": [
                    "SqlTimeoutException - not seen in baseline period",
                    "ConnectionPoolExhaustedException - first appeared at 10:15"
                ],
                "pattern_detection": {
                    "pattern": "SUDDEN_SPIKE",
                    "description": "Errors increased 10x within 15 minutes",
                    "correlation": "All errors started after 10:00 AM"
                },
                "impact_assessment": {
                    "affected_users_estimate": 15230,
                    "affected_operations": ["CreateOrder", "ProcessPayment"],
                    "business_impact": "HIGH - Core transaction flow affected"
                },
                "recommendations": [
                    "CRITICAL: Error rate is 10x normal - immediate action required",
                    "New error type (SqlTimeoutException) indicates database issues",
                    "Pattern suggests sudden failure rather than gradual degradation"
                ],
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Set default time range
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(hours=4)).isoformat() + "Z"
            if not end_date:
                end_date = datetime.utcnow().isoformat() + "Z"
            
            # Calculate baseline period
            current_start = datetime.fromisoformat(start_date.rstrip('Z'))
            current_end = datetime.fromisoformat(end_date.rstrip('Z'))
            baseline_end = current_start - timedelta(days=1)
            baseline_start = baseline_end - timedelta(days=baseline_days)
            
            # Build filters
            service_filter = f"| where cloud_RoleName == '{service_name}'" if service_name else ""
            error_filter = f"| where type == '{error_type}'" if error_type else ""
            
            # Current period analysis
            current_query = f"""
            let errors = union
                (requests | where success == false | extend error_type = tostring(customDimensions["Exception.Type"])),
                (exceptions | extend error_type = type);
            errors
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            {error_filter}
            | summarize 
                total_errors = count(),
                unique_error_types = dcount(error_type),
                error_types = make_set(error_type),
                by_type = make_bag(pack(error_type, 1))
            """
            
            # Error type breakdown
            error_breakdown_query = f"""
            union
                (requests | where success == false | extend error_type = tostring(customDimensions["Exception.Type"])),
                (exceptions | extend error_type = type)
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            | summarize count = count() by error_type
            | order by count desc
            | limit 10
            """
            
            # Hourly trend
            hourly_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            | summarize 
                total = count(),
                errors = countif(success == false),
                error_rate = round(countif(success == false) * 100.0 / count(), 1)
            by bin(timestamp, 1h)
            | order by timestamp asc
            """
            
            # Baseline analysis
            baseline_query = f"""
            requests
            | where timestamp >= datetime('{baseline_start.isoformat()}Z') and timestamp <= datetime('{baseline_end.isoformat()}Z')
            {service_filter}
            | summarize 
                total_requests = count(),
                total_errors = countif(success == false),
                hourly_avg_errors = countif(success == false) / {baseline_days * 24.0}
            """
            
            # Find anomaly start time
            anomaly_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {service_filter}
            | where success == false
            | summarize error_count = count() by bin(timestamp, 5m)
            | order by timestamp asc
            """
            
            # Execute queries
            current_response = logs_client.query_resource(resource_id, current_query, timespan=None)
            breakdown_response = logs_client.query_resource(resource_id, error_breakdown_query, timespan=None)
            hourly_response = logs_client.query_resource(resource_id, hourly_query, timespan=None)
            baseline_response = logs_client.query_resource(resource_id, baseline_query, timespan=None)
            anomaly_response = logs_client.query_resource(resource_id, anomaly_query, timespan=None)
            
            if current_response.status == LogsQueryStatus.SUCCESS and baseline_response.status == LogsQueryStatus.SUCCESS:
                # Process current period
                current_data = {}
                for table in current_response.tables:
                    if table.rows:
                        current_data = dict(zip([_col_name(col) for col in table.columns], table.rows[0]))
                
                # Process error breakdown
                error_breakdown = []
                total_errors = current_data.get("total_errors", 0)
                for table in breakdown_response.tables:
                    for row in table.rows:
                        error_info = dict(zip([_col_name(col) for col in table.columns], row))
                        error_breakdown.append({
                            "type": error_info.get("error_type", "Unknown"),
                            "count": error_info.get("count", 0),
                            "percentage": round(error_info.get("count", 0) / total_errors * 100, 1) if total_errors > 0 else 0
                        })
                
                # Process baseline
                baseline_data = {}
                for table in baseline_response.tables:
                    if table.rows:
                        baseline_data = dict(zip([_col_name(col) for col in table.columns], table.rows[0]))
                
                baseline_hourly_avg = baseline_data.get("hourly_avg_errors", 0)
                
                # Process hourly trend and compare with baseline
                hourly_comparison = []
                current_hourly_errors = []
                for table in hourly_response.tables:
                    for row in table.rows:
                        hourly_data = dict(zip([_col_name(col) for col in table.columns], row))
                        errors = hourly_data.get("errors", 0)
                        current_hourly_errors.append(errors)
                        
                        deviation = ((errors - baseline_hourly_avg) / baseline_hourly_avg * 100) if baseline_hourly_avg > 0 else 0
                        hourly_comparison.append({
                            "hour": _format_datetime(hourly_data["timestamp"]),
                            "errors": errors,
                            "baseline_avg": round(baseline_hourly_avg),
                            "deviation": f"+{round(deviation)}%" if deviation > 0 else f"{round(deviation)}%"
                        })
                
                # Detect anomaly start
                anomaly_start = None
                for table in anomaly_response.tables:
                    for row in table.rows:
                        anomaly_data = dict(zip([_col_name(col) for col in table.columns], row))
                        if anomaly_data.get("error_count", 0) > baseline_hourly_avg * 3:  # 3x baseline
                            anomaly_start = _format_datetime(anomaly_data["timestamp"])
                            break
                    if anomaly_start:
                        break
                
                # Calculate trend analysis
                current_avg_hourly = sum(current_hourly_errors) / len(current_hourly_errors) if current_hourly_errors else 0
                change_percentage = ((current_avg_hourly - baseline_hourly_avg) / baseline_hourly_avg * 100) if baseline_hourly_avg > 0 else 0
                
                # Determine trend
                if change_percentage > 200:
                    trend = "CRITICAL_INCREASE"
                    severity = "CRITICAL"
                elif change_percentage > 50:
                    trend = "INCREASING"
                    severity = "HIGH"
                elif change_percentage < -50:
                    trend = "IMPROVING"
                    severity = "LOW"
                else:
                    trend = "STABLE"
                    severity = "NORMAL"
                
                # Pattern detection
                pattern = "NORMAL"
                pattern_desc = "Error rate within normal range"
                if len(current_hourly_errors) > 1:
                    if current_hourly_errors[-1] > current_hourly_errors[0] * 5:
                        pattern = "SUDDEN_SPIKE"
                        pattern_desc = "Errors increased dramatically in short time"
                    elif all(current_hourly_errors[i] >= current_hourly_errors[i-1] for i in range(1, len(current_hourly_errors))):
                        pattern = "GRADUAL_INCREASE"
                        pattern_desc = "Errors steadily increasing over time"
                
                # Generate recommendations
                recommendations = []
                if severity == "CRITICAL":
                    recommendations.append(f"CRITICAL: Error rate is {round(change_percentage/100)}x normal - immediate action required")
                if anomaly_start:
                    recommendations.append(f"Anomaly detected starting at {anomaly_start}")
                if pattern == "SUDDEN_SPIKE":
                    recommendations.append("Sudden spike suggests acute issue - check recent deployments or infrastructure changes")
                elif pattern == "GRADUAL_INCREASE":
                    recommendations.append("Gradual increase suggests growing problem - check for resource leaks or capacity issues")
                
                # Check for new error types
                current_types = set(current_data.get("error_types", []))
                new_error_types = []
                for error_type in current_types:
                    if error_type and error_type not in ["ValidationException", "NotFoundException"]:  # Common baseline errors
                        new_error_types.append(f"{error_type} - new in current period")
                
                return {
                    "current_period": {
                        "total_errors": total_errors,
                        "unique_error_types": current_data.get("unique_error_types", 0),
                        "most_common_errors": error_breakdown[:5],
                        "time_range": {"from": start_date, "to": end_date}
                    },
                    "baseline_period": {
                        "avg_errors_per_hour": round(baseline_hourly_avg, 1),
                        "total_errors": baseline_data.get("total_errors", 0),
                        "baseline_days": baseline_days
                    },
                    "trend_analysis": {
                        "trend": trend,
                        "severity": severity,
                        "change_percentage": round(change_percentage),
                        "is_anomaly": severity in ["HIGH", "CRITICAL"],
                        "anomaly_start_time": anomaly_start
                    },
                    "hourly_comparison": hourly_comparison,
                    "new_error_types": new_error_types,
                    "pattern_detection": {
                        "pattern": pattern,
                        "description": pattern_desc
                    },
                    "recommendations": recommendations,
                    "status": "success"
                }
            else:
                return {
                    "error": "Failed to analyze error trends",
                    "error_type": "QueryError"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to analyze error trends: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def sync_wrapper(
        service_name: Optional[str] = None,
        error_type: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        baseline_days: int = 7
    ) -> Dict[str, Any]:
        return _run_async(get_error_trends_analysis(
            service_name, error_type, start_date, end_date, baseline_days
        ))
    
    sync_wrapper.__doc__ = get_error_trends_analysis.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_error_trends_analysis,
        name="get_error_trends_analysis",
        description=get_error_trends_analysis.__doc__ or "Analyze error trends and anomalies"
    )
    return tool


def create_execute_flexible_kql_query_tool(secret_retriever: ISecretRetriever):
    """Factory function to create flexible KQL query execution tool with injected secret retriever."""
    
    async def execute_flexible_kql_query(
        query: str,
        max_results: int = 100,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """Execute custom KQL queries for advanced root cause analysis scenarios.
        
        This tool provides direct KQL query access for complex investigations that require
        custom analysis beyond pre-built tools. Use this when you need to join multiple
        tables, perform complex aggregations, or investigate specific patterns.
        
        Use this tool for:
        - Complex multi-table joins and correlations
        - Custom aggregations and statistical analysis
        - Investigating specific patterns or hypotheses
        - Ad-hoc queries during incident investigation
        - Scenarios not covered by other tools
        
        Common KQL operations:
        - union: Combine data from multiple tables
        - join: Correlate data between tables
        - summarize: Aggregate data with functions like count(), avg(), percentile()
        - extend: Add calculated columns
        - project: Select and rename columns
        - where: Filter data
        - order by: Sort results
        
        Args:
            query: KQL query string to execute.
                  Example queries:
                  - "requests | where success == false | summarize count() by resultCode"
                  - "exceptions | where timestamp > ago(1h) | project message, type"
                  - "dependencies | where duration > 5000 | order by duration desc"
            max_results: Maximum rows to return (default 100, max 1000)
            timeout_seconds: Query timeout in seconds (default 30)
        
        Returns:
            Dict[str, Any]: Query results with metadata.
            
            Success example:
            {
                "results": [
                    {"column1": "value1", "column2": 123},
                    {"column1": "value2", "column2": 456}
                ],
                "row_count": 2,
                "column_names": ["column1", "column2"],
                "column_types": ["string", "long"],
                "query_executed": "requests | where...",
                "execution_time_ms": 245,
                "status": "success"
            }
            
            Error example:
            {
                "error": "Invalid query syntax at line 1",
                "error_type": "QuerySyntaxError",
                "query": "requests | where..."
            }
        
        Safety notes:
        - Queries are limited by timeout and result count
        - Large queries may impact Application Insights performance
        - Avoid queries that scan entire history without time filters
        - Use 'limit' clause to control result size
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Validate and sanitize query
            if not query or not isinstance(query, str):
                return {
                    "error": "Query must be a non-empty string",
                    "error_type": "InvalidInput"
                }
            
            # Add safety limits if not present
            if "limit" not in query.lower():
                query = f"{query.rstrip().rstrip(';')} | limit {min(max_results, 1000)}"
            
            # Log query for debugging (in production, ensure no sensitive data)
            import time
            start_time = time.time()
            
            # Execute query with timeout
            response = logs_client.query_resource(
                resource_id, 
                query, 
                timespan=None,
                server_timeout=timeout_seconds
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status == LogsQueryStatus.SUCCESS:
                results = []
                column_names = []
                column_types = []
                
                for table in response.tables:
                    # Get column metadata
                    if not column_names and table.columns:
                        column_names = [_col_name(col) for col in table.columns]
                        column_types = [col.type for col in table.columns if hasattr(col, 'type')]
                    
                    # Process rows
                    for row in table.rows:
                        # Convert row to dictionary with proper type handling
                        row_dict = {}
                        for i, value in enumerate(row):
                            col_name = column_names[i] if i < len(column_names) else f"column_{i}"
                            # Handle datetime serialization
                            if isinstance(value, datetime):
                                row_dict[col_name] = value.isoformat()
                            elif value is None:
                                row_dict[col_name] = None
                            else:
                                row_dict[col_name] = value
                        results.append(row_dict)
                
                return {
                    "results": results[:max_results],
                    "row_count": len(results),
                    "truncated": len(results) > max_results,
                    "column_names": column_names,
                    "column_types": column_types,
                    "query_executed": query,
                    "execution_time_ms": execution_time_ms,
                    "status": "success"
                }
            
            elif response.status == LogsQueryStatus.PARTIAL_FAILURE:
                # Partial failure - some results but also errors
                partial_results = []
                for table in response.tables:
                    for row in table.rows:
                        partial_results.append(dict(zip([_col_name(col) for col in table.columns], row)))
                
                return {
                    "results": partial_results[:max_results],
                    "row_count": len(partial_results),
                    "error": "Query partially failed - some results returned",
                    "error_details": str(response.partial_error) if hasattr(response, 'partial_error') else "Unknown error",
                    "status": "partial_success"
                }
            
            else:
                # Complete failure
                error_message = "Query failed"
                if hasattr(response, 'error'):
                    error_message = str(response.error)
                
                return {
                    "error": error_message,
                    "error_type": "QueryExecutionError",
                    "query": query,
                    "status": "failed"
                }
                
        except Exception as e:
            error_type = "QuerySyntaxError" if "syntax" in str(e).lower() else type(e).__name__
            return {
                "error": f"Failed to execute query: {str(e)}",
                "error_type": error_type,
                "query": query
            }
    
    def sync_wrapper(
        query: str,
        max_results: int = 100,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        return _run_async(execute_flexible_kql_query(query, max_results, timeout_seconds))
    
    sync_wrapper.__doc__ = execute_flexible_kql_query.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=execute_flexible_kql_query,
        name="execute_flexible_kql_query",
        description=execute_flexible_kql_query.__doc__ or "Execute custom KQL queries"
    )
    return tool


def create_get_performance_baseline_comparison_tool(secret_retriever: ISecretRetriever):
    """Factory function to create performance baseline comparison tool with injected secret retriever."""
    
    async def get_performance_baseline_comparison(
        service_name: Optional[str] = None,
        endpoint_pattern: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        baseline_days: int = 7,
        percentiles: List[int] = None
    ) -> Dict[str, Any]:
        """Compare current performance metrics with historical baselines to identify degradation.
        
        This tool analyzes performance metrics (response time, throughput) against historical
        baselines to determine if current performance is anomalous. It helps distinguish
        between normal variations and actual performance problems.
        
        Use this tool for:
        - Identifying performance degradation vs normal variance
        - Understanding if slowness is affecting all endpoints or specific ones
        - Comparing current load with typical patterns
        - Validating if performance issues correlate with incidents
        - Determining performance SLO violations
        
        Args:
            service_name: Optional service name to filter analysis
            endpoint_pattern: Optional URL pattern to analyze specific endpoints
            start_date: Start of current period. Defaults to 2 hours ago.
            end_date: End of current period. Defaults to now.
            baseline_days: Number of days for baseline calculation (default 7)
            percentiles: List of percentiles to calculate (default [50, 90, 95, 99])
        
        Returns:
            Dict[str, Any]: Performance comparison with baseline.
            
            Success example:
            {
                "current_performance": {
                    "avg_response_time_ms": 2500,
                    "p50_response_time_ms": 2200,
                    "p90_response_time_ms": 4500,
                    "p95_response_time_ms": 6000,
                    "p99_response_time_ms": 12000,
                    "requests_per_minute": 850,
                    "success_rate": 85.5
                },
                "baseline_performance": {
                    "avg_response_time_ms": 250,
                    "p50_response_time_ms": 200,
                    "p90_response_time_ms": 450,
                    "p95_response_time_ms": 600,
                    "p99_response_time_ms": 1200,
                    "requests_per_minute": 800,
                    "success_rate": 99.5
                },
                "comparison": {
                    "response_time_increase": 900,  # 900% increase
                    "is_anomaly": true,
                    "severity": "CRITICAL",
                    "throughput_change": 6.25,  # 6.25% increase
                    "success_rate_drop": 14.0  # 14 percentage points
                },
                "endpoint_breakdown": [
                    {
                        "endpoint": "POST /api/payment/process",
                        "current_avg_ms": 8500,
                        "baseline_avg_ms": 500,
                        "increase_percent": 1600,
                        "request_count": 320,
                        "impact": "HIGH"
                    },
                    {
                        "endpoint": "GET /api/user/profile",
                        "current_avg_ms": 280,
                        "baseline_avg_ms": 250,
                        "increase_percent": 12,
                        "request_count": 530,
                        "impact": "LOW"
                    }
                ],
                "time_based_analysis": {
                    "performance_timeline": [...],
                    "degradation_start": "2024-01-15T10:30:00Z",
                    "worst_period": "2024-01-15T10:45:00Z to 11:00:00Z"
                },
                "slo_violations": [
                    "P95 response time exceeds 1000ms SLO (current: 6000ms)",
                    "Success rate below 99% SLO (current: 85.5%)"
                ],
                "insights": [
                    "Performance is 10x slower than baseline",
                    "Payment endpoint showing severe degradation",
                    "Issue started at 10:30 AM - check for deployments",
                    "High impact on user experience - 14% failures"
                ],
                "recommendations": [
                    "Focus on POST /api/payment/process - showing 16x slowdown",
                    "Check payment service dependencies and database",
                    "Consider rolling back recent changes",
                    "Scale up if load is higher than normal"
                ],
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Set default time ranges
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z"
            if not end_date:
                end_date = datetime.utcnow().isoformat() + "Z"
            
            # Default percentiles
            if not percentiles:
                percentiles = [50, 90, 95, 99]
            
            # Calculate baseline period
            current_start = datetime.fromisoformat(start_date.rstrip('Z'))
            baseline_end = current_start - timedelta(days=1)
            baseline_start = baseline_end - timedelta(days=baseline_days)
            
            # Build filters
            filters = []
            if service_name:
                filters.append(f"cloud_RoleName == '{service_name}'")
            if endpoint_pattern:
                filters.append(f"name contains '{endpoint_pattern}'")
            
            where_clause = f"| where {' and '.join(filters)}" if filters else ""
            
            # Current period performance query
            percentile_calcs = ", ".join([f"p{p} = percentile(duration, {p})" for p in percentiles])
            
            current_perf_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {where_clause}
            | summarize 
                total_requests = count(),
                successful_requests = countif(success == true),
                avg_duration = avg(duration),
                {percentile_calcs},
                requests_per_minute = count() / {(datetime.fromisoformat(end_date.rstrip('Z')) - datetime.fromisoformat(start_date.rstrip('Z'))).total_seconds() / 60}
            """
            
            # Baseline performance query
            baseline_perf_query = f"""
            requests
            | where timestamp >= datetime('{baseline_start.isoformat()}Z') and timestamp <= datetime('{baseline_end.isoformat()}Z')
            {where_clause}
            | summarize 
                total_requests = count(),
                successful_requests = countif(success == true),
                avg_duration = avg(duration),
                {percentile_calcs},
                requests_per_minute = count() / {(baseline_end - baseline_start).total_seconds() / 60}
            """
            
            # Endpoint breakdown query
            endpoint_query = f"""
            let current_period = requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {where_clause}
            | summarize 
                current_avg = avg(duration),
                current_count = count(),
                current_failures = countif(success == false)
            by name;
            let baseline_period = requests
            | where timestamp >= datetime('{baseline_start.isoformat()}Z') and timestamp <= datetime('{baseline_end.isoformat()}Z')
            {where_clause}
            | summarize 
                baseline_avg = avg(duration),
                baseline_count = count()
            by name;
            current_period
            | join kind=leftouter baseline_period on name
            | extend 
                increase_percent = round((current_avg - baseline_avg) / baseline_avg * 100, 0),
                impact = case(
                    current_avg > baseline_avg * 5 and current_count > 100, "HIGH",
                    current_avg > baseline_avg * 2 and current_count > 50, "MEDIUM",
                    "LOW"
                )
            | where current_avg > baseline_avg * 1.5  // Only show degraded endpoints
            | order by current_count desc
            | limit 10
            """
            
            # Performance timeline query
            timeline_query = f"""
            requests
            | where timestamp >= datetime('{start_date}') and timestamp <= datetime('{end_date}')
            {where_clause}
            | summarize 
                avg_duration = avg(duration),
                p95_duration = percentile(duration, 95),
                success_rate = countif(success == true) * 100.0 / count()
            by bin(timestamp, 15m)
            | order by timestamp asc
            """
            
            # Execute queries
            current_response = logs_client.query_resource(resource_id, current_perf_query, timespan=None)
            baseline_response = logs_client.query_resource(resource_id, baseline_perf_query, timespan=None)
            endpoint_response = logs_client.query_resource(resource_id, endpoint_query, timespan=None)
            timeline_response = logs_client.query_resource(resource_id, timeline_query, timespan=None)
            
            if current_response.status == LogsQueryStatus.SUCCESS and baseline_response.status == LogsQueryStatus.SUCCESS:
                # Process current performance
                current_perf = {}
                for table in current_response.tables:
                    if table.rows:
                        row_data = dict(zip([_col_name(col) for col in table.columns], table.rows[0]))
                        current_perf = {
                            "avg_response_time_ms": round(row_data.get("avg_duration", 0)),
                            "requests_per_minute": round(row_data.get("requests_per_minute", 0), 1),
                            "success_rate": round(row_data.get("successful_requests", 0) / row_data.get("total_requests", 1) * 100, 1)
                        }
                        # Add percentiles
                        for p in percentiles:
                            current_perf[f"p{p}_response_time_ms"] = round(row_data.get(f"p{p}", 0))
                
                # Process baseline performance
                baseline_perf = {}
                for table in baseline_response.tables:
                    if table.rows:
                        row_data = dict(zip([_col_name(col) for col in table.columns], table.rows[0]))
                        baseline_perf = {
                            "avg_response_time_ms": round(row_data.get("avg_duration", 0)),
                            "requests_per_minute": round(row_data.get("requests_per_minute", 0), 1),
                            "success_rate": round(row_data.get("successful_requests", 0) / row_data.get("total_requests", 1) * 100, 1)
                        }
                        # Add percentiles
                        for p in percentiles:
                            baseline_perf[f"p{p}_response_time_ms"] = round(row_data.get(f"p{p}", 0))
                
                # Calculate comparison
                response_time_increase = 0
                if baseline_perf.get("avg_response_time_ms", 0) > 0:
                    response_time_increase = round(
                        (current_perf.get("avg_response_time_ms", 0) - baseline_perf.get("avg_response_time_ms", 0)) 
                        / baseline_perf.get("avg_response_time_ms", 1) * 100
                    )
                
                throughput_change = 0
                if baseline_perf.get("requests_per_minute", 0) > 0:
                    throughput_change = round(
                        (current_perf.get("requests_per_minute", 0) - baseline_perf.get("requests_per_minute", 0))
                        / baseline_perf.get("requests_per_minute", 1) * 100, 1
                    )
                
                success_rate_drop = round(
                    baseline_perf.get("success_rate", 100) - current_perf.get("success_rate", 100), 1
                )
                
                # Determine severity
                severity = "NORMAL"
                is_anomaly = False
                if response_time_increase > 500 or success_rate_drop > 10:
                    severity = "CRITICAL"
                    is_anomaly = True
                elif response_time_increase > 200 or success_rate_drop > 5:
                    severity = "HIGH"
                    is_anomaly = True
                elif response_time_increase > 50 or success_rate_drop > 2:
                    severity = "MEDIUM"
                    is_anomaly = True
                
                comparison = {
                    "response_time_increase": response_time_increase,
                    "is_anomaly": is_anomaly,
                    "severity": severity,
                    "throughput_change": throughput_change,
                    "success_rate_drop": success_rate_drop
                }
                
                # Process endpoint breakdown
                endpoint_breakdown = []
                for table in endpoint_response.tables:
                    for row in table.rows:
                        endpoint_data = dict(zip([_col_name(col) for col in table.columns], row))
                        endpoint_breakdown.append({
                            "endpoint": endpoint_data.get("name"),
                            "current_avg_ms": round(endpoint_data.get("current_avg", 0)),
                            "baseline_avg_ms": round(endpoint_data.get("baseline_avg", 0)),
                            "increase_percent": endpoint_data.get("increase_percent", 0),
                            "request_count": endpoint_data.get("current_count", 0),
                            "failure_count": endpoint_data.get("current_failures", 0),
                            "impact": endpoint_data.get("impact", "LOW")
                        })
                
                # Process timeline
                performance_timeline = []
                degradation_start = None
                worst_period_start = None
                worst_response_time = 0
                
                for table in timeline_response.tables:
                    for row in table.rows:
                        timeline_data = dict(zip([_col_name(col) for col in table.columns], row))
                        avg_duration = timeline_data.get("avg_duration", 0)
                        
                        performance_timeline.append({
                            "timestamp": _format_datetime(timeline_data["timestamp"]),
                            "avg_response_time_ms": round(avg_duration),
                            "p95_response_time_ms": round(timeline_data.get("p95_duration", 0)),
                            "success_rate": round(timeline_data.get("success_rate", 0), 1)
                        })
                        
                        # Detect degradation start
                        if not degradation_start and avg_duration > baseline_perf.get("avg_response_time_ms", 0) * 2:
                            degradation_start = _format_datetime(timeline_data["timestamp"])
                        
                        # Track worst period
                        if avg_duration > worst_response_time:
                            worst_response_time = avg_duration
                            worst_period_start = _format_datetime(timeline_data["timestamp"])
                
                # Check SLO violations
                slo_violations = []
                if current_perf.get("p95_response_time_ms", 0) > 1000:
                    slo_violations.append(f"P95 response time exceeds 1000ms SLO (current: {current_perf['p95_response_time_ms']}ms)")
                if current_perf.get("success_rate", 100) < 99:
                    slo_violations.append(f"Success rate below 99% SLO (current: {current_perf['success_rate']}%)")
                if current_perf.get("p99_response_time_ms", 0) > 3000:
                    slo_violations.append(f"P99 response time exceeds 3000ms SLO (current: {current_perf['p99_response_time_ms']}ms)")
                
                # Generate insights
                insights = []
                if response_time_increase > 100:
                    factor = round(current_perf.get("avg_response_time_ms", 0) / baseline_perf.get("avg_response_time_ms", 1))
                    insights.append(f"Performance is {factor}x slower than baseline")
                
                high_impact_endpoints = [e for e in endpoint_breakdown if e["impact"] == "HIGH"]
                if high_impact_endpoints:
                    insights.append(f"{high_impact_endpoints[0]['endpoint']} showing severe degradation")
                
                if degradation_start:
                    insights.append(f"Issue started at {degradation_start} - check for deployments")
                
                if success_rate_drop > 5:
                    insights.append(f"High impact on user experience - {success_rate_drop}% more failures")
                
                # Generate recommendations
                recommendations = []
                if high_impact_endpoints:
                    for endpoint in high_impact_endpoints[:2]:
                        recommendations.append(
                            f"Focus on {endpoint['endpoint']} - showing {endpoint['increase_percent']}% slowdown"
                        )
                
                if severity == "CRITICAL":
                    recommendations.append("Consider rolling back recent changes")
                    recommendations.append("Check database query performance and connection pools")
                
                if throughput_change > 50:
                    recommendations.append("Traffic is higher than normal - consider scaling")
                
                return {
                    "current_performance": current_perf,
                    "baseline_performance": baseline_perf,
                    "comparison": comparison,
                    "endpoint_breakdown": endpoint_breakdown,
                    "time_based_analysis": {
                        "performance_timeline": performance_timeline[:10],  # Limit for readability
                        "degradation_start": degradation_start,
                        "worst_period": f"{worst_period_start} (avg: {round(worst_response_time)}ms)" if worst_period_start else None
                    },
                    "slo_violations": slo_violations,
                    "insights": insights,
                    "recommendations": recommendations,
                    "analysis_config": {
                        "current_period": {"from": start_date, "to": end_date},
                        "baseline_days": baseline_days,
                        "service_filter": service_name,
                        "endpoint_filter": endpoint_pattern
                    },
                    "status": "success"
                }
            else:
                return {
                    "error": "Failed to retrieve performance data",
                    "error_type": "QueryError"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to compare performance baseline: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def sync_wrapper(
        service_name: Optional[str] = None,
        endpoint_pattern: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        baseline_days: int = 7,
        percentiles: List[int] = None
    ) -> Dict[str, Any]:
        return _run_async(get_performance_baseline_comparison(
            service_name, endpoint_pattern, start_date, end_date, baseline_days, percentiles
        ))
    
    sync_wrapper.__doc__ = get_performance_baseline_comparison.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_performance_baseline_comparison,
        name="get_performance_baseline_comparison",
        description=get_performance_baseline_comparison.__doc__ or "Compare performance with baseline"
    )
    return tool


def create_find_first_occurrence_tool(secret_retriever: ISecretRetriever):
    """Factory function to create first occurrence finder tool with injected secret retriever."""
    
    async def find_first_occurrence(
        error_pattern: str,
        search_type: str = "message",
        lookback_hours: int = 24,
        include_context: bool = True
    ) -> Dict[str, Any]:
        """Find when a specific error or pattern first appeared to identify trigger events.
        
        This tool searches backwards in time to find the first occurrence of an error,
        helping identify what triggered the issue. It's essential for correlating
        errors with deployments, configuration changes, or other events.
        
        Use this tool for:
        - Identifying when a new error type first appeared
        - Correlating error start time with deployments
        - Finding the originating event for cascading failures
        - Determining if an error is new or recurring
        - Establishing timeline for incident reports
        
        Args:
            error_pattern: Pattern to search for (error message, exception type, etc.)
            search_type: Where to search - "message", "exception_type", "custom_dimension"
            lookback_hours: How many hours to search back (default 24, max 168/7 days)
            include_context: Include surrounding events for context (default True)
        
        Returns:
            Dict[str, Any]: First occurrence details with context.
            
            Success example:
            {
                "first_occurrence": {
                    "timestamp": "2024-01-15T10:32:15Z",
                    "operation_id": "abc123def456",
                    "error_message": "SqlTimeoutException: Timeout expired. The timeout period elapsed...",
                    "exception_type": "System.Data.SqlClient.SqlException",
                    "endpoint": "POST /api/order/create",
                    "duration_ms": 30000,
                    "service": "order-service"
                },
                "occurrence_timeline": [
                    {"timestamp": "2024-01-15T10:32:15Z", "count": 1},
                    {"timestamp": "2024-01-15T10:35:00Z", "count": 5},
                    {"timestamp": "2024-01-15T10:40:00Z", "count": 125},
                    {"timestamp": "2024-01-15T10:45:00Z", "count": 450}
                ],
                "context": {
                    "events_before": [
                        {
                            "timestamp": "2024-01-15T10:30:00Z",
                            "type": "deployment",
                            "message": "Deployed version 2.5.0 to order-service"
                        },
                        {
                            "timestamp": "2024-01-15T10:31:00Z",
                            "type": "config_change", 
                            "message": "Updated connection pool size from 100 to 50"
                        }
                    ],
                    "concurrent_errors": [
                        "Connection pool exhausted (started 10:31:45Z)",
                        "Redis timeout errors (started 10:33:00Z)"
                    ]
                },
                "analysis": {
                    "time_to_peak": "13 minutes",
                    "spread_pattern": "EXPONENTIAL",
                    "likely_trigger": "Configuration change at 10:31:00Z",
                    "is_new_error": true,
                    "previous_occurrence": null
                },
                "search_metadata": {
                    "pattern_searched": "SqlTimeoutException",
                    "search_type": "message",
                    "lookback_hours": 24,
                    "total_occurrences_found": 581
                },
                "recommendations": [
                    "Error first appeared 1 minute after config change",
                    "Connection pool reduction likely caused timeouts",
                    "Consider reverting connection pool size to 100"
                ],
                "status": "success"
            }
        """
        try:
            # Get credentials
            tenant_id = await secret_retriever.retrieve_optional_secret_value("AZURE_TENANT_ID")
            client_id = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_ID")
            client_secret = await secret_retriever.retrieve_optional_secret_value("AZURE_CLIENT_SECRET")
            resource_id = await secret_retriever.retrieve_mandatory_secret_value("AZURE_APP_RESOURCE")
            
            credential = _get_credential(tenant_id, client_id, client_secret)
            logs_client = LogsQueryClient(credential=credential)
            
            # Validate inputs
            lookback_hours = min(lookback_hours, 168)  # Max 7 days
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=lookback_hours)
            
            # Build search filter based on type
            search_filters = {
                "message": f"message contains '{error_pattern}' or innermostMessage contains '{error_pattern}'",
                "exception_type": f"type == '{error_pattern}' or customDimensions['Exception.Type'] == '{error_pattern}'",
                "custom_dimension": f"customDimensions contains '{error_pattern}'"
            }
            
            search_filter = search_filters.get(search_type, search_filters["message"])
            
            # Find first occurrence
            first_occurrence_query = f"""
            union isfuzzy=true
                (requests 
                | where timestamp >= datetime('{start_time.isoformat()}Z')
                | where success == false
                | extend error_message = tostring(customDimensions["Exception.Message"])
                | extend exception_type = tostring(customDimensions["Exception.Type"])),
                (exceptions
                | where timestamp >= datetime('{start_time.isoformat()}Z'))
            | where {search_filter}
            | order by timestamp asc
            | limit 1
            | project 
                timestamp,
                operation_Id,
                itemType,
                message,
                innermostMessage,
                type,
                method,
                name,
                url,
                duration,
                cloud_RoleName,
                customDimensions
            """
            
            # Get occurrence timeline
            timeline_query = f"""
            union isfuzzy=true
                (requests 
                | where timestamp >= datetime('{start_time.isoformat()}Z')
                | where success == false),
                (exceptions
                | where timestamp >= datetime('{start_time.isoformat()}Z'))
            | where {search_filter}
            | summarize count = count() by bin(timestamp, 5m)
            | order by timestamp asc
            | limit 50
            """
            
            # Execute queries
            first_response = logs_client.query_resource(resource_id, first_occurrence_query, timespan=None)
            timeline_response = logs_client.query_resource(resource_id, timeline_query, timespan=None)
            
            if first_response.status == LogsQueryStatus.SUCCESS:
                first_occurrence = None
                
                # Process first occurrence
                for table in first_response.tables:
                    if table.rows:
                        data = dict(zip([_col_name(col) for col in table.columns], row) for row in table.rows).__next__()
                        
                        first_occurrence = {
                            "timestamp": _format_datetime(data.get("timestamp")),
                            "operation_id": data.get("operation_Id"),
                            "error_message": data.get("message") or data.get("innermostMessage"),
                            "exception_type": data.get("type"),
                            "endpoint": data.get("name") or data.get("url"),
                            "duration_ms": data.get("duration"),
                            "service": data.get("cloud_RoleName"),
                            "item_type": data.get("itemType")
                        }
                        break
                
                if not first_occurrence:
                    return {
                        "error": f"No occurrences of '{error_pattern}' found in last {lookback_hours} hours",
                        "error_type": "NotFound",
                        "search_metadata": {
                            "pattern_searched": error_pattern,
                            "search_type": search_type,
                            "lookback_hours": lookback_hours
                        }
                    }
                
                # Process timeline
                occurrence_timeline = []
                total_occurrences = 0
                peak_count = 0
                peak_time = None
                
                for table in timeline_response.tables:
                    for row in table.rows:
                        timeline_data = dict(zip([_col_name(col) for col in table.columns], row))
                        count = timeline_data.get("count", 0)
                        total_occurrences += count
                        
                        occurrence_timeline.append({
                            "timestamp": _format_datetime(timeline_data["timestamp"]),
                            "count": count
                        })
                        
                        if count > peak_count:
                            peak_count = count
                            peak_time = timeline_data["timestamp"]
                
                # Get context if requested
                context = {}
                if include_context and first_occurrence["timestamp"]:
                    # Look for events around first occurrence
                    context_start = datetime.fromisoformat(first_occurrence["timestamp"].rstrip('Z')) - timedelta(minutes=10)
                    context_end = datetime.fromisoformat(first_occurrence["timestamp"].rstrip('Z')) + timedelta(minutes=5)
                    
                    # Check for deployment events, config changes, or other errors
                    context_query = f"""
                    union isfuzzy=true
                        (traces 
                        | where timestamp between(datetime('{context_start.isoformat()}Z') .. datetime('{context_end.isoformat()}Z'))
                        | where message contains "deploy" or message contains "config" or message contains "restart"
                        | project timestamp, message, severityLevel),
                        (exceptions
                        | where timestamp between(datetime('{context_start.isoformat()}Z') .. datetime('{context_end.isoformat()}Z'))
                        | where not({search_filter})
                        | summarize count = count(), first_seen = min(timestamp) by type
                        | project first_seen, type, count)
                    | order by timestamp asc
                    | limit 20
                    """
                    
                    context_response = logs_client.query_resource(resource_id, context_query, timespan=None)
                    
                    if context_response.status == LogsQueryStatus.SUCCESS:
                        events_before = []
                        concurrent_errors = []
                        
                        for table in context_response.tables:
                            for row in table.rows:
                                if len(table.columns) == 3 and "message" in [_col_name(col) for col in table.columns]:
                                    # This is a trace event
                                    event_data = dict(zip([_col_name(col) for col in table.columns], row))
                                    events_before.append({
                                        "timestamp": _format_datetime(event_data["timestamp"]),
                                        "type": "trace",
                                        "message": event_data.get("message", "")[:200]  # Truncate long messages
                                    })
                                else:
                                    # This is an error summary
                                    error_data = dict(zip([_col_name(col) for col in table.columns], row))
                                    concurrent_errors.append(
                                        f"{error_data.get('type')} (started {_format_datetime(error_data.get('first_seen'))})"
                                    )
                        
                        context = {
                            "events_before": events_before,
                            "concurrent_errors": concurrent_errors
                        }
                
                # Analyze spread pattern
                spread_pattern = "UNKNOWN"
                time_to_peak = None
                if len(occurrence_timeline) > 3:
                    # Check if exponential growth
                    growth_rates = []
                    for i in range(1, min(4, len(occurrence_timeline))):
                        if occurrence_timeline[i-1]["count"] > 0:
                            rate = occurrence_timeline[i]["count"] / occurrence_timeline[i-1]["count"]
                            growth_rates.append(rate)
                    
                    if growth_rates and all(rate >= 2 for rate in growth_rates):
                        spread_pattern = "EXPONENTIAL"
                    elif growth_rates and all(1 <= rate <= 2 for rate in growth_rates):
                        spread_pattern = "LINEAR"
                    else:
                        spread_pattern = "IRREGULAR"
                    
                    # Calculate time to peak
                    if peak_time and first_occurrence["timestamp"]:
                        first_time = datetime.fromisoformat(first_occurrence["timestamp"].rstrip('Z'))
                        peak_datetime = peak_time
                        time_diff = (peak_datetime - first_time).total_seconds() / 60
                        time_to_peak = f"{int(time_diff)} minutes"
                
                # Generate analysis
                analysis = {
                    "time_to_peak": time_to_peak,
                    "spread_pattern": spread_pattern,
                    "is_new_error": True,  # We found it within lookback period
                    "previous_occurrence": None  # Would need longer lookback to determine
                }
                
                # Look for likely triggers
                if context.get("events_before"):
                    deploy_events = [e for e in context["events_before"] if "deploy" in e.get("message", "").lower()]
                    config_events = [e for e in context["events_before"] if "config" in e.get("message", "").lower()]
                    
                    if deploy_events:
                        analysis["likely_trigger"] = f"Deployment at {deploy_events[0]['timestamp']}"
                    elif config_events:
                        analysis["likely_trigger"] = f"Configuration change at {config_events[0]['timestamp']}"
                
                # Generate recommendations
                recommendations = []
                if analysis.get("likely_trigger"):
                    recommendations.append(f"Error appeared shortly after {analysis['likely_trigger']}")
                
                if spread_pattern == "EXPONENTIAL":
                    recommendations.append("Exponential error growth indicates cascading failure")
                
                if total_occurrences > 1000:
                    recommendations.append("High error volume - immediate action required")
                
                return {
                    "first_occurrence": first_occurrence,
                    "occurrence_timeline": occurrence_timeline,
                    "context": context,
                    "analysis": analysis,
                    "search_metadata": {
                        "pattern_searched": error_pattern,
                        "search_type": search_type,
                        "lookback_hours": lookback_hours,
                        "total_occurrences_found": total_occurrences
                    },
                    "recommendations": recommendations,
                    "status": "success"
                }
            else:
                return {
                    "error": f"Failed to search for first occurrence: {first_response.status}",
                    "error_type": "QueryError"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to find first occurrence: {str(e)}",
                "error_type": type(e).__name__
            }
    
    def sync_wrapper(
        error_pattern: str,
        search_type: str = "message",
        lookback_hours: int = 24,
        include_context: bool = True
    ) -> Dict[str, Any]:
        return _run_async(find_first_occurrence(error_pattern, search_type, lookback_hours, include_context))
    
    sync_wrapper.__doc__ = find_first_occurrence.__doc__
    
    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=find_first_occurrence,
        name="find_first_occurrence",
        description=find_first_occurrence.__doc__ or "Find first occurrence of error pattern"
    )
    return tool
