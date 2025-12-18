import asyncio
import json
import ssl
import urllib3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import certifi
import requests
from langchain_core.tools import StructuredTool

from fx_ai_reusables.environment_loading.interfaces.datadog_config_reader_interface import IDatadogConfigReader

# Import Datadog SDK components
try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v2.api.spans_api import SpansApi
    from datadog_api_client.v2.model.spans_list_request import SpansListRequest
    from datadog_api_client.v2.model.spans_list_request_attributes import SpansListRequestAttributes
    from datadog_api_client.v2.model.spans_list_request_data import SpansListRequestData
    from datadog_api_client.v2.model.spans_list_request_page import SpansListRequestPage
    from datadog_api_client.v2.model.spans_list_request_type import SpansListRequestType
    from datadog_api_client.v2.model.spans_query_filter import SpansQueryFilter
    from datadog_api_client.v2.model.spans_query_options import SpansQueryOptions
    from datadog_api_client.v2.model.spans_sort import SpansSort
    DATADOG_SDK_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Datadog SDK import failed: {e}")
    DATADOG_SDK_AVAILABLE = False


def _run_async(coroutine):
    """Helper to run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, we can't use run_until_complete
            # This shouldn't happen in normal LangChain usage
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


def create_get_datadog_service_dependencies_tool(
    datadog_config_reader: IDatadogConfigReader
):
    """Factory function to create Datadog service dependencies tool with injected dependencies.
    
    This factory uses closure pattern to inject the datadog_config_reader dependency.
    The returned tool closes over this variable, making it available when the LLM invokes the tool.
    
    Args:
        datadog_config_reader: IDatadogConfigReader instance for fetching all Datadog settings
        
    Returns:
        Configured tool instance that the LLM can call
    """
    async def get_datadog_service_dependencies(
        service_name: Optional[str] = None,
        env: str = "*",
        primary_tag: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """Retrieve APM service dependencies from DataDog Service Dependencies API.
    
    This function uses DataDog's Service Dependencies API (currently in public beta) to
    retrieve service dependency information. It can get either all service dependencies
    or dependencies for a specific service, showing which services call each other.
    
    This API provides more accurate and structured service relationship data compared
    to parsing metrics, making it ideal for incident response, troubleshooting, and
    understanding service architecture.
    
    When to use:
    - Map service dependencies during incident analysis
    - Understand upstream/downstream impacts of service failures
    - Identify service relationships for troubleshooting
    - Get structured APM service dependency data
    - Analyze service architecture and communication patterns
    
    Args:
        service_name: Optional specific service name to get dependencies for.
                     If provided, returns dependencies for this service only.
                     If None, returns all service dependencies.
        env: Environment to query. Examples: 'prod', 'staging', 'dev', '*'.
             Defaults to '*' which queries all environments.
             Must match the environment name in DataDog APM.
        primary_tag: Optional primary tag to filter services by.
                    Used for additional filtering beyond environment.
        start_time: Optional start time in epoch seconds. 
                   Defaults to 1 hour before end_time if not provided.
        end_time: Optional end time in epoch seconds.
                 Defaults to current time if not provided.
    
    Returns:
        Dict[str, Any]: Dictionary containing service dependency information.
                       
                       For specific service:
                       {
                           "service_name": "web-api",
                           "called_by": ["load-balancer", "api-gateway"],
                           "calls": ["payment-service", "user-service"],
                           "dependencies": {
                               "upstream": ["load-balancer", "api-gateway"],
                               "downstream": ["payment-service", "user-service"]
                           },
                           "environment": "*",
                           "query_params": {"env": "*", "service": "web-api"}
                       }
                       
                       For all services:
                       {
                           "services": {
                               "web-api": {
                                   "called_by": ["load-balancer"],
                                   "calls": ["payment-service", "user-service"],
                                   "name": "web-api"
                               },
                               "payment-service": {
                                   "called_by": ["web-api", "checkout-service"],
                                   "calls": ["database", "notification-service"],
                                   "name": "payment-service"
                               }
                           },
                           "total_services": 2,
                           "environment": "*",
                           "query_params": {"env": "*"}
                       }
                       
                       Error example:
                       {
                           "error": "Environment 'invalid-env' not found",
                           "error_type": "EnvironmentError",
                           "api_endpoint": "/api/v1/service_dependencies"
                       }
    
    Raises:
        Exception: Captured and returned as error dict. Common causes include:
                  - Missing or invalid DataDog API credentials
                  - Invalid environment name
                  - Service not found (for specific service queries)
                  - Network connectivity issues
                  - API rate limiting
    
    Note:
        - Requires DATADOG_API_KEY and DATADOG_APP_KEY environment variables
        - This API is currently in public beta
        - Environment parameter defaults to '*' for all environments
        - Service names are case-sensitive
        - Time range affects which dependencies are returned
        - Returns immediate dependencies only (not transitive)
        """
        
        # Get DataDog configuration from datadog_config_reader (injected via closure)
        datadog_config = await datadog_config_reader.read_datadog_config()
        
        api_key = datadog_config.DATADOG_API_KEY
        app_key = datadog_config.DATADOG_APP_KEY
        base_url = datadog_config.DATADOG_API_URL
        timeout = datadog_config.DATADOG_TIMEOUT
        
        try:
            
            # Build query parameters
            params = {"env": env}
            if primary_tag:
                params["primary_tag"] = primary_tag
            if start_time:
                params["start"] = start_time
            if end_time:
                params["end"] = end_time
            
            # Set up headers
            headers = {
                "Accept": "application/json",
                "DD-API-KEY": api_key,
                "DD-APPLICATION-KEY": app_key
            }
            
            # Choose endpoint based on whether specific service is requested
            if service_name:
                # Get dependencies for specific service
                endpoint = f"{base_url}/api/v1/service_dependencies/{service_name}"
                operation = "get_specific_service_dependencies"
            else:
                # Get all service dependencies
                endpoint = f"{base_url}/api/v1/service_dependencies"
                operation = "get_all_service_dependencies"
            
            # Make API request with SSL configuration
            try:
                # Configure SSL session
                session = requests.Session()
                session.verify = certifi.where()
                
                response = session.get(
                    endpoint,
                    params=params,
                    headers=headers,
                    timeout=timeout
                )
                
                # Check response status
                if response.status_code == 200:
                    data = response.json()
                    
                    # Process response based on operation type
                    if service_name:
                        # Single service response processing
                        if isinstance(data, dict):
                            result = {
                                "service_name": service_name,
                                "called_by": data.get("called_by", []),
                                "calls": data.get("calls", []),
                                "dependencies": {
                                    "upstream": data.get("called_by", []),
                                    "downstream": data.get("calls", [])
                                },
                                "environment": env,
                                "api_endpoint": f"/api/v1/service_dependencies/{service_name}",
                                "query_params": params,
                                "status": "success"
                            }
                        else:
                            result = {
                                "service_name": service_name,
                                "called_by": [],
                                "calls": [],
                                "dependencies": {"upstream": [], "downstream": []},
                                "environment": env,
                                "warning": "Unexpected response format from API",
                                "raw_response": data,
                                "api_endpoint": f"/api/v1/service_dependencies/{service_name}",
                                "query_params": params,
                                "status": "success_with_warning"
                            }
                    else:
                        # All services response processing
                        if isinstance(data, dict):
                            services_data = {}
                            total_count = 0
                            
                            # Process each service in the response
                            for key, value in data.items():
                                if isinstance(value, dict):
                                    services_data[key] = {
                                        "called_by": value.get("called_by", []),
                                        "calls": value.get("calls", []),
                                        "name": value.get("name", key)
                                    }
                                    total_count += 1
                            
                            result = {
                                "services": services_data,
                                "total_services": total_count,
                                "environment": env,
                                "api_endpoint": "/api/v1/service_dependencies",
                                "query_params": params,
                                "status": "success"
                            }
                        else:
                            result = {
                                "services": {},
                                "total_services": 0,
                                "environment": env,
                                "warning": "Unexpected response format from API",
                                "raw_response": data,
                                "api_endpoint": "/api/v1/service_dependencies",
                                "query_params": params,
                                "status": "success_with_warning"
                            }
                    
                    return result
                    
                elif response.status_code == 400:
                    return {
                        "error": f"Bad request: Invalid parameters. Check environment '{env}' and other parameters.",
                        "error_type": "BadRequestError",
                        "status_code": 400,
                        "api_endpoint": endpoint.replace(base_url, ""),
                        "query_params": params,
                        "response_text": response.text[:500] if response.text else "No response body"
                    }
                elif response.status_code == 403:
                    return {
                        "error": "Access forbidden: Check API key permissions for Service Dependencies API",
                        "error_type": "PermissionError",
                        "status_code": 403,
                        "api_endpoint": endpoint.replace(base_url, ""),
                        "note": "Service Dependencies API is in public beta - ensure access is enabled"
                    }
                elif response.status_code == 404:
                    if service_name:
                        return {
                            "error": f"Service '{service_name}' not found in environment '{env}'",
                            "error_type": "ServiceNotFoundError",
                            "status_code": 404,
                            "api_endpoint": endpoint.replace(base_url, ""),
                            "query_params": params
                        }
                    else:
                        return {
                            "error": f"Environment '{env}' not found or has no services",
                            "error_type": "EnvironmentError",
                            "status_code": 404,
                            "api_endpoint": endpoint.replace(base_url, "")
                        }
                elif response.status_code == 429:
                    return {
                        "error": "Rate limit exceeded: Too many requests to DataDog API",
                        "error_type": "RateLimitError",
                        "status_code": 429,
                        "api_endpoint": endpoint.replace(base_url, ""),
                        "retry_after": response.headers.get("Retry-After", "unknown")
                    }
                else:
                    return {
                        "error": f"API request failed with status {response.status_code}",
                        "error_type": "APIError",
                        "status_code": response.status_code,
                        "api_endpoint": endpoint.replace(base_url, ""),
                        "response_text": response.text[:500] if response.text else "No response body"
                    }
                    
            except requests.exceptions.SSLError as ssl_error:
                return {
                    "error": f"SSL connection failed: {str(ssl_error)}",
                    "error_type": "SSLError",
                    "suggestion": "Check network connectivity and certificate configuration"
                }
            except requests.exceptions.Timeout:
                return {
                    "error": "Request timeout: DataDog API did not respond in time",
                    "error_type": "TimeoutError",
                    "suggestion": "Try again or check DataDog API status"
                }
            except requests.exceptions.RequestException as req_error:
                return {
                    "error": f"Network request failed: {str(req_error)}",
                    "error_type": "NetworkError"
                }
                
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            return {
                "error": f"Unexpected error: {error_message}",
                "error_type": error_type,
                "operation": operation if 'operation' in locals() else "unknown"
            }
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(
        service_name: Optional[str] = None,
        env: str = "*",
        primary_tag: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return _run_async(get_datadog_service_dependencies(
            service_name, env, primary_tag, start_time, end_time
        ))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = get_datadog_service_dependencies.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=get_datadog_service_dependencies,  # Async version
        name="get_datadog_service_dependencies",
        description=get_datadog_service_dependencies.__doc__ or "Retrieve APM service dependencies from DataDog",
    )
    return tool


def create_find_service_errors_and_traces_tool(
    datadog_config_reader: IDatadogConfigReader
):
    """Factory function to create Datadog service errors and traces tool with injected dependencies.
    
    This factory uses closure pattern to inject the datadog_config_reader dependency.
    The returned tool closes over this variable, making it available when the LLM invokes the tool.
    
    Args:
        datadog_config_reader: IDatadogConfigReader instance for fetching all Datadog settings
        
    Returns:
        Configured tool instance that the LLM can call
    """
    async def find_service_errors_and_traces(
        service_name: str,
        env: str = "*",
        time_range_minutes: int = 60,
        max_traces: int = 50,
        http_status_code: Optional[str] = None,
        exclude_healthchecks: bool = True,
        custom_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Find error traces for a specific service and identify which downstream services/APIs are causing the errors.
    
    This tool uses advanced Datadog query syntax to precisely search for error traces in Datadog APM
    and provides detailed information about which downstream services, APIs, or dependencies are the 
    source of errors. It focuses purely on error detection and downstream service identification.
    
    Args:
        service_name: Name of the service to find errors for (case-sensitive).
                     Must match the service name in Datadog APM.
        env: Environment to search. Examples: 'prod-blue', 'staging', 'dev', '*'.
             Defaults to '*' for all environments.
        time_range_minutes: Number of minutes to look back from current time.
                           Defaults to 60 minutes.
        max_traces: Maximum number of error traces to retrieve and analyze.
                   Defaults to 50.
        http_status_code: Specific HTTP status code to filter by (e.g., '500', '404', '>=400').
                         Can use comparison operators like '>=500' or range '[400 TO 499]'.
        exclude_healthchecks: Whether to exclude health check operations from results.
                            Defaults to True to reduce noise.
        custom_query: Advanced custom query string to override default query building.
                     Uses full Datadog query syntax.
    
    Returns:
        Dict[str, Any]: Dictionary containing error traces and downstream service information.
    
    Note:
        - Requires DATADOG_API_KEY and DATADOG_APP_KEY environment variables
        - Uses official Datadog SDK v2 for spans API with advanced query syntax
        - Uses -status:ok instead of status:error for more precise error detection
        - Supports full Datadog query syntax including wildcards, ranges, and boolean operators
        """
        
        # Get DataDog configuration from datadog_config_reader (injected via closure)
        datadog_config = await datadog_config_reader.read_datadog_config()
        
        api_key = datadog_config.DATADOG_API_KEY
        app_key = datadog_config.DATADOG_APP_KEY
        
        if not DATADOG_SDK_AVAILABLE:
            return {
                "error": "Datadog SDK not available. Please install: pip install datadog-api-client",
                "error_type": "SDKNotAvailableError",
                "service_name": service_name,
                "environment": env
            }
        
        try:
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=time_range_minutes)
            
            # Format times for Datadog SDK (relative time format)
            start_relative = f"now-{time_range_minutes}m"
            end_relative = "now"
            
            # Build advanced search query using Datadog syntax
            if custom_query:
                # Use provided custom query
                error_query = custom_query
            else:
                # Build query using advanced syntax patterns
                query_parts = []
                
                # Environment filter (if not wildcard)
                if env != "*":
                    query_parts.append(f"env:{env}")
                
                # Service filter
                query_parts.append(f"service:{service_name}")
                
                # Error detection using -status:ok (more precise than status:error)
                query_parts.append("-status:ok")
                
                # HTTP status code filter (if specified)
                if http_status_code:
                    # Handle different status code formats
                    if http_status_code.startswith("[") and http_status_code.endswith("]"):
                        # Range query like [400 TO 499]
                        query_parts.append(f"@http.status_code:{http_status_code}")
                    elif any(op in http_status_code for op in [">=", "<=", ">", "<"]):
                        # Comparison query like >=500
                        query_parts.append(f"@http.status_code:{http_status_code}")
                    else:
                        # Exact status code like 500
                        query_parts.append(f"@http.status_code:{http_status_code}")
                
                # Exclude health checks to reduce noise
                if exclude_healthchecks:
                    query_parts.extend([
                        "-operation_name:*health*",
                        "-operation_name:*ping*",
                        "-resource_name:*health*",
                        "-resource_name:*ping*"
                    ])
                
                # Combine all parts with AND (default operator)
                error_query = " ".join(query_parts)
            
            # Configure Datadog SDK with SSL settings
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = api_key
            configuration.api_key["appKeyAuth"] = app_key
            
            # Add SSL configuration to handle certificate verification
            import ssl
            import urllib3
            
            # Disable SSL warnings and configure SSL context
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Set SSL verify to use system certificates
            configuration.verify_ssl = True
            configuration.ssl_ca_cert = certifi.where()
            
            # Create the spans request using SDK models following the documentation example
            body = SpansListRequest(
                data=SpansListRequestData(
                    attributes=SpansListRequestAttributes(
                        filter=SpansQueryFilter(
                            _from=start_relative,
                            query=error_query,
                            to=end_relative,
                        ),
                        options=SpansQueryOptions(
                            timezone="GMT",
                        ),
                        page=SpansListRequestPage(
                            limit=max_traces,
                        ),
                        sort=SpansSort.TIMESTAMP_DESCENDING,  # Most recent errors first
                    ),
                    type=SpansListRequestType.SEARCH_REQUEST,
                ),
            )
            
            # Execute search using official SDK
            with ApiClient(configuration) as api_client:
                api_instance = SpansApi(api_client)
                response = api_instance.list_spans(body=body)
            
            # Check if we got data
            if not response.data:
                return {
                    "error": f"No error traces found for service '{service_name}' in environment '{env}' in the last {time_range_minutes} minutes",
                    "error_type": "NoDataFoundError",
                    "service_name": service_name,
                    "environment": env,
                    "time_range_minutes": time_range_minutes,
                    "query_used": error_query
                }
            
            # Store the complete raw response data without any processing or formatting
            raw_spans_data = []
            
            for span in response.data:
                # Use the SDK's to_dict() method if available, or manual conversion
                try:
                    if hasattr(span, 'to_dict'):
                        # Use built-in serialization method
                        span_dict = span.to_dict()
                    else:
                        # Manual conversion - get the raw data as JSON-serializable dict
                        span_dict = {
                            "id": str(span.id) if span.id else None,
                            "type": getattr(span, 'type', 'spans'),
                            "attributes": {}
                        }
                        
                        # Convert attributes to dict safely
                        if hasattr(span, 'attributes') and span.attributes:
                            if hasattr(span.attributes, 'to_dict'):
                                span_dict["attributes"] = span.attributes.to_dict()
                            else:
                                # Try to access the raw dictionary from the SDK response
                                # The SDK usually stores the raw data in _data_store or similar
                                if hasattr(span.attributes, '_data_store'):
                                    span_dict["attributes"] = span.attributes._data_store
                                elif hasattr(span.attributes, 'actual_instance'):
                                    span_dict["attributes"] = span.attributes.actual_instance
                                else:
                                    # Fallback to empty dict if we can't extract
                                    span_dict["attributes"] = {}
                    
                    raw_spans_data.append(span_dict)
                    
                except Exception as span_error:
                    # If individual span fails, add error info but continue
                    raw_spans_data.append({
                        "id": str(span.id) if hasattr(span, 'id') and span.id else "unknown",
                        "type": "spans",
                        "attributes": {},
                        "extraction_error": str(span_error)
                    })
            
            # Calculate basic summary statistics
            total_spans = len(raw_spans_data)
            
            return {
                "service_name": service_name,
                "environment": env,
                "time_period": {
                    "start_time": start_relative,
                    "end_time": end_relative,
                    "duration_minutes": time_range_minutes
                },
                "query_used": error_query,
                "total_spans": total_spans,
                "spans_data": raw_spans_data,  # Complete raw response data
                "status": "success",
                "sdk_version": "official_datadog_sdk_v2",
                "advanced_query_syntax": True,
                "data_format": "complete_raw_response"
            }
        
        except Exception as e:
            return {
                "error": f"Failed to retrieve error traces using SDK: {str(e)}",
                "error_type": type(e).__name__,
                "service_name": service_name,
                "environment": env
            }
    
    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(
        service_name: str,
        env: str = "*",
        time_range_minutes: int = 60,
        max_traces: int = 50,
        http_status_code: Optional[str] = None,
        exclude_healthchecks: bool = True,
        custom_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return _run_async(find_service_errors_and_traces(
            service_name, env, time_range_minutes, max_traces,
            http_status_code, exclude_healthchecks, custom_query
        ))
    
    # Preserve the docstring
    sync_wrapper.__doc__ = find_service_errors_and_traces.__doc__
    
    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=find_service_errors_and_traces,  # Async version
        name="find_service_errors_and_traces",
        description=find_service_errors_and_traces.__doc__ or "Find error traces for a service",
    )
    return tool