# Configuration for HashiCorp Vault in DevelopmentLocal

When running with `DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL`, the application will use HashiCorp Vault for secret retrieval.

## Required Configuration

### Environment Variables Setup

#### 1. Deployment Configuration
```bash
export DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL
```

#### 2. HashiCorp Vault Token (Security - Environment Variable)
```bash
export HASHIVAULT_TOKEN="hvs.AQAAAQAAAAAAA"
```

#### 3. HashiCorp Vault Configuration (ConfigMap - Environment Variables)
```bash
export HASHIVAULT_URL="https://vault.example.com"
export HASHIVAULT_NAMESPACE="my-namespace"
export HASHIVAULT_SECRET_PATHS="app/config,app/database"
export HASHIVAULT_TIMEOUT="60"  # Optional, defaults to 30
```

#### 4. Azure AD Redirect URI
```bash
export AAD_REDIRECT_URI="http://localhost:8501"
```

## How It Works

1. **Configuration Source**: The composition root uses `EnvironmentVariablesConfigMapRetriever` for configuration values and keeps the token as an environment variable for security.

2. **Lazy Initialization**: The `HashiVaultSecretRetrieverWrapper` handles the async initialization of the HashiCorp Vault connection when secrets are first accessed.

3. **Fallback**: Other deployment flavors (K8DEPLOYED, GITWORKFLOWDEPLOYED) still use `EnvironmentVariableSecretRetriever` as before.

## Complete Setup Example

### 1. Create .env file (recommended)
Create a `.env` file in the project root with:
```bash
# Deployment Configuration
DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL

# HashiCorp Vault Configuration
HASHIVAULT_TOKEN=hvs.AQAAAQAAAAAAA
HASHIVAULT_URL=https://vault.example.com
HASHIVAULT_NAMESPACE=my-namespace
HASHIVAULT_SECRET_PATHS=app/config,app/database,shared/certificates
HASHIVAULT_TIMEOUT=60

# Azure AD Authentication (if needed)

AAD_REDIRECT_URI=http://localhost:8501
```

### 2. Or export environment variables manually
```bash
# Set the deployment flavor
export DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL

# Set Vault configuration
export HASHIVAULT_URL="https://vault.example.com"
export HASHIVAULT_NAMESPACE="my-namespace"
export HASHIVAULT_TOKEN="hvs.AQAAAQAAAAAAA"
export HASHIVAULT_SECRET_PATHS="app/config,app/database,shared/certificates"
export HASHIVAULT_TIMEOUT="45"

# Set Azure AD (if needed)
export AAD_REDIRECT_URI="http://localhost:8501"

```

### 3. Run the application
```bash
# Set Python path
export PYTHONPATH=$(pwd)

# Run your application
streamlit run use_cases/liquid_template_generator/app.py
```

## Integration Notes

- The wrapper ensures thread-safe lazy initialization of the Vault connection
- All secret retrieval methods are async-compatible
- Configuration errors will be reported when secrets are first accessed
- The Vault token remains in environment variables for security best practices