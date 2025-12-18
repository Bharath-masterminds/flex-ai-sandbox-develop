# Copilot Instructions for FLEX AI Sandbox

This document provides guidelines for GitHub Copilot when assisting with code in this repository.

## Project Overview

This is **fx-ai-reusables** - a Python library for reusable AI/ML components built on Azure OpenAI, LangChain, and enterprise AI workflows. The project follows a clean architecture pattern with interface-based design and dependency injection.

### Repository Structure

```
fx_ai_reusables/          # Reusable components for ANY AI use case
use_cases/                # Specific AI use-case implementations
```

**Critical Rule**: Code in `fx_ai_reusables/` must be generic and reusable. Use-case-specific code goes in `use_cases/`.

## Architecture & Design Patterns

### 1. Interface-Based Design

All major components follow the interface pattern:
- Place interfaces in `interfaces/` subdirectories
- Implement concrete classes in `concretes/` subdirectories
- Use ABC (Abstract Base Class) with `@abstractmethod` decorators
- Prefix interface names with `I` (e.g., `IHcpAuthenticator`, `ILlmCreator`)

**Example Structure**:
```
module_name/
├── interfaces/
│   └── component_interface.py    # IComponent(ABC)
└── concretes/
    └── component_concrete.py      # ConcreteComponent(IComponent)
```

### 2. Dependency Injection (IoC)

- Use `dependency-injector` library for IoC containers
- Create composition roots in `use_cases/<use_case>/ioc/` directories
- Use providers for dependency wiring (Factory, Singleton, etc.)
- Always inject interfaces, not concrete implementations
- Configuration management via `IocConfig` base class

**Example Pattern**:
```python
from dependency_injector import containers, providers
from fx_ai_reusables.ioc.configuration.ioc_configuration import IocConfig

class MyCompositionRoot(containers.DeclarativeContainer):
    config = providers.Singleton(IocConfig)
    
    # Inject interfaces
    authenticator = providers.Factory(
        HcpAuthenticator,
        azure_llm_configmap_and_secrets_holder_wrapper_retriever=...
    )
```

### 3. Async-First Design

- Prefer async/await patterns for I/O operations
- Use `async def` for methods that interact with APIs, databases, or LLMs
- Suffix async interfaces with `Async` when sync versions exist (e.g., `IEnvironmentFetcherAsync`)
- Use `asyncio.run()` or `await` appropriately based on context

### 4. Factory Pattern

- Use factory classes for creating complex objects (LLMs, vector stores, etc.)
- Factories implement `ICreator` interfaces
- Examples: `AzureChatOpenAILlmCreator`, `AzureAISearchVectorStoreCreator`

## Code Style & Conventions

### Python Standards

- **Python Version**: 3.12+
- **Line Length**: 120 characters (Black formatter)
- **Import Style**: Use explicit imports from interfaces and concretes
  ```python
  from fx_ai_reusables.llm.creators import AzureChatOpenAILlmCreator
  from fx_ai_reusables.llm.creators.interfaces import ILlmCreator
  ```
- **Type Hints**: Always use type hints for function parameters and return values
- **Docstrings**: Use descriptive docstrings for public methods, especially for tools

### Naming Conventions

- **Classes**: PascalCase (e.g., `HcpAuthenticator`, `AzureChatOpenAILlmCreator`)
- **Functions/Methods**: snake_case (e.g., `get_hcp_token`, `create_llm`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_AUTH_TIMEOUT`, `AZURE_OPENAI_ENDPOINT`)
- **Private Members**: Prefix with underscore (e.g., `_cache`)
- **Interfaces**: Prefix with `I` (e.g., `IAgent`, `ISecretRetriever`)

### Module Organization

Each module typically contains:
```
module_name/
├── __init__.py           # Public exports
├── constants.py          # Module-specific constants
├── interfaces/           # Abstract interfaces
├── concretes/            # Concrete implementations
├── samples/              # Usage examples and sample implementations
└── README.md            # Module documentation (when needed)
```

## Key Components & Usage Patterns

### Authentication (authenticators/)

- **HCP Authentication**: Use `HcpAuthenticator` for Healthcare Cloud Platform tokens
- **Pattern**: Token caching with cache-aside decorators
- **Timeout**: Default 30-second timeout for auth requests (`DEFAULT_AUTH_TIMEOUT`)

```python
from fx_ai_reusables.authenticators.hcp.concretes import HcpAuthenticator

hcp_authenticator = HcpAuthenticator(environment_reader)
token = await hcp_authenticator.get_hcp_token()
```

### LLM Integration (llm/)

- **Factory**: `AzureChatOpenAILlmCreator` for Azure OpenAI models
- **Caching**: Use `LlmCreatorCacheAsideDecorator` for LLM instance caching
- **Tools Binding**: Support for LangChain tools via `tools` parameter
- **Structured Output**: Enable via `with_structured_output=True`

```python
llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
llm = await llm_creator.create_llm(tools=my_tools, tool_choice="any")
```

### Configuration & Secrets (configmaps/, secrets/, environment_loading/)

- **Config**: `IConfigMapRetriever` for configuration values
- **Secrets**: `ISecretRetriever` for sensitive data
- **Combined**: `AzureLlmConfigAndSecretsHolderWrapperReader` combines both
- **Environment**: Use `EnvironmentVariablesConfigMapRetriever` and `EnvironmentVariableSecretRetriever` for env-based config

### Agents & Tools (agents/, tools/)

- **Base Interface**: All agents implement `IAgent`
- **LangChain Tools**: Use `@tool` decorator with parse_docstring=True
- **Tool Documentation**: Comprehensive docstrings guide LLM tool selection
- **Agent Types**: ServiceNow, Splunk, DataDog, App Insights agents available

**Tool Pattern**:
```python
from langchain_core.tools import tool

@tool("tool_name", parse_docstring=True)
def my_tool(param: str) -> Dict[str, Any]:
    """Clear description of what the tool does.
    
    Args:
        param: Parameter description
        
    Returns:
        Description of return value
    """
    # Implementation
```

### Vector Stores (vectorizers/)

- **Factory Pattern**: Create vector stores via factory classes
- **Data Layer**: Abstract data access patterns
- **Supported**: Azure AI Search, other vector databases
- **Helpers**: Embedding and similarity utilities

### Document Processing (chunkers/, file_parsers/)

- **Chunkers**: Implement `IChunker` interface
- **Strategies**: By source folder, by file type, custom
- **File Parsers**: JSON, XML, XSD parsing utilities
- **Source Code**: Specialized chunking for code repositories

## Testing

- **Framework**: pytest with asyncio support
- **Location**: `fx_ai_reusables/tests/unit/`
- **Pattern**: Use fixtures for mock objects and test setup
- **Async Tests**: Mark with `@pytest.mark.asyncio`

```python
class TestMyComponent:
    @pytest.fixture
    def mock_dependency(self):
        return MagicMock()
    
    @pytest.mark.asyncio
    async def test_async_method(self, mock_dependency):
        # Test implementation
        assert await component.method() == expected
```

## Branching & Development Strategy

### Branch Naming

- **New Features**: `feature/<ticket>-<short-description>`
  - Example: `feature/US0000-add-datadog-agent`
- **Experiments**: Create subfolder in `use_cases/` - DO NOT merge to main

### Folder Organization Rules

1. **Reusables** (`fx_ai_reusables/`): For ANY/ALL use cases
   - Generic utilities (XML parsing, JSON loading, etc.)
   - Never put use-case-specific logic here
   
2. **Use Cases** (`use_cases/`): Specific AI implementations
   - Create subfolder with descriptive name
   - Use versioning if multiple attempts: `_version_one`, `_version_two`
   - For related use cases, create family structure:
     ```
     use_cases/
     └── liquid_templates/
         ├── fhir_liquid_template_version_one/
         ├── hl7v2_liquid_template_version_one/
         └── use_case_family_reusable/
     ```

### Pull Request Guidelines

- **Do Not Merge**: Label experimental PRs with "do not merge"
- **Description**: Explain what the code does and why
- **Utility Helpers**: Can be merged to main if generic enough
- **Use-Case Code**: Keep in branches, do not merge to main

## Environment Variables

Key environment variables (see `.env.example`):
- `DEPLOYMENT_FLAVOR`: Environment type (DEVELOPMENTLOCAL, PRODUCTION, etc.)
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI service endpoint
- `AZURE_OPENAI_API_VERSION`: API version
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment name
- `HCP_TOKEN_URL`: HCP authentication endpoint
- `HCP_CLIENT_ID`, `HCP_CLIENT_SECRET`: HCP credentials

## Common Patterns to Follow

### 1. Error Handling

- Use try/except for API calls and I/O operations
- Provide meaningful error messages
- Log errors appropriately
- Consider retry logic with `tenacity` library

### 2. Configuration Loading

Always use the environment loading pattern:
```python
config_map_retriever = EnvironmentVariablesConfigMapRetriever()
secrets_retriever = EnvironmentVariableSecretRetriever()
environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(
    config_map_retriever, 
    secrets_retriever
)
```

### 3. Sample Code

- Provide sample implementations in `samples/` directories
- Samples should be runnable examples
- Document prerequisites and setup steps
- Use samples for testing patterns and documentation

### 4. Imports Organization

Order imports as:
1. Standard library imports
2. Third-party library imports (langchain, pydantic, azure, etc.)
3. Local application imports (fx_ai_reusables)

```python
import asyncio
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel

from fx_ai_reusables.authenticators.hcp.concretes import HcpAuthenticator
```

## Streamlit Applications

When building Streamlit apps in use cases:
- Use `@st.cache_resource` for IoC containers
- Load environment variables BEFORE importing IoC components
- Set PYTHONPATH: `export PYTHONPATH=$(pwd)`
- Run as module: `streamlit run use_cases/<use_case>/app.py`

## Documentation

- **Module Level**: Docstrings in `__init__.py`
- **Class Level**: Describe purpose and usage
- **Method Level**: Args, Returns, Raises sections
- **README files**: For complex modules and use cases
- **Type Hints**: Required for all public APIs

## Security & Credentials

- **Never commit secrets**: Use environment variables
- **Token Management**: Cache tokens, respect TTLs
- **API Keys**: Always use `SecretStr` from Pydantic for sensitive strings
- **HTTPS Only**: All API communications use TLS
- **Certificate Verification**: Use `certifi` for SSL verification

## LangChain & LangGraph

- **Agents**: Use LangGraph for multi-agent workflows
- **Tools**: LangChain tools with `@tool` decorator
- **Supervisors**: Implement supervisor patterns in `supervisors/`
- **Message Types**: Use LangChain message types (AIMessage, HumanMessage, etc.)
- **Tracing**: Phoenix tracing for observability (`phoenix_setup.py`)

## Monitoring & Observability

- **Phoenix**: Arize Phoenix for LLM tracing
- **Reporters**: LLM usage tracking via reporters module
- **Logging**: Use structured logging patterns
- **Metrics**: Capture API calls, token usage, latencies

## Dependencies

Key libraries to be aware of:
- **langchain**: LangChain framework (0.3.14+)
- **langgraph**: Multi-agent orchestration (0.6.6)
- **pydantic**: Data validation (2.10.4+)
- **azure-identity**: Azure authentication
- **dependency-injector**: IoC container (~4.48.2)
- **streamlit**: UI for use cases
- **pytest**: Testing framework

## Code Owners

For questions or reviews, contact:
- @cconno13_uhg
- @shollid3_uhg
- @tdarmorh_uhg

## Best Practices Summary

1. ✅ Use interface-based design with ABC
2. ✅ Inject dependencies via IoC containers
3. ✅ Write async code for I/O operations
4. ✅ Add comprehensive type hints
5. ✅ Follow 120-character line length
6. ✅ Keep reusables generic, use cases specific
7. ✅ Write docstrings for public APIs
8. ✅ Use samples for examples
9. ✅ Test with pytest and async fixtures
10. ✅ Never commit secrets or credentials

## Anti-Patterns to Avoid

1. ❌ Don't put use-case logic in `fx_ai_reusables/`
2. ❌ Don't instantiate concrete classes directly - use DI
3. ❌ Don't mix sync and async code improperly
4. ❌ Don't hardcode configuration values
5. ❌ Don't skip type hints on public APIs
6. ❌ Don't create god classes - use composition
7. ❌ Don't merge experimental code to main
8. ❌ Don't skip interface creation for new components

---

**When in doubt**: Look at existing implementations in `samples/` directories for reference patterns.
