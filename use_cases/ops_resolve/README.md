# OpsResolve - Incident Analysis System

A supervisor-orchestrated, agent-based system that analyzes production incidents by querying ServiceNow, Splunk, and Azure Application Insights to generate evidence-backed hypotheses.

## Architecture

The system follows a hierarchical architecture:

```
Supervisor (OpsResolve) 
├── ServiceNow Agent
│   ├── get_servicenow_incident
│   ├── update_servicenow_incident
│   └── find_similar_servicenow_incidents
├── Splunk Agent
│   ├── search_splunk_logs
│   ├── get_splunk_job_status
│   ├── get_splunk_results
│   └── cancel_splunk_job
└── App Insights Agent
    ├── get_app_insights_operation_id_using_url
    ├── get_app_insights_exceptions
    ├── get_app_insights_metrics
    └── get_app_insights_dependencies
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables and authentication:
   - See [AUTHENTICATION_SETUP.md](./AUTHENTICATION_SETUP.md) for detailed authentication configuration
   - See [README_IOC.md](./README_IOC.md) for IoC container configuration
   - Create a `.env` file with required secrets (Azure AD, HCP, LLM configs)

3. Run the system:

**Streamlit Web UI (with Authentication)**:
```bash
export PYTHONPATH=$(pwd)
streamlit run use_cases/ops_resolve/streamlit_app.py
```

**Command Line** (headless, no authentication):
```bash
python -m use_cases.ops_resolve.main INC0000123
```

## Components

### Tools (`reusables/tools/`)
- **ServiceNow Tools**: Incident management operations
- **Splunk Tools**: Log search and analysis
- **App Insights Tools**: Metrics and trace analysis

### Agents (`reusables/agents/`)
- **ServiceNowAgent**: Manages ServiceNow operations
- **SplunkAgent**: Handles Splunk queries and job management
- **AppInsightsAgent**: Processes Azure Application Insights data

### Supervisor (`use_cases/ops_resolve/supervisor/`)
- **OpsResolveSupervisor**: Orchestrates the incident analysis workflow using LangGraph

### Factory (`use_cases/ops_resolve/factories/`)
- **AgentFactory**: Creates and configures agents dynamically

## Usage

The system can be run with an incident ID:

```bash
python -m use_cases.ops_resolve.main INC0000123
```

The supervisor will:
1. Gather incident details from ServiceNow
2. Search for relevant logs in Splunk
3. Retrieve metrics and traces from App Insights
4. Correlate signals across data sources
5. Generate evidence-backed hypotheses
6. Update ServiceNow with structured findings

## Current Status

This is the initial implementation with placeholder business logic. The architecture and interfaces are complete, ready for actual API integrations.
