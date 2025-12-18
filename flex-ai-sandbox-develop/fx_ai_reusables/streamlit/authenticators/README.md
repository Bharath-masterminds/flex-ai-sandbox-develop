# Streamlit Azure AD Authentication

A reusable Azure Active Directory authentication module for Streamlit applications.

## Features

- **Complete OAuth2 Authorization Code Flow**: Secure server-side authentication
- **Automatic Token Management**: Handles access and refresh tokens automatically
- **Token Refresh**: Proactively refreshes tokens before expiration
- **Session Management**: Maintains user sessions across page reloads
- **Security**: Includes CSRF protection with state validation
- **Easy Integration**: Simple dependency injection pattern
- **Customizable Scopes**: Configure OAuth2 scopes as needed
- **Error Handling**: Comprehensive error handling and logging

## Quick Start

```python
import streamlit as st
from fx_ai_reusables.streamlit.authenticators import StreamlitAzureAuth

# Initialize authentication (with your DI container)
azure_auth = StreamlitAzureAuth(
    secret_retriever=your_secret_retriever,
    config_map_retriever=your_config_map_retriever,
    logger=your_logger  # optional
)

# Configure Streamlit page
st.set_page_config(page_title="My Secure App", page_icon="🔐")

# Check authentication - stops execution if not authenticated
if not azure_auth.check_authentication():
    return

# Your authenticated app content
st.title("🔐 Secure App")
st.success("You are authenticated!")

# Show user info in sidebar
with st.sidebar:
    azure_auth.show_user_info_sidebar()
```

## Setup and Configuration

### Azure AD Setup Process

#### 1. Create Secure Group
Create a secure group (for MS/Windows platform) with a meaningful name starting with `AZU_`:
- Example: `AZU_YourAppName_Users` 
- This group will control who can access your Streamlit application

#### 2. Add Group to Your MS ID
Add the secure group to your Microsoft ID via the secure group management system.

#### 3. Create OIDC SSO App Registration
1. Go to the OIDC Automation portal: https://console.hcp.uhg.com/dashboard/security-identity-and-compliance/oidc-automation/az-oidc
2. Create a new OIDC SSO app (Azure App registration) for your application
3. Supply the secure group created in step 1 for the AD Group field
4. Configure redirect URI (typically `http://localhost:8501` for local development)

**Important**: Because you added the AD Group to the OIDC SSO, Azure AD authentication will automatically validate that users attempting to log in are part of the secure group. No additional authentication checks are needed at the application level.

#### 4. Store Credentials in HashiCorp Vault
After creating the OIDC SSO app, you'll receive:
- OIDC SSO client ID
- OIDC SSO client secret  
- Tenant ID

Store these securely in HashiCorp Vault and configure the vault path in your environment variables (see HashiCorp Secret Retriever README for details).

### Configuration Requirements

#### Required Secrets (HashiCorp Vault)
Configure these secrets in your secret store (hashi, keyvault, env variables):

- `AAD_CLIENT_ID`: Azure AD application client ID (from OIDC SSO setup)
- `AAD_CLIENT_SECRET`: Azure AD application client secret (from OIDC SSO setup)
- `AAD_TENANT_ID`: Azure AD tenant ID (from OIDC SSO setup)

#### Required Config Map Values  
Configure these in your config store (.env, env variables, config maps)

- `AAD_REDIRECT_URI`: OAuth2 redirect URI (e.g., `http://localhost:8501` for local, production URL for deployed apps)


Optional:
- `AAD_LOGIN_BASE_URL`: Azure AD login base URL (optional, defaults to `https://login.microsoftonline.com`)
- `AAD_GRAPH_API_URL`: Microsoft Graph API URL (optional, defaults to `https://graph.microsoft.com/v1.0/me`)

### Environment Setup

#### HashiCorp Vault Configuration
Ensure your environment variables are configured for HashiCorp Vault access:
```bash
# Example environment variables (refer to HashiCorp Secret Retriever README for complete setup)
HASHIVAULT_TOKEN=hvs.EXAMPLE_TOKEN_REPLACE_WITH_YOUR_ACTUAL_TOKEN
HASHIVAULT_URL=https://your-vault-server.company.com  # Vault server URL  
HASHIVAULT_NAMESPACE=YOUR/ORG/APP/ENV         # Vault namespace
HASHIVAULT_SECRET_PATHS=path/to/your/secrets,path/to/other/secrets
```

#### Development vs Production
- **Development**: Use `http://localhost:8501` as redirect URI
- **Production**: Use your actual application URL as redirect URI (e.g., `https://yourapp.yourdomain.com`)

### Security Features

#### Automatic Group-Based Authorization
- Users must be members of the specified secure group to authenticate
- No additional authorization logic needed in your application
- Group membership is validated during the Azure AD login process

#### Token Management
- Automatic token refresh with 5-minute buffer before expiration
- Secure token storage in Streamlit session state
- CSRF protection with state parameter validation

## API Reference

### StreamlitAzureAuth Class

#### Constructor
```python
StreamlitAzureAuth(
    secret_retriever: ISecretRetriever,
    config_map_retriever: IConfigMapRetriever,
    logger: Optional[logging.Logger] = None,
    scope: Optional[list] = None  # defaults to ["User.Read"]
)
```

#### Methods

##### `check_authentication() -> bool`
Main method to check authentication status. Call this before your app content.
- Returns `True` if authenticated, `False` if not
- Automatically handles login flow and token validation
- Stops Streamlit execution if authentication is required

##### `handle_login() -> None`
Manages the OAuth2 login flow. Usually called automatically by `check_authentication()`.

##### `handle_logout() -> None` 
Clears session and logs out the user.

##### `get_user_info() -> Optional[Dict[str, Any]]`
Returns the authenticated user's information from Microsoft Graph API.

##### `get_access_token() -> Optional[str]`
Returns the current valid access token for API calls.

##### `show_user_info_sidebar() -> None`
Convenience method to display user info and logout button in Streamlit sidebar.

##### `is_token_valid() -> bool`
Checks if the current token is valid (handles automatic refresh).

##### `refresh_access_token() -> bool`
Manually refresh the access token using the refresh token.

## Usage Examples

### Basic Usage
```python
# Check authentication
if not azure_auth.check_authentication():
    return

# Your app content here
st.write("Welcome to the authenticated app!")
```

### Custom Scopes
```python
# Initialize with custom scopes
azure_auth = StreamlitAzureAuth(
    secret_retriever=secret_retriever,
    config_map_retriever=config_map_retriever,
    scope=["User.Read", "Mail.Read", "Calendars.Read"]
)
```

### Making Authenticated API Calls
```python
import requests

# Get user info
user_info = azure_auth.get_user_info()
st.write(f"Hello, {user_info['name']}!")

# Get access token for API calls
token = azure_auth.get_access_token()
if token:
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("https://graph.microsoft.com/v1.0/me/messages", headers=headers)
    # Handle response...
```

### Custom User Interface
```python
# Custom sidebar layout
with st.sidebar:
    user_info = azure_auth.get_user_info()
    if user_info:
        st.write(f"👋 Hello, {user_info['name']}")
        if st.button("Logout"):
            azure_auth.handle_logout()
```

## Security Features

- **CSRF Protection**: Uses state parameter validation
- **Token Expiration**: Automatic token refresh with 5-minute buffer
- **Secure Storage**: Tokens stored in Streamlit session state
- **Error Handling**: Comprehensive error handling and logging

## Requirements

- `streamlit`
- `msal` (Microsoft Authentication Library)
- `requests`
- Your configured secret and config map retrievers

## Azure AD Application Setup

### Automated Setup (Recommended)
Use the OIDC Automation portal for streamlined setup:

1. **Access Portal**: https://console.hcp.uhg.com/dashboard/security-identity-and-compliance/oidc-automation/az-oidc
2. **Create Application**: Follow the guided process to create your OIDC SSO app
3. **Configure Group Access**: Specify your secure group (e.g., `AZU_YourAppName_Users`)
4. **Set Redirect URI**: Configure based on your deployment environment
5. **Retrieve Credentials**: Note the generated Client ID, Client Secret, and Tenant ID

### Manual Setup (Alternative)
If using manual Azure AD registration:

1. Register an application in Azure AD portal
2. Configure redirect URI (e.g., `http://localhost:8501` for local development)
3. Generate client secret in "Certificates & secrets" section
4. Configure required permissions (minimum: `User.Read`)
5. Set up group-based access control in "Token configuration"
6. Note down Client ID, Client Secret, and Tenant ID

### Key Configuration Points

#### Redirect URI Configuration
- **Local Development**: `http://localhost:8501`
- **Deployed Application**: `https://your-app-domain.com`
- **Multiple Environments**: Add multiple redirect URIs for dev/staging/prod

#### Required Permissions
- `User.Read` (minimum) - for basic user profile information
- Additional scopes can be configured via the `scope` parameter in `StreamlitAzureAuth`

#### Group-Based Access Control
- Ensure your secure group is properly linked to the Azure AD application
- Users not in the specified group will be denied access automatically
- No additional code required for group validation

## Troubleshooting

### Common Setup Issues

1. **"Azure AD configuration is missing"**
   - **Cause**: Missing or incorrect secrets in HashiCorp Vault
   - **Solution**: 
     - Verify `AAD_CLIENT_ID`, `AAD_CLIENT_SECRET`, and `AAD_TENANT_ID` are stored in vault
     - Check vault path configuration in environment variables
     - Ensure secret retriever has proper vault access permissions

2. **"Security validation failed"**  
   - **Cause**: State parameter mismatch (CSRF protection)
   - **Solution**: 
     - Clear browser cache and cookies
     - Ensure redirect URI matches exactly between config and Azure AD app
     - Check for network issues during auth flow

3. **"User not authorized" or login loop**
   - **Cause**: User not in the specified secure group
   - **Solution**:
     - Verify user is added to the secure group (e.g., `AZU_YourAppName_Users`)
     - Check that the correct secure group is linked to the Azure AD application
     - Confirm group membership propagation (can take up to 24 hours)

4. **Token refresh failures**
   - **Cause**: Azure AD app configuration or network issues
   - **Solution**:
     - Verify Azure AD app configuration and permissions
     - Check network connectivity to Azure AD endpoints
     - Review application logs for specific error messages
     - Ensure app registration hasn't expired

5. **Redirect URI mismatch**
   - **Cause**: Configured redirect URI doesn't match the actual application URL
   - **Solution**:
     - Update `AAD_REDIRECT_URI` in config map to match your application URL
     - Ensure Azure AD app registration includes the same redirect URI
     - For local development, use `http://localhost:8501`

6. **HashiCorp Vault access issues**
   - **Cause**: Incorrect vault configuration or permissions
   - **Solution**:
     - Verify `HASHIVAULT_URL`, `HASHIVAULT_TOKEN`, `HASHIVAULT_NAMESPACE`, and `HASHIVAULT_SECRET_PATHS` configuration
     - Check vault access permissions for the service account
     - Ensure vault namespace and secret paths are correct
     - Refer to HashiCorp Secret Retriever documentation
     - Test vault access independently of the Streamlit app

### Setup Validation Checklist

- [ ] Secure group created with `AZU_` prefix
- [ ] User added to secure group  
- [ ] OIDC SSO app created via automation portal
- [ ] Secure group linked to OIDC SSO app
- [ ] Client ID, Client Secret, and Tenant ID stored in HashiCorp Vault
- [ ] Redirect URI configured in both config map and Azure AD app
- [ ] HashiCorp Vault access working (test with secret retriever)
- [ ] Environment variables configured for vault access (`HASHIVAULT_TOKEN`, `HASHIVAULT_URL`, `HASHIVAULT_NAMESPACE`, `HASHIVAULT_SECRET_PATHS`)
- [ ] Application deployment URL matches redirect URI (for production)

### Debug Mode
Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

azure_auth = StreamlitAzureAuth(
    secret_retriever=secret_retriever,
    config_map_retriever=config_map_retriever,
    logger=logging.getLogger(__name__)
)
```

## Integration with Existing Projects

To migrate from inline authentication code:

1. Replace authentication methods with `StreamlitAzureAuth` instance
2. Update method calls:
   - `self.check_authentication()` → `self.azure_auth.check_authentication()`  
   - `self._handle_logout()` → `self.azure_auth.handle_logout()`
3. Use `azure_auth.show_user_info_sidebar()` for user info display
4. Remove inline authentication code and imports

See `example_usage.py` for complete examples.