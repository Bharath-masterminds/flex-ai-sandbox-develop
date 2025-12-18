import asyncio
from langchain_core.tools import StructuredTool
from typing import Dict, Any, List, Optional
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from dynatrace import Dynatrace
from dynatrace.pagination import PaginatedList


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


def create_list_dynatrace_services_tool(secret_retriever: ISecretRetriever):
    """Factory function to create Dynatrace service listing tool with injected secret retriever.

    Args:
        secret_retriever: ISecretRetriever instance for fetching Dynatrace credentials

    Returns:
        Configured tool instance that the LLM can call
    """

    async def list_dynatrace_services(
        name_filter: Optional[str] = None,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List all Dynatrace services with optional name filtering.

        This function efficiently retrieves a list of all services monitored by Dynatrace.
        Use this tool FIRST to discover available services before querying dependencies,
        errors, or metrics for specific services.

        This is a lightweight operation that only retrieves service IDs and names,
        without fetching dependency relationships which would be resource-intensive
        for large environments (e.g., 1400+ services).

        When to use:
        - Discover all available services in the environment
        - Search for services by name pattern or keyword
        - Get service IDs needed for other tool operations
        - Understand the service landscape during incident analysis
        - Find services related to a specific application or component

        Args:
            name_filter: Optional case-insensitive substring to filter services by name.
                        Example: "auth" will match "authentication-service", "auth-api", etc.
                        If None, returns all services.
            from_timestamp: Optional start time in ISO 8601 format or relative time (e.g., "now-2h").
                           Filters services active in this time range.
                           Defaults to "now-2h" if not provided.
            to_timestamp: Optional end time in ISO 8601 format or relative time (e.g., "now").
                         Defaults to "now" if not provided.
            max_results: Optional maximum number of services to return.
                        If None, returns all matching services.
                        Use this to limit results for large environments.

        Returns:
            Dict[str, Any]: Dictionary containing service list.

                           Success example:
                           {
                               "services": [
                                   {
                                       "id": "SERVICE-XXXXXXXXXXXXX",
                                       "name": "authentication-service",
                                       "type": "SERVICE"
                                   },
                                   {
                                       "id": "SERVICE-YYYYYYYYYYYYY",
                                       "name": "user-management-api",
                                       "type": "SERVICE"
                                   }
                               ],
                               "total_services": 2,
                               "filter_applied": "auth",
                               "time_range": {"from": "now-2h", "to": "now"},
                               "status": "success"
                           }

                           Error example:
                           {
                               "error": "Failed to retrieve services",
                               "error_type": "APIError"
                           }

        Raises:
            Exception: Captured and returned as error dict. Common causes include:
                      - Missing or invalid Dynatrace credentials
                      - Network connectivity issues
                      - API rate limiting

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
            - Returns service metadata only (no dependencies, metrics, or errors)
            - Use get_dynatrace_service_dependencies() after identifying specific services
            - Service IDs follow format SERVICE-XXXXXXXXXXXXX
        """

        # Get Dynatrace credentials from secret retriever
        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")
        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            # Initialize Dynatrace client
            dt_client = Dynatrace(base_url, api_token)

            # Set default time range if not provided
            if not from_timestamp:
                from_timestamp = "now-2h"
            if not to_timestamp:
                to_timestamp = "now"

            # Get all services
            services = dt_client.entities.list(
                entity_selector="type(SERVICE)", time_from=from_timestamp, time_to=to_timestamp
            )

            # Convert to list and extract basic info
            services_data = []
            for service in services:
                service_info = {
                    "id": service.entity_id,
                    "name": service.display_name,
                    "type": "SERVICE",
                }

                # Apply name filter if provided
                if name_filter is None or name_filter.lower() in service.display_name.lower():
                    services_data.append(service_info)

                # Apply max_results limit if specified
                if max_results and len(services_data) >= max_results:
                    break

            return {
                "services": services_data,
                "total_services": len(services_data),
                "filter_applied": name_filter,
                "time_range": {"from": from_timestamp, "to": to_timestamp},
                "status": "success",
            }

        except Exception as e:
            return {"error": f"Failed to retrieve services: {str(e)}", "error_type": type(e).__name__}

    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(
        name_filter: Optional[str] = None,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return _run_async(list_dynatrace_services(name_filter, from_timestamp, to_timestamp, max_results))

    # Preserve the docstring
    sync_wrapper.__doc__ = list_dynatrace_services.__doc__

    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=list_dynatrace_services,  # Async version
        name="list_dynatrace_services",
        description=list_dynatrace_services.__doc__ or "List all Dynatrace services with optional name filtering",
    )
    return tool


def create_get_dynatrace_service_dependencies_tool(secret_retriever: ISecretRetriever):
    """Factory function to create Dynatrace service dependencies tool with injected secret retriever.

    This factory uses closure pattern to inject the secret_retriever dependency.
    The returned tool closes over the secret_retriever variable, making it available
    when the LLM invokes the tool.

    Args:
        secret_retriever: ISecretRetriever instance for fetching Dynatrace credentials

    Returns:
        Configured tool instance that the LLM can call
    """

    async def get_dynatrace_service_dependencies(
        service_id: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve upstream/downstream dependencies for a specific Dynatrace service.

        This function uses Dynatrace's Smartscape topology API to retrieve service
        dependency information for a SPECIFIC service. It shows which services call
        this service (upstream/callers) and which services this service calls (downstream/callees).

        This API provides structured service relationship data discovered by Dynatrace's
        automated topology mapping, making it ideal for incident response, troubleshooting,
        and understanding service architecture.

        IMPORTANT: This tool requires a specific service_id. To discover available services,
        use list_dynatrace_services() first. Querying dependencies for all services is
        resource-intensive and should be avoided.

        When to use:
        - Map dependencies for a specific service during incident analysis
        - Understand upstream/downstream impacts of a service failure
        - Identify relationships for a known service
        - Analyze cascade failures from a specific service
        - Perform impact analysis for changes to a specific service

        Args:
            service_id: REQUIRED Dynatrace service entity ID to get dependencies for.
                       Format: "SERVICE-XXXXXXXXXXXXX"
                       Use list_dynatrace_services() to discover service IDs.
            from_timestamp: Optional start time in ISO 8601 format or relative time (e.g., "now-2h").
                           Defaults to "now-2h" if not provided.
            to_timestamp: Optional end time in ISO 8601 format or relative time (e.g., "now").
                         Defaults to "now" if not provided.

        Returns:
            Dict[str, Any]: Dictionary containing service dependency information.

                           Success example:
                           {
                               "service_id": "SERVICE-XXXXX",
                               "service_name": "web-api",
                               "called_by": [{"id": "SERVICE-YYYYY", "name": "load-balancer"}],
                               "calls": [{"id": "SERVICE-ZZZZZ", "name": "payment-service"}],
                               "dependencies": {
                                   "upstream": [...],
                                   "downstream": [...]
                               },
                               "time_range": {"from": "now-2h", "to": "now"},
                               "status": "success"
                           }

                           Error example:
                           {
                               "error": "Service not found",
                               "error_type": "ServiceNotFoundError",
                               "service_id": "SERVICE-XXXXX"
                           }

        Raises:
            Exception: Captured and returned as error dict. Common causes include:
                      - Missing or invalid Dynatrace credentials
                      - Invalid service ID format
                      - Service not found
                      - Network connectivity issues
                      - API rate limiting

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
            - Service IDs follow format SERVICE-XXXXXXXXXXXXX
            - Time range affects which dependencies are returned
            - Returns immediate dependencies only (not transitive)
            - Uses Dynatrace Smartscape topology API
            - For discovering services, use list_dynatrace_services() first
        """

        # Get Dynatrace credentials from secret retriever
        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")
        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            # Initialize Dynatrace client
            dt_client = Dynatrace(base_url, api_token)

            # Set default time range if not provided
            if not from_timestamp:
                from_timestamp = "now-2h"
            if not to_timestamp:
                to_timestamp = "now"

            # Get dependencies for specific service
            try:
                # Get the service entity
                entity = dt_client.entities.get(entity_id=service_id)

                # Get upstream (services that call this service) and downstream (services called by this service)
                # Note: toRelationships.calls() finds services that ARE CALLED BY the specified service
                # fromRelationships.calls() finds services that CALL the specified service
                from_relationships = dt_client.entities.list(
                    entity_selector=f"type(SERVICE),fromRelationships.calls(entityId({service_id}))",
                    time_from=from_timestamp,
                    time_to=to_timestamp,
                )

                to_relationships = dt_client.entities.list(
                    entity_selector=f"type(SERVICE),toRelationships.calls(entityId({service_id}))",
                    time_from=from_timestamp,
                    time_to=to_timestamp,
                )

                called_by = [{"id": e.entity_id, "name": e.display_name} for e in from_relationships]
                calls = [{"id": e.entity_id, "name": e.display_name} for e in to_relationships]

                return {
                    "service_id": service_id,
                    "service_name": entity.display_name if entity else service_id,
                    "called_by": called_by,
                    "calls": calls,
                    "dependencies": {"upstream": called_by, "downstream": calls},
                    "time_range": {"from": from_timestamp, "to": to_timestamp},
                    "status": "success",
                }
            except Exception as e:
                return {
                    "error": f"Failed to retrieve dependencies for service {service_id}: {str(e)}",
                    "error_type": type(e).__name__,
                    "service_id": service_id,
                }

        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}", "error_type": type(e).__name__}

    # Create sync wrapper for compatibility with LangGraph
    def sync_wrapper(
        service_id: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sync wrapper that runs the async function."""
        return _run_async(get_dynatrace_service_dependencies(service_id, from_timestamp, to_timestamp))

    # Preserve the docstring
    sync_wrapper.__doc__ = get_dynatrace_service_dependencies.__doc__

    # Create and return the StructuredTool with both sync and async support
    tool = StructuredTool.from_function(
        func=sync_wrapper,  # Sync wrapper for compatibility
        coroutine=get_dynatrace_service_dependencies,  # Async version
        name="get_dynatrace_service_dependencies",
        description=get_dynatrace_service_dependencies.__doc__
        or "Retrieve upstream/downstream dependencies for Dynatrace services",
    )
    return tool


def create_find_service_errors_and_traces_tool(secret_retriever: ISecretRetriever):
    """Factory function to create service errors and traces tool with injected secret retriever."""

    async def find_service_errors_and_traces(
        service_id: str,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Find error traces for a specific service and identify downstream root causes.

        This tool uses Dynatrace's Problems API and metrics to find errors affecting a service.
        It retrieves problems that have been detected by Dynatrace's automated monitoring and
        provides information about affected entities, root causes, and error rates.

        When to use:
        - Identify errors occurring in a specific service
        - Find root causes of service failures
        - Analyze error patterns and trends
        - Investigate downstream service impacts
        - Troubleshoot cascading failures
        - Correlate errors with infrastructure issues

        Args:
            service_id: Dynatrace service entity ID to find errors for.
                       Format: "SERVICE-XXXXXXXXXXXXX"
            from_timestamp: Start time in ISO 8601 format or relative time (e.g., "now-1h").
                           Defaults to "now-1h" if not provided.
            to_timestamp: End time in ISO 8601 format or relative time (e.g., "now").
                         Defaults to "now" if not provided.
            max_results: Maximum number of error traces to retrieve and analyze.
                        Defaults to 50.

        Returns:
            Dict[str, Any]: Dictionary containing error traces and root cause information.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
            - Retrieves problems detected by Dynatrace's automated monitoring
            - Analyzes both application and infrastructure problems
            - Correlates errors with service dependencies
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            if not from_timestamp:
                from_timestamp = "now-1h"
            if not to_timestamp:
                to_timestamp = "now"

            problems = dt_client.problems.list(
                entity_selector=f'entityId("{service_id}")', time_from=from_timestamp, time_to=to_timestamp
            )

            problems_data = []
            for problem in problems:
                problem_details = dt_client.problems.get(problem_id=problem.problem_id)
                problems_data.append(
                    {
                        "problem_id": problem.problem_id,
                        "title": problem.title,
                        "impact_level": problem.impact_level,
                        "severity_level": problem.severity_level,
                        "status": problem.status,
                        "affected_entities": [{"id": e.entity_id, "name": e.name} for e in problem.affected_entities],
                        "root_cause": problem.root_cause_entity if hasattr(problem, "root_cause_entity") else None,
                    }
                )

            try:
                error_rate_metric = dt_client.metrics.query(
                    metric_selector="builtin:service.errors.server.rate",
                    entity_selector=f'entityId("{service_id}")',
                    time_from=from_timestamp,
                    time_to=to_timestamp,
                )

                error_rate = None
                if error_rate_metric and len(error_rate_metric.result) > 0:
                    data_points = error_rate_metric.result[0].data
                    if data_points:
                        error_rate = {
                            "average": sum(dp.values[0] for dp in data_points) / len(data_points),
                            "max": max(dp.values[0] for dp in data_points),
                            "min": min(dp.values[0] for dp in data_points),
                        }
            except Exception as e:
                error_rate = {"error": str(e)}

            return {
                "service_id": service_id,
                "errors_found": len(problems_data),
                "problems": problems_data[:max_results],
                "error_rate": error_rate,
                "time_range": {"from": from_timestamp, "to": to_timestamp},
                "status": "success",
            }

        except Exception as e:
            return {
                "error": f"Failed to retrieve error traces: {str(e)}",
                "error_type": type(e).__name__,
                "service_id": service_id,
            }

    def sync_wrapper(
        service_id: str,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        return _run_async(find_service_errors_and_traces(service_id, from_timestamp, to_timestamp, max_results))

    sync_wrapper.__doc__ = find_service_errors_and_traces.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=find_service_errors_and_traces,
        name="find_service_errors_and_traces",
        description=find_service_errors_and_traces.__doc__ or "Find error traces for a specific service",
    )
    return tool


def create_get_service_metrics_tool(secret_retriever: ISecretRetriever):
    """Factory function to create service metrics tool with injected secret retriever."""

    async def get_service_metrics(
        service_id: str,
        metrics: Optional[List[str]] = None,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query key metrics for a Dynatrace service.

        This function queries Dynatrace metrics for a specific service including response time,
        error rate, throughput, and other performance indicators. It uses the Dynatrace Metrics
        API v2 to retrieve time-series data for analysis and monitoring.

        When to use:
        - Monitor service performance and health
        - Detect anomalies in response time or throughput
        - Analyze error rates and failure patterns
        - Track service SLOs and SLIs
        - Compare metrics across time periods
        - Investigate performance degradation

        Args:
            service_id: Dynatrace service entity ID to query metrics for.
            metrics: Optional list of metric selectors to query.
            from_timestamp: Start time in ISO 8601 format or relative time.
            to_timestamp: End time in ISO 8601 format or relative time.
            resolution: Optional resolution for data points.

        Returns:
            Dict[str, Any]: Dictionary containing metric data.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
            - Uses Dynatrace Metrics API v2
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            if not from_timestamp:
                from_timestamp = "now-1h"
            if not to_timestamp:
                to_timestamp = "now"

            if not metrics:
                metrics = [
                    "builtin:service.response.time",
                    "builtin:service.errors.server.rate",
                    "builtin:service.requestCount.server",
                ]

            metrics_data = {}
            for metric_selector in metrics:
                try:
                    result = dt_client.metrics.query(
                        metric_selector=metric_selector,
                        entity_selector=f'entityId("{service_id}")',
                        time_from=from_timestamp,
                        time_to=to_timestamp,
                        resolution=resolution,
                    )

                    if result and len(result.result) > 0:
                        data_points = result.result[0].data
                        if data_points:
                            values = [dp.values[0] for dp in data_points if dp.values]
                            metrics_data[metric_selector] = {
                                "average": sum(values) / len(values) if values else 0,
                                "max": max(values) if values else 0,
                                "min": min(values) if values else 0,
                                "data_points": len(values),
                                "unit": result.result[0].unit if hasattr(result.result[0], "unit") else "unknown",
                            }
                except Exception as e:
                    metrics_data[metric_selector] = {"error": str(e)}

            return {
                "service_id": service_id,
                "metrics": metrics_data,
                "time_range": {"from": from_timestamp, "to": to_timestamp},
                "resolution": resolution,
                "status": "success",
            }

        except Exception as e:
            return {"error": f"Failed to retrieve metrics: {str(e)}", "error_type": type(e).__name__}

    def sync_wrapper(
        service_id: str,
        metrics: Optional[List[str]] = None,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _run_async(get_service_metrics(service_id, metrics, from_timestamp, to_timestamp, resolution))

    sync_wrapper.__doc__ = get_service_metrics.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_service_metrics,
        name="get_service_metrics",
        description=get_service_metrics.__doc__ or "Query key metrics for a Dynatrace service",
    )
    return tool


def create_get_active_problems_tool(secret_retriever: ISecretRetriever):
    """Factory function to create active problems tool with injected secret retriever."""

    async def get_active_problems(
        impact_level: Optional[str] = None, severity_level: Optional[str] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        """List currently open problems in Dynatrace.

        Retrieves problems that have been detected and analyzed by Dynatrace's automated monitoring.
        Problems represent detected anomalies, performance issues, and failures in your environment.

        When to use:
        - Triage and prioritize ongoing incidents
        - Get overview of system health issues
        - Identify high-impact problems requiring immediate attention

        Args:
            impact_level: Optional filter by impact level.
            severity_level: Optional filter by severity level.
            max_results: Maximum number of problems to retrieve.

        Returns:
            Dict[str, Any]: Dictionary containing active problems.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            kwargs = {"problem_selector": "status(OPEN)", "sort": "-startTime"}

            if impact_level:
                kwargs["problem_selector"] += f",impactLevel({impact_level})"

            if severity_level:
                kwargs["problem_selector"] += f",severityLevel({severity_level})"

            problems = dt_client.problems.list(**kwargs)

            problems_data = []
            for problem in list(problems)[:max_results]:
                problems_data.append(
                    {
                        "problem_id": problem.problem_id,
                        "title": problem.title,
                        "impact_level": problem.impact_level,
                        "severity_level": problem.severity_level,
                        "status": problem.status,
                        "affected_entities": (
                            [{"id": e.entity_id, "name": e.name} for e in problem.affected_entities]
                            if hasattr(problem, "affected_entities")
                            else []
                        ),
                        "start_time": problem.start_time if hasattr(problem, "start_time") else None,
                        "display_id": problem.display_id if hasattr(problem, "display_id") else None,
                    }
                )

            return {
                "problems": problems_data,
                "total_problems": len(problems_data),
                "filters": {"impact_level": impact_level, "severity_level": severity_level},
                "status": "success",
            }

        except Exception as e:
            return {"error": f"Failed to retrieve active problems: {str(e)}", "error_type": type(e).__name__}

    def sync_wrapper(
        impact_level: Optional[str] = None, severity_level: Optional[str] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        return _run_async(get_active_problems(impact_level, severity_level, max_results))

    sync_wrapper.__doc__ = get_active_problems.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_active_problems,
        name="get_active_problems",
        description=get_active_problems.__doc__ or "List currently open problems detected by Dynatrace Davis AI",
    )
    return tool


def create_get_problem_details_tool(secret_retriever: ISecretRetriever):
    """Factory function to create problem details tool with injected secret retriever."""

    async def get_problem_details(problem_id: str) -> Dict[str, Any]:
        """Retrieve detailed information about a specific Dynatrace problem.

        Gets comprehensive details about a problem including affected entities, root cause information,
        and supporting evidence that has been analyzed by Dynatrace's automated monitoring.

        When to use:
        - Investigate specific problems in detail
        - Understand root cause of incidents
        - Review automated analysis and evidence

        Args:
            problem_id: The Dynatrace problem ID to retrieve details for.

        Returns:
            Dict[str, Any]: Dictionary containing detailed problem information.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)
            problem = dt_client.problems.get(problem_id=problem_id)

            problem_data = {
                "problem_id": problem.problem_id,
                "display_id": problem.display_id if hasattr(problem, "display_id") else None,
                "title": problem.title,
                "impact_level": problem.impact_level,
                "severity_level": problem.severity_level,
                "status": problem.status,
                "start_time": problem.start_time if hasattr(problem, "start_time") else None,
                "end_time": problem.end_time if hasattr(problem, "end_time") else None,
                "affected_entities": (
                    [
                        {
                            "id": e.entity_id,
                            "name": e.name,
                            "type": e.entity_type if hasattr(e, "entity_type") else None,
                        }
                        for e in problem.affected_entities
                    ]
                    if hasattr(problem, "affected_entities")
                    else []
                ),
                "root_cause": None,
                "evidence": [],
                "status": "success",
            }

            if hasattr(problem, "root_cause_entity") and problem.root_cause_entity:
                problem_data["root_cause"] = {
                    "entity_id": problem.root_cause_entity.entity_id,
                    "entity_name": (
                        problem.root_cause_entity.name if hasattr(problem.root_cause_entity, "name") else None
                    ),
                }

            if hasattr(problem, "evidence_details") and problem.evidence_details:
                evidence_list = problem.evidence_details.details if hasattr(problem.evidence_details, "details") else []
                problem_data["evidence"] = [
                    {
                        "title": evidence.display_name if hasattr(evidence, "display_name") else None,
                        "entity": evidence.entity if hasattr(evidence, "entity") else None,
                        "grouping_entity": evidence.grouping_entity if hasattr(evidence, "grouping_entity") else None,
                    }
                    for evidence in evidence_list
                ]

            return problem_data

        except Exception as e:
            return {
                "error": f"Failed to retrieve problem details: {str(e)}",
                "error_type": type(e).__name__,
                "problem_id": problem_id,
            }

    def sync_wrapper(problem_id: str) -> Dict[str, Any]:
        return _run_async(get_problem_details(problem_id))

    sync_wrapper.__doc__ = get_problem_details.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_problem_details,
        name="get_problem_details",
        description=get_problem_details.__doc__ or "Retrieve detailed information about a specific Dynatrace problem",
    )
    return tool


def create_get_entity_info_tool(secret_retriever: ISecretRetriever):
    """Factory function to create entity info tool with injected secret retriever."""

    async def get_entity_info(
        entity_id: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch metadata and tags for any Dynatrace entity.

        When to use:
        - Get detailed information about specific entities
        - Retrieve entity tags and metadata
        - Enrich incident responses with entity context

        Args:
            entity_id: The Dynatrace entity ID to retrieve information for.
            from_timestamp: Optional start time.
            to_timestamp: Optional end time.

        Returns:
            Dict[str, Any]: Dictionary containing entity information.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            if not from_timestamp:
                from_timestamp = "now-2h"
            if not to_timestamp:
                to_timestamp = "now"

            entity = dt_client.entities.get(entity_id=entity_id)

            entity_data = {
                "entity_id": entity.entity_id,
                "display_name": entity.display_name,
                "entity_type": entity.type if hasattr(entity, "type") else None,
                "first_seen": entity.first_seen_tms if hasattr(entity, "first_seen_tms") else None,
                "last_seen": entity.last_seen_tms if hasattr(entity, "last_seen_tms") else None,
                "tags": (
                    [
                        {
                            "key": tag.key,
                            "value": tag.value if hasattr(tag, "value") else None,
                            "context": tag.context if hasattr(tag, "context") else None,
                        }
                        for tag in entity.tags
                    ]
                    if hasattr(entity, "tags")
                    else []
                ),
                "properties": entity.properties if hasattr(entity, "properties") else {},
                "management_zones": (
                    [{"id": mz.id, "name": mz.name} for mz in entity.management_zones]
                    if hasattr(entity, "management_zones")
                    else []
                ),
                "status": "success",
            }

            return entity_data

        except Exception as e:
            return {
                "error": f"Failed to retrieve entity information: {str(e)}",
                "error_type": type(e).__name__,
                "entity_id": entity_id,
            }

    def sync_wrapper(
        entity_id: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        return _run_async(get_entity_info(entity_id, from_timestamp, to_timestamp))

    sync_wrapper.__doc__ = get_entity_info.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_entity_info,
        name="get_entity_info",
        description=get_entity_info.__doc__ or "Fetch metadata and tags for any Dynatrace entity",
    )
    return tool


def create_search_logs_tool(secret_retriever: ISecretRetriever):
    """Factory function to create search logs tool with injected secret retriever."""

    async def search_logs(
        query: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None, max_results: int = 100
    ) -> Dict[str, Any]:
        """Query logs using Dynatrace Query Language (DQL).

        When to use:
        - Search for specific log entries or patterns
        - Debug application errors and exceptions
        - Correlate logs with problems and metrics

        Args:
            query: DQL query string to search logs.
                   CRITICAL DQL SYNTAX RULES:
                   - Use single = for equality (NOT ==)
                   - Use 'contains' for substring matching (NOT LIKE)
                   - Use AND, OR, NOT for boolean operations
                   - String values must be in double quotes
                   - Field names: service.name, log.level, content, dt.entity.service
                   
                   QUERY COMPLEXITY LIMIT:
                   - Maximum 20 relations per query (Dynatrace enforced)
                   - Keep queries simple - avoid many OR conditions
                   - If you need to search multiple keywords, make separate queries
                   - Better: 3 simple queries than 1 complex query with many ORs
                   
                   Valid examples:
                   - 'service.name = "user-management" AND content contains "error"'
                   - 'log.level = "ERROR" AND content contains "authentication"'
                   - 'dt.entity.service = "SERVICE-123" AND content contains "fail"'
                   - 'content contains "login" AND NOT content contains "success"'
                   
                   INVALID (will cause 400 error):
                   - 'service.name == "user-management"'  (use = not ==)
                   - 'service.name = user-management'  (missing quotes)
                   - '(error OR fail)'  (operators need field names)
                   - Too many ORs: 'content contains "a" OR content contains "b" OR content contains "c" OR ...'  (exceeds 20 relations)
            from_timestamp: Start time in ISO 8601 format or relative time.
            to_timestamp: End time in ISO 8601 format or relative time.
            max_results: Maximum number of log entries to return (default 100).

        Returns:
            Dict[str, Any]: Dictionary containing log search results.
                           {
                               "logs": [{"timestamp": ..., "content": ..., "severity": ...}],
                               "total_results": 10,
                               "query": "service.name = ...",
                               "time_range": {"from": ..., "to": ...},
                               "status": "success"
                           }

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
            - DQL is case-sensitive for field names
            - Use 'contains' operator for substring search, not LIKE
            - Equality uses single = not ==
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            if not from_timestamp:
                from_timestamp = "now-1h"
            if not to_timestamp:
                to_timestamp = "now"

            # Note: limit is not needed in query as export method handles pagination
            # and we'll limit results after fetching
            
            # Use the logs export method (handles pagination automatically)
            result = dt_client.logs.export(query=query, time_from=from_timestamp, time_to=to_timestamp)

            logs_data = []
            count = 0
            # result is a PaginatedList, iterate through it
            for record in result:
                if count >= max_results:
                    break
                logs_data.append(
                    {
                        "timestamp": record.timestamp if hasattr(record, "timestamp") else None,
                        "severity": record.severity if hasattr(record, "severity") else None,
                        "content": record.content if hasattr(record, "content") else None,
                        "attributes": record.attributes if hasattr(record, "attributes") else {},
                    }
                )
                count += 1

            return {
                "logs": logs_data,
                "total_results": len(logs_data),
                "query": query,
                "time_range": {"from": from_timestamp, "to": to_timestamp},
                "status": "success",
            }

        except Exception as e:
            return {"error": f"Failed to search logs: {str(e)}", "error_type": type(e).__name__, "query": query}

    def sync_wrapper(
        query: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None, max_results: int = 100
    ) -> Dict[str, Any]:
        return _run_async(search_logs(query, from_timestamp, to_timestamp, max_results))

    sync_wrapper.__doc__ = search_logs.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=search_logs,
        name="search_logs",
        description=search_logs.__doc__ or "Query logs using Dynatrace Query Language (DQL)",
    )
    return tool


def create_push_deployment_event_tool(secret_retriever: ISecretRetriever):
    """Factory function to create push deployment event tool with injected secret retriever."""

    async def push_deployment_event(
        entity_id: str,
        event_type: str,
        title: str,
        description: Optional[str] = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Ingest deployment or custom events into Dynatrace.

        When to use:
        - Mark deployment events for correlation with problems
        - Track configuration changes and their impacts
        - Annotate timelines with important business events

        Args:
            entity_id: The Dynatrace entity ID to attach the event to.
            event_type: Type of event to create.
            title: Short title for the event.
            description: Optional detailed description.
            properties: Optional custom properties.

        Returns:
            Dict[str, Any]: Dictionary containing event creation result.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            event_data = {
                "eventType": event_type,
                "title": title,
                "entitySelector": f'entityId("{entity_id}")',
            }

            if description:
                event_data["description"] = description

            if properties:
                event_data["properties"] = properties

            result = dt_client.events.ingest(event_data)

            return {
                "entity_id": entity_id,
                "event_type": event_type,
                "title": title,
                "result": result if result else "Event created",
                "status": "success",
            }

        except Exception as e:
            return {
                "error": f"Failed to push event: {str(e)}",
                "error_type": type(e).__name__,
                "entity_id": entity_id,
            }

    def sync_wrapper(
        entity_id: str,
        event_type: str,
        title: str,
        description: Optional[str] = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return _run_async(push_deployment_event(entity_id, event_type, title, description, properties))

    sync_wrapper.__doc__ = push_deployment_event.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=push_deployment_event,
        name="push_deployment_event",
        description=push_deployment_event.__doc__ or "Ingest deployment or custom events into Dynatrace",
    )
    return tool


def create_get_synthetic_test_results_tool(secret_retriever: ISecretRetriever):
    """Factory function to create synthetic test results tool with injected secret retriever."""

    async def get_synthetic_test_results(
        monitor_id: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve results of Dynatrace synthetic monitoring tests.

        When to use:
        - Monitor application availability from user perspective
        - Track synthetic test success rates
        - Detect availability issues before users are impacted

        Args:
            monitor_id: The Dynatrace synthetic monitor ID.
            from_timestamp: Start time.
            to_timestamp: End time.

        Returns:
            Dict[str, Any]: Dictionary containing synthetic test results.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            if not from_timestamp:
                from_timestamp = "now-24h"
            if not to_timestamp:
                to_timestamp = "now"

            results = dt_client.synthetic_monitors.get_results(
                monitor_id=monitor_id, time_from=from_timestamp, time_to=to_timestamp
            )

            results_data = []
            success_count = 0
            total_count = 0

            if hasattr(results, "executions") and results.executions:
                for execution in results.executions:
                    total_count += 1
                    is_success = execution.success if hasattr(execution, "success") else False
                    if is_success:
                        success_count += 1

                    results_data.append(
                        {
                            "timestamp": execution.timestamp if hasattr(execution, "timestamp") else None,
                            "success": is_success,
                            "response_time": execution.response_time if hasattr(execution, "response_time") else None,
                            "location": execution.location_id if hasattr(execution, "location_id") else None,
                            "error": execution.error if hasattr(execution, "error") else None,
                        }
                    )

            availability = (success_count / total_count * 100) if total_count > 0 else 0

            return {
                "monitor_id": monitor_id,
                "results": results_data,
                "total_executions": total_count,
                "successful_executions": success_count,
                "availability": round(availability, 2),
                "time_range": {"from": from_timestamp, "to": to_timestamp},
                "status": "success",
            }

        except Exception as e:
            return {
                "error": f"Failed to retrieve synthetic test results: {str(e)}",
                "error_type": type(e).__name__,
                "monitor_id": monitor_id,
            }

    def sync_wrapper(
        monitor_id: str, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        return _run_async(get_synthetic_test_results(monitor_id, from_timestamp, to_timestamp))

    sync_wrapper.__doc__ = get_synthetic_test_results.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_synthetic_test_results,
        name="get_synthetic_test_results",
        description=get_synthetic_test_results.__doc__ or "Retrieve results of Dynatrace synthetic monitoring tests",
    )
    return tool


def create_get_security_issues_tool(secret_retriever: ISecretRetriever):
    """Factory function to create security issues tool with injected secret retriever."""

    async def get_security_issues(
        severity: Optional[str] = None, status: Optional[str] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        """List active security problems detected by Dynatrace.

        When to use:
        - Identify active security vulnerabilities
        - Prioritize security remediation efforts
        - Track security problem trends

        Args:
            severity: Optional filter by severity level.
            status: Optional filter by status.
            max_results: Maximum number of security issues to retrieve.

        Returns:
            Dict[str, Any]: Dictionary containing security issues.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            security_problem_selector = []
            if status:
                security_problem_selector.append(f"status({status})")
            if severity:
                security_problem_selector.append(f"riskLevel({severity})")

            selector = ",".join(security_problem_selector) if security_problem_selector else None

            security_problems = dt_client.security_problems.list(security_problem_selector=selector)

            issues_data = []
            for issue in list(security_problems)[:max_results]:
                issues_data.append(
                    {
                        "id": issue.security_problem_id if hasattr(issue, "security_problem_id") else None,
                        "title": issue.title if hasattr(issue, "title") else None,
                        "severity": issue.risk_level if hasattr(issue, "risk_level") else None,
                        "status": issue.status if hasattr(issue, "status") else None,
                        "affected_entities": (
                            [{"id": e.entity_id, "name": e.name} for e in issue.affected_entities]
                            if hasattr(issue, "affected_entities")
                            else []
                        ),
                        "cve_ids": issue.cve_ids if hasattr(issue, "cve_ids") else [],
                        "technology": issue.technology if hasattr(issue, "technology") else None,
                    }
                )

            return {
                "security_issues": issues_data,
                "total_issues": len(issues_data),
                "filters": {"severity": severity, "status": status},
                "status": "success",
            }

        except Exception as e:
            return {"error": f"Failed to retrieve security issues: {str(e)}", "error_type": type(e).__name__}

    def sync_wrapper(
        severity: Optional[str] = None, status: Optional[str] = None, max_results: int = 50
    ) -> Dict[str, Any]:
        return _run_async(get_security_issues(severity, status, max_results))

    sync_wrapper.__doc__ = get_security_issues.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_security_issues,
        name="get_security_issues",
        description=get_security_issues.__doc__ or "List active security problems detected by Dynatrace",
    )
    return tool


def create_get_alerting_profiles_tool(secret_retriever: ISecretRetriever):
    """Factory function to create alerting profiles tool with injected secret retriever."""

    async def get_alerting_profiles() -> Dict[str, Any]:
        """List and describe Dynatrace alerting profiles.

        When to use:
        - Review current alerting configuration
        - Understand alert routing and notification rules
        - Audit alerting profile setup

        Returns:
            Dict[str, Any]: Dictionary containing alerting profiles.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            profiles = dt_client.alerting_profiles.list()

            profiles_data = []
            for profile in profiles:
                profiles_data.append(
                    {
                        "id": profile.id if hasattr(profile, "id") else None,
                        "name": profile.name if hasattr(profile, "name") else None,
                        "management_zone_id": (
                            profile.management_zone_id if hasattr(profile, "management_zone_id") else None
                        ),
                        "rules": profile.rules if hasattr(profile, "rules") else [],
                    }
                )

            return {"alerting_profiles": profiles_data, "total_profiles": len(profiles_data), "status": "success"}

        except Exception as e:
            return {"error": f"Failed to retrieve alerting profiles: {str(e)}", "error_type": type(e).__name__}

    def sync_wrapper() -> Dict[str, Any]:
        return _run_async(get_alerting_profiles())

    sync_wrapper.__doc__ = get_alerting_profiles.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_alerting_profiles,
        name="get_alerting_profiles",
        description=get_alerting_profiles.__doc__ or "List and describe Dynatrace alerting profiles",
    )
    return tool


def create_get_topology_map_tool(secret_retriever: ISecretRetriever):
    """Factory function to create topology map tool with injected secret retriever."""

    async def get_topology_map(
        entity_type: Optional[str] = None, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve Smartscape topology relationships from Dynatrace.

        When to use:
        - Visualize system architecture and dependencies
        - Understand service relationships and communication patterns
        - Investigate cascading failures

        Args:
            entity_type: Optional filter by entity type.
            from_timestamp: Optional start time.
            to_timestamp: Optional end time.

        Returns:
            Dict[str, Any]: Dictionary containing topology information.

        Note:
            - Requires DYNATRACE_BASE_URL and DYNATRACE_API_TOKEN secrets
        """

        base_url = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_BASE_URL")

        api_token = await secret_retriever.retrieve_mandatory_secret_value("DYNATRACE_API_TOKEN")

        try:
            dt_client = Dynatrace(base_url, api_token)

            if not from_timestamp:
                from_timestamp = "now-2h"
            if not to_timestamp:
                to_timestamp = "now"

            if entity_type:
                entity_selector = f"type({entity_type})"
            else:
                entity_selector = "type(SERVICE),type(PROCESS_GROUP),type(HOST),type(APPLICATION)"

            entities = dt_client.entities.list(
                entity_selector=entity_selector, time_from=from_timestamp, time_to=to_timestamp
            )

            topology_data = []
            for entity in entities:
                entity_info = {
                    "id": entity.entity_id,
                    "name": entity.display_name,
                    "type": entity.type if hasattr(entity, "type") else None,
                    "relationships": [],
                }

                if hasattr(entity, "from_relationships") and entity.from_relationships:
                    for rel in entity.from_relationships:
                        entity_info["relationships"].append(
                            {
                                "type": rel.type if hasattr(rel, "type") else "unknown",
                                "target_id": rel.id if hasattr(rel, "id") else None,
                            }
                        )

                topology_data.append(entity_info)

            return {
                "entities": topology_data,
                "total_entities": len(topology_data),
                "entity_type_filter": entity_type,
                "time_range": {"from": from_timestamp, "to": to_timestamp},
                "status": "success",
            }

        except Exception as e:
            return {"error": f"Failed to retrieve topology map: {str(e)}", "error_type": type(e).__name__}

    def sync_wrapper(
        entity_type: Optional[str] = None, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        return _run_async(get_topology_map(entity_type, from_timestamp, to_timestamp))

    sync_wrapper.__doc__ = get_topology_map.__doc__

    tool = StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=get_topology_map,
        name="get_topology_map",
        description=get_topology_map.__doc__ or "Retrieve Smartscape topology relationships from Dynatrace",
    )
    return tool
