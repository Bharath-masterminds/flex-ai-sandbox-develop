"""
Example usage of the StreamlitAzureAuth reusable module.

This demonstrates how to use the streamlit Azure authentication module
in your own Streamlit applications.
"""

import logging
import streamlit as st
from fx_ai_reusables.streamlit.authenticators import StreamlitAzureAuth
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever

# Example usage
def create_streamlit_app_with_auth(
    secret_retriever: ISecretRetriever,
    config_map_retriever: IConfigMapRetriever
):
    """
    Example of how to create a Streamlit app with Azure AD authentication.
    
    Args:
        secret_retriever: Your configured secret retriever service
        config_map_retriever: Your configured config map retriever service
    """
    
    # Configure page settings first (before authentication check)
    st.set_page_config(
        page_title="My Secure App",
        page_icon="🔐",
        layout="wide"
    )
    
    # Initialize Azure authentication
    azure_auth = StreamlitAzureAuth(
        secret_retriever=secret_retriever,
        config_map_retriever=config_map_retriever,
        logger=logging.getLogger(__name__)
        # Optional: scope=["User.Read", "Mail.Read"]  # Custom scopes if needed
    )
    
    # Check authentication - will stop execution if not authenticated
    if not azure_auth.check_authentication():
        return
    
    # Your authenticated app content starts here
    st.title("🔐 Secure Streamlit App")
    st.success("You are successfully authenticated!")
    
    # Show user info in sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        azure_auth.show_user_info_sidebar()
        
        # Your other sidebar content here
        st.subheader("App Settings")
        # ... other settings ...
    
    # Main app content
    user_info = azure_auth.get_user_info()
    if user_info:
        st.write(f"Hello, {user_info.get('name', 'User')}!")
        st.write("Your user details:")
        st.json(user_info)
    
    # Get access token if you need to make API calls
    access_token = azure_auth.get_access_token()
    if access_token:
        st.write("✅ Access token is available for API calls")
        # Use the token for Microsoft Graph API calls, etc.
    
    # Your main application logic goes here
    st.write("## Your App Content")
    st.info("Build your secure Streamlit app features here!")


# Required configuration for Azure AD authentication:
"""
The StreamlitAzureAuth module requires the following secrets to be configured:
- AAD_CLIENT_ID: Azure AD application client ID
- AAD_CLIENT_SECRET: Azure AD application client secret  
- AAD_TENANT_ID: Azure AD tenant ID
- AAD_REDIRECT_URI: OAuth2 redirect URI (optional, defaults to http://localhost:8501)

And these config map values:
- AAD_LOGIN_BASE_URL: Azure AD login base URL (optional, defaults to https://login.microsoftonline.com)
- AAD_GRAPH_API_URL: Microsoft Graph API URL (optional, defaults to https://graph.microsoft.com/v1.0/me)

Example of using the module in different DI containers:
"""

# Example with your IoC container
def example_usage_with_ioc():
    """
    Example showing how to integrate with dependency injection.
    """
    # Assuming you have your IoC container set up
    # container = your_ioc_container()
    # secret_retriever = container.get(ISecretRetriever)
    # config_map_retriever = container.get(IConfigMapRetriever)
    
    # create_streamlit_app_with_auth(secret_retriever, config_map_retriever)
    pass


# Simple direct usage example
def simple_usage_example():
    """
    Simple example for quick prototyping.
    """
    # You would implement these based on your secret/config storage
    # secret_retriever = YourSecretRetriever()
    # config_map_retriever = YourConfigMapRetriever()
    
    # create_streamlit_app_with_auth(secret_retriever, config_map_retriever)
    pass