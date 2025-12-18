# HashiCorp Vault Secret Retriever

This implementation provides a Python secret retriever for HashiCorp Vault that works seamlessly with the existing secret retriever interface. It's designed to be a drop-in replacement for other secret retrievers like environment variables or volume mounts.

## Features

- **Dual Interface Support**: Both async and synchronous interfaces available
- **Synchronous Wrapper**: `SyncHashiCorpVaultSecretRetriever` provides sync interface for DI containers
- **Lazy Loading**: Secrets are loaded from Vault only when first accessed
- **Thread Safety**: Uses locks to ensure safe concurrent access
- **Caching**: Secrets are cached in memory after loading to avoid repeated Vault calls
- **Multiple Creation Patterns**: Direct instantiation, factory methods, environment variables, ConfigMap retriever, and builder pattern
- **ConfigMap Integration**: Use ConfigMap retrievers for configuration while keeping tokens secure in environment variables
- **Reusable**: Easy to integrate into any Python application or dependency injection framework
- **Error Handling**: Comprehensive error handling with detailed logging
- **Validation**: Input validation and secret validation (prevents name/value matches)
- **Configurable Timeouts**: HTTP timeout configuration for Vault requests

## Requirements

Add to your `requirements.txt`:
```
aiohttp>=3.8.0
```

## Configuration

The HashiCorp Vault secret retriever supports two configuration approaches:

### Option 1: ConfigMap Retriever (Recommended)
Use a ConfigMap retriever for configuration values while keeping the authentication token secure in environment variables:

- **ConfigMap Values**: Vault URL, namespace, secret paths, timeout
- **Environment Variable**: Vault token (for security)

### Option 2: Environment Variables
All configuration values including the token are provided via environment variables.

**Configuration Values:**
- **Vault URL**: Base URL of your HashiCorp Vault instance (e.g., `https://vault.example.com`)
- **Vault Namespace**: The namespace to use for Vault operations
- **Vault Token**: Authentication token for accessing Vault
- **Secret Paths**: List of secret paths to load from Vault (e.g., `["app/config", "app/database"]`)
- **Timeout** (optional): HTTP request timeout in seconds (default: 30)

## Usage Examples

### 1. Direct Creation

```python
import asyncio
from fx_ai_reusables.secrets.concretes.hashicorp_vault import HashiCorpVaultSecretRetriever

async def example():
    retriever = HashiCorpVaultSecretRetriever(
        vault_url="https://vault.example.com",
        vault_namespace="my-namespace",
        vault_token="hvs.AQAAAQAAAAAAA",
        secret_paths=["app/config", "app/database"],
        timeout=30
    )
    
    # Get optional secret
    secret_value = await retriever.retrieve_optional_secret_value("database_password")
    
    # Get mandatory secret (raises ValueError if not found)
    api_key = await retriever.retrieve_mandatory_secret_value("api_key")
    
    # Get secret DTO
    secret_dto = await retriever.retrieve_secret("ssl_certificate")
    if secret_dto:
        print(f"Secret: {secret_dto.secret_name}")
        value = secret_dto.secret_value

asyncio.run(example())
```

### 2. Factory Creation

```python
from fx_ai_reusables.secrets.concretes.hashicorp_vault import HashiCorpVaultSecretRetrieverFactory

# Simple factory creation
retriever = HashiCorpVaultSecretRetrieverFactory.create(
    vault_url="https://vault.example.com",
    vault_namespace="my-namespace",
    vault_token="hvs.AQAAAQAAAAAAA",
    secret_paths=["app/config", "app/database"]
)
```

### 3. Environment Variables

Set environment variables:
```bash
export HASHIVAULT_URL="https://vault.example.com"
export HASHIVAULT_NAMESPACE="my-namespace"
export HASHIVAULT_TOKEN="hvs.AQAAAQAAAAAAA"
export HASHIVAULT_SECRET_PATHS="app/config,app/database,shared/certificates"
export HASHIVAULT_TIMEOUT="60"
```

Create retriever:
```python
retriever = HashiCorpVaultSecretRetrieverFactory.create_from_env()
```

### 4. ConfigMap Retriever (Recommended)

#### Async Version
Use a ConfigMap retriever for configuration values while keeping the token as an environment variable for security:

```python
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.concretes.hashicorp_vault import HashiCorpVaultSecretRetrieverFactory

# Set token as environment variable (for security)
export HASHIVAULT_TOKEN="hvs.AQAAAQAAAAAAA"

# Create using ConfigMap retriever (async)
retriever = await HashiCorpVaultSecretRetrieverFactory.create_from_configmap(
    config_retriever=your_config_map_retriever
)
```

#### Synchronous Version (For DI Containers)
Perfect for dependency injection containers and synchronous applications:

```python
# Create synchronous version (no await needed!)
retriever = HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap(
    config_retriever=your_config_map_retriever
)

# Use synchronously - perfect for DI containers
secret_value = retriever.retrieve_optional_secret_value("my_secret")
```

**ConfigMap Values Required:**
- `HASHIVAULT_URL`: Vault URL
- `HASHIVAULT_NAMESPACE`: Vault namespace
- `HASHIVAULT_SECRET_PATHS`: Comma-separated list of secret paths
- `HASHIVAULT_TIMEOUT`: Optional timeout in seconds (default: 30)

**Environment Variable Required:**
- `HASHIVAULT_TOKEN`: Vault authentication token (kept as env var for security)

### 5. Builder Pattern

```python
retriever = HashiCorpVaultSecretRetrieverFactory.create_with_builder() \
    .vault_url("https://vault.example.com") \
    .vault_namespace("my-namespace") \
    .vault_token("hvs.AQAAAQAAAAAAA") \
    .add_secret_path("app/config") \
    .add_secret_path("app/database") \
    .add_secret_paths("shared/certificates", "shared/keys") \
    .timeout(90) \
    .build_retriever()
```

### 5. Configuration Object

```python
from fx_ai_reusables.secrets.concretes.hashicorp_vault import VaultConfiguration

config = VaultConfiguration(
    vault_url="https://vault.example.com",
    vault_namespace="my-namespace",
    vault_token="hvs.AQAAAQAAAAAAA",
    secret_paths=["app/config", "app/database"],
    timeout=120
)

retriever = HashiCorpVaultSecretRetrieverFactory.create_from_config(config)
```

## HashiCorp Vault Setup

This implementation works with HashiCorp Vault KV v2 secrets engine. The expected Vault response format is:

```json
{
    "data": {
        "data": {
            "database_password": "secret_value_1",
            "api_key": "secret_value_2",
            "ssl_certificate": "-----BEGIN CERTIFICATE-----..."
        }
    }
}
```

### Vault Configuration Steps

1. **Enable KV v2 secrets engine** (if not already enabled):
   ```bash
   vault secrets enable -path=kv kv-v2
   ```

2. **Store secrets**:
   ```bash
   vault kv put kv/app/config \
     database_password="my_secret_password" \
     api_key="my_api_key"
   
   vault kv put kv/app/database \
     connection_string="postgres://..." \
     ssl_certificate="-----BEGIN CERTIFICATE-----..."
   ```

3. **Create a policy** for your application:
   ```bash
   vault policy write my-app-policy - <<EOF
   path "kv/data/app/*" {
     capabilities = ["read"]
   }
   EOF
   ```

4. **Create a token** with the policy:
   ```bash
   vault token create -policy=my-app-policy
   ```

## Error Handling

The implementation provides detailed error handling:

- **Configuration Errors**: Invalid or missing configuration parameters
- **Network Errors**: Connection issues with Vault
- **Authentication Errors**: Invalid or expired tokens (403 errors)
- **Not Found Errors**: Missing secret paths (404 errors)
- **Validation Errors**: Secret name/value validation failures

Example error handling:
```python
try:
    secret_value = await retriever.retrieve_mandatory_secret_value("missing_secret")
except ValueError as e:
    print(f"Secret not found: {e}")
except PermissionError as e:
    print(f"Access denied: {e}")
except RuntimeError as e:
    print(f"Vault error: {e}")
```

## Logging

The retriever supports detailed logging. Configure logging to see debug information:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

retriever = HashiCorpVaultSecretRetriever(
    # ... configuration ...
    logger=logger
)
```

## Dependency Injection Integration

The synchronous version is specifically designed for dependency injection containers:

### With dependency-injector Library
```python
from dependency_injector import containers, providers
from fx_ai_reusables.secrets.concretes.hashicorp_vault import HashiCorpVaultSecretRetrieverFactory

class MyContainer(containers.DeclarativeContainer):
    # ConfigMap retriever
    config_retriever = providers.Factory(YourConfigMapRetriever)
    
    # HashiCorp Vault secret retriever (synchronous!)
    secret_retriever = providers.Callable(
        HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap,
        config_retriever=config_retriever,
        logger=providers.Callable(logging.getLogger, "VaultSecrets")
    )
    
    # Your application with injected secrets
    app = providers.Factory(
        YourApplication,
        secret_retriever=secret_retriever
    )
```

### Generic Factory Pattern
```python
def create_secret_retriever(config_retriever: IConfigMapRetriever) -> ISecretRetriever:
    """Factory function for any DI framework."""
    return HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap(
        config_retriever=config_retriever
    )
```

## Advanced Features

### Force Reload Secrets

```python
# Async version
await retriever.reload_secrets()

# Sync version
sync_retriever.reload_secrets()
```

### Check Status

```python
# Check if secrets are loaded
is_loaded = sync_retriever.is_initialized()

# Get list of cached secret names
secret_names = sync_retriever.get_cached_secret_names()
```

## Security Considerations

1. **Token Security**: Vault tokens should be stored securely and rotated regularly
2. **Network Security**: Use HTTPS for Vault connections in production
3. **Logging**: Tokens and secret values are not logged to prevent exposure
4. **Caching**: Secrets are cached in memory - consider memory protection in production
5. **Validation**: The implementation validates that secret names and values are not identical

## Comparison with Java Implementation

This Python implementation mirrors the Java version's functionality:

- Same configuration parameters and validation
- Same Vault API usage (KV v2)
- Same error handling patterns
- Same secret loading behavior (loads all secrets from specified paths)
- Same caching mechanism
- Same validation logic

## Testing

See `example_usage.py` for comprehensive usage examples. For testing with a real Vault instance, ensure you have:

1. A running HashiCorp Vault instance
2. KV v2 secrets engine enabled
3. Appropriate policies and tokens configured
4. Test secrets stored in the specified paths