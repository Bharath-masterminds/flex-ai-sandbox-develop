# FLEX AI Reusables

A comprehensive Python library providing reusable AI/ML components for Azure OpenAI, LangChain, and enterprise AI workflows.

## 🚀 Quick Start

### Installation

```bash
pip install fx-ai-reusables
```

### Basic Usage

```python
from fx_ai_reusables.authenticators.hcp.concretes import HcpAuthenticator
from fx_ai_reusables.llm.creators import AzureChatOpenAILlmCreator
from fx_ai_reusables.configmaps.concretes import EnvironmentVariablesConfigMapRetriever
from fx_ai_reusables.secrets.concretes import EnvironmentVariableSecretRetriever
from fx_ai_reusables.environment_loading.concretes import AzureLlmConfigAndSecretsHolderWrapperReader

# Set up configuration and authentication
config_map_retriever = EnvironmentVariablesConfigMapRetriever()
secrets_retriever = EnvironmentVariableSecretRetriever()
environment_reader = AzureLlmConfigAndSecretsHolderWrapperReader(config_map_retriever, secrets_retriever)

# Create HCP authenticator
hcp_authenticator = HcpAuthenticator(environment_reader)

# Initialize Azure OpenAI LLM
llm_creator = AzureChatOpenAILlmCreator(environment_reader, hcp_authenticator)
llm = await llm_creator.create_llm()

# Use the LLM
response = await llm.ainvoke("Hello, how are you?")
print(response.content)
```

## 🏗️ Architecture

FX AI Reusables is built around several core modules:

- **🔐 Authentication** - HCP (Healthcare Cloud Platform) token management
- **🤖 LLM Creators** - Factory patterns for Azure OpenAI models
- **📊 Vector Stores** - Document embedding and similarity search
- **📄 Document Processing** - Chunking and parsing utilities
- **⚙️ Configuration** - Environment-based config and secrets management
- **🔧 Tools** - Reusable AI workflow components

## 📋 Core Components

### Authentication (`authenticators/`)

- **HCP Authenticator**: Manages Healthcare Cloud Platform authentication tokens
- **Cache-aside decorators**: Efficient token caching strategies
- **Factory patterns**: Flexible authenticator creation

### LLM Integration (`llm/`)

- **Azure OpenAI Creators**: Factory classes for Azure-hosted OpenAI models
- **LangChain Integration**: Seamless integration with LangChain ecosystem
- **Model Configuration**: Environment-driven model selection and configuration
- **Reporters**: LLM usage tracking and monitoring

### Document Processing (`chunkers/`, `file_parsers/`)

- **Chunkers**: Split documents by source folder or custom strategies
- **Source Code Chunkers**: Specialized chunking for code repositories
- **File Parsers**: JSON, XML, and XSD parsing utilities
- **Sampling**: Example implementations and test data

### Vector Storage (`vectorizers/`)

- **Vector Store Creators**: Factory patterns for vector database connections
- **Data Layer**: Abstraction over different vector storage backends
- **Helpers**: Utility functions for embedding and similarity operations
- **Constants**: Configuration constants for vector operations

### Configuration Management (`configmaps/`, `secrets/`, `environment_loading/`)

- **Environment Loading**: Unified config and secrets loading from environment variables
- **Config Maps**: Structured configuration retrieval patterns
- **Secrets Management**: Secure handling of API keys and credentials
- **DTOs**: Data transfer objects for configuration structures

### Workflow Components (`question_answer/`, `supervisors/`, `tools/`)

- **Question-Answer Chains**: Pre-built conversational workflow components
- **Supervisors**: Workflow orchestration and management
- **Strategies**: Pluggable strategy patterns for different use cases
- **Tools**: Reusable AI workflow tools and utilities

## 🔧 Configuration

The library uses environment variables for configuration. See the `.env.example` file for a complete list of configuration options.

Key variables include:

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your-endpoint
AZURE_OPENAI_API_VERSION=your-api-version
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment

# HCP Authentication
HCP_CLIENT_ID=your-client-id
HCP_CLIENT_SECRET=your-client-secret
HCP_TOKEN_URL=your-token-url
```

For a complete configuration template, copy `.env.example` to `.env` and update with your values.

## 🛠️ Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd fx-ai-reusables

# Install in development mode
pip install -e .
```

---

## 📋 TODO: Future Documentation

- [] **Tutorial Notebooks**: Create step-by-step Jupyter notebooks for common workflows
- [] **Example Organization**: Create dedicated `examples/` folder with READMEs
- [] **Environment Setup Guide**: Detailed Azure/HCP configuration walkthrough
- [] **Architecture Deep Dive**: Detailed explanation of design patterns and interfaces
- [] **Best Practices Guide**: Recommended patterns for enterprise AI workflows
- [] **Testing Guide**: How to run tests and add new test cases
- [] **Performance Guide**: Optimization tips and benchmarking examples
