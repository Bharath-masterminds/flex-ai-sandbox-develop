"""
Concrete implementation of Streamlit Azure AD authentication.
"""

import json
import logging
import time
import uuid
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import msal
import requests
import streamlit as st

from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.helpers import run_async_in_sync_context
from .interfaces import IStreamlitAzureAuth


class StreamlitAzureAuth(IStreamlitAzureAuth):
    """
    Concrete implementation of Azure AD authentication for Streamlit applications.
    
    This class provides a complete Azure AD authentication flow including:
    - OAuth2 authorization code flow
    - Token management (access and refresh tokens)
    - Automatic token refresh
    - User session management
    - Logout functionality
    """
    
    def __init__(self,
                 secret_retriever: ISecretRetriever,
                 config_map_retriever: IConfigMapRetriever,
                 logger: Optional[logging.Logger] = None,
                 scope: Optional[list] = None):
        """
        Initialize the StreamlitAzureAuth.
        
        Args:
            secret_retriever: Service for retrieving Azure AD configuration secrets
            config_map_retriever: Service for retrieving Azure AD URL configuration
            logger: Optional logger instance
            scope: Optional list of OAuth2 scopes (defaults to ["User.Read"])
        """
        self.secret_retriever = secret_retriever
        self.config_map_retriever = config_map_retriever
        self._logger = logger or logging.getLogger(__name__)
        self.scope = scope or ["User.Read"]
        
        # Constants for token refresh
        self.REFRESH_BUFFER_SECONDS = 300  # 5 minutes buffer before expiration
    
    def _get_azure_ad_urls(self) -> Dict[str, str]:
        """Retrieve Azure AD URL configuration from config map."""
        try:
            login_base_url = run_async_in_sync_context(
                self.config_map_retriever.retrieve_mandatory_config_map_value, 
                "AAD_LOGIN_BASE_URL"
            )
            graph_api_url = run_async_in_sync_context(
                self.config_map_retriever.retrieve_mandatory_config_map_value, 
                "AAD_GRAPH_API_URL"
            )
            
            return {
                'login_base_url': login_base_url,
                'graph_api_url': graph_api_url
            }
        except Exception as e:
            self._logger.error(f"Error retrieving Azure AD URL configuration: {str(e)}")
            return {
                'login_base_url': "https://login.microsoftonline.com",
                'graph_api_url': "https://graph.microsoft.com/v1.0/me"
            }
    
    def _get_azure_ad_config(self) -> Dict[str, Optional[str]]:
        """Retrieve Azure AD configuration from secret retriever and config map."""
        try:
            # Get secrets from secret retriever
            client_id = run_async_in_sync_context(self.secret_retriever.retrieve_secret, "AAD_CLIENT_ID")
            client_secret = run_async_in_sync_context(self.secret_retriever.retrieve_secret, "AAD_CLIENT_SECRET")
            tenant_id = run_async_in_sync_context(self.secret_retriever.retrieve_secret, "AAD_TENANT_ID")
            
            # Get redirect URI from config map
            try:
                redirect_uri = run_async_in_sync_context(
                    self.config_map_retriever.retrieve_mandatory_config_map_value,
                    "AAD_REDIRECT_URI"
                )
            except Exception as e:
                self._logger.warning(f"Could not retrieve AAD_REDIRECT_URI from config map: {str(e)}")
                redirect_uri = "http://localhost:8501"  # Default fallback
            
            config = {
                'client_id': client_id.secret_value if client_id else None,
                'client_secret': client_secret.secret_value if client_secret else None,
                'tenant_id': tenant_id.secret_value if tenant_id else None,
                'redirect_uri': redirect_uri
            }
            
            return config
        except Exception as e:
            self._logger.error(f"Error retrieving Azure AD configuration: {str(e)}")
            return {
                'client_id': None,
                'client_secret': None,
                'tenant_id': None,
                'redirect_uri': "http://localhost:8501"
            }
    
    def _build_msal_app(self) -> msal.ConfidentialClientApplication:
        """Build and return MSAL application instance for Web app (server-side)."""
        config = self._get_azure_ad_config()
        urls = self._get_azure_ad_urls()
        
        if not all([config['client_id'], config['client_secret'], config['tenant_id']]):
            raise ValueError("Missing required Azure AD configuration: CLIENT_ID, CLIENT_SECRET, or TENANT_ID")
        
        authority = f"{urls['login_base_url']}/{config['tenant_id']}"
        
        return msal.ConfidentialClientApplication(
            config['client_id'],
            authority=authority,
            client_credential=config['client_secret']
        )
    
    def handle_login(self) -> None:
        """Handle Azure AD login flow."""
        config = self._get_azure_ad_config()
        urls = self._get_azure_ad_urls()
        
        if not all([config['client_id'], config['tenant_id']]):
            st.error("Azure AD configuration is missing. Please check your secret configuration.")
            return
            
        authority = f"{urls['login_base_url']}/{config['tenant_id']}"
        
        # Check if we have a code from the redirect
        query_params = st.query_params
        code = query_params.get("code", None)
        
        if code:
            # Exchange code for token using Web app flow
            app = self._build_msal_app()
            
            # Check if we have a state parameter for validation
            state = query_params.get("state", None)
            stored_state = st.session_state.get("auth_state")
            
            if stored_state and state != stored_state:
                self._logger.warning("State parameter mismatch - possible CSRF attack")
                st.error("Security validation failed. Please try logging in again.")
                st.session_state.clear()
                st.query_params.clear()
                st.rerun()
                return
            
            # Perform token exchange
            token_response = app.acquire_token_by_authorization_code(
                code,
                scopes=self.scope,
                redirect_uri=config['redirect_uri']
            )

            if "access_token" in token_response:
                # Store token and expiration info
                st.session_state["access_token"] = token_response["access_token"]
                
                # Store token expiration information from token response
                if "expires_in" in token_response:
                    # expires_in is in seconds, so add to current time to get expiration timestamp
                    token_expires_at = int(time.time()) + token_response["expires_in"]
                    st.session_state["token_expires_at"] = token_expires_at
                    st.session_state["token_expires_in"] = token_response["expires_in"]
                    self._logger.debug(f"Token expires in {token_response['expires_in']} seconds (at timestamp: {token_expires_at})")
                
                # Store refresh token if available
                if "refresh_token" in token_response:
                    st.session_state["refresh_token"] = token_response["refresh_token"]
                    self._logger.debug("Refresh token stored for future token renewal")
                
                user_response = requests.get(
                    urls['graph_api_url'],
                    headers={"Authorization": f"Bearer {token_response['access_token']}"}
                )
                
                if user_response.status_code == 200:
                    user_info = user_response.json()
                    
                    # Store token claims separately for validation
                    if 'id_token_claims' in token_response:
                        token_claims = token_response['id_token_claims']
                        st.session_state["id_token_claims"] = token_claims
                        
                        # Merge token claims into user_info, prioritizing Graph API data
                        for key, value in token_claims.items():
                            if key not in user_info and value:
                                user_info[key] = value
                    
                    st.session_state["user_info"] = user_info
                    
                    # User authorization is now handled by Azure AD roles
                    st.success("Login successful! Redirecting...")
                    self._logger.info(f"User logged in: {user_info.get('userPrincipalName', 'Unknown')}")
                    st.rerun()
                else:
                    st.error("Failed to get user information.")
            else:
                st.error("Authentication failed.")
        else:
            # Build authorization URL for Web app flow
            random_state = str(uuid.uuid4())
            
            params = {
                "client_id": config['client_id'],
                "response_type": "code",
                "redirect_uri": config['redirect_uri'],
                "response_mode": "query",
                "scope": " ".join(self.scope),
                "state": random_state,
                "prompt": "select_account"  # Force login screen even if user is already authenticated
            }
            
            login_url = f"{authority}/oauth2/v2.0/authorize?{urlencode(params)}"
            
            # Store state for CSRF validation
            st.session_state["auth_state"] = random_state
            
            # Use custom HTML button with JavaScript to force same-tab navigation
            # This ensures the OAuth flow happens in the current tab
            st.markdown(
                f"""
                <a href="{login_url}" target="_self">
                    <button style="
                        background-color: #0078D4;
                        color: white;
                        padding: 0.75rem 1.5rem;
                        font-size: 1rem;
                        font-weight: 500;
                        border: none;
                        border-radius: 0.5rem;
                        cursor: pointer;
                        width: 100%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 0.5rem;
                        transition: background-color 0.3s;
                    "
                    onmouseover="this.style.backgroundColor='#106EBE'"
                    onmouseout="this.style.backgroundColor='#0078D4'">
                        🔐 Login
                    </button>
                </a>
                """,
                unsafe_allow_html=True
            )
    
    def refresh_access_token(self) -> bool:
        """
        Attempt to refresh the access token using the refresh token.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        try:
            refresh_token = st.session_state.get("refresh_token")
            if not refresh_token:
                self._logger.warning("No refresh token available for token renewal")
                return False

            self._logger.info("Attempting to refresh access token")
            
            # Build MSAL app and use refresh token
            app = self._build_msal_app()
            
            # Use MSAL to refresh the token
            token_response = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self.scope
            )
            
            if "access_token" in token_response:
                # Store new access token and expiration info
                st.session_state["access_token"] = token_response["access_token"]
                
                if "expires_in" in token_response:
                    token_expires_at = int(time.time()) + token_response["expires_in"]
                    st.session_state["token_expires_at"] = token_expires_at
                    st.session_state["token_expires_in"] = token_response["expires_in"]
                    self._logger.info(f"Access token refreshed successfully. New expiration: {token_expires_at}")
                
                # Update refresh token if a new one was provided
                if "refresh_token" in token_response:
                    st.session_state["refresh_token"] = token_response["refresh_token"]
                    self._logger.debug("Refresh token updated")
                
                return True
            else:
                self._logger.warning("Token refresh failed - no access token in response")
                if "error" in token_response:
                    self._logger.warning(f"Refresh error: {token_response.get('error')}: {token_response.get('error_description', '')}")
                return False
                
        except Exception as e:
            self._logger.error(f"Error refreshing token: {str(e)}")
            return False
    
    def is_token_valid(self) -> bool:
        """
        Validate if the stored access token is still valid, attempting refresh if expired.
        
        Returns:
            bool: True if token is valid (including after refresh), False if invalid/refresh failed
        """
        try:
            # Check if we have token expiration info from the token response
            token_expires_at = st.session_state.get("token_expires_at")
            if not token_expires_at:
                self._logger.warning("No token expiration timestamp found in session")
                return False

            # Get current time as Unix timestamp
            current_time = int(time.time())
            
            # Check if token is expired or about to expire
            if current_time >= (token_expires_at - self.REFRESH_BUFFER_SECONDS):
                expires_in_original = st.session_state.get("token_expires_in", "unknown")
                self._logger.info(f"Access token expired or expiring soon. Current: {current_time}, Expires at: {token_expires_at} (was valid for {expires_in_original} seconds)")
                
                # Try to refresh the token
                if self.refresh_access_token():
                    self._logger.info("Access token refreshed successfully")
                    return True
                else:
                    self._logger.warning("Failed to refresh access token - user will need to re-authenticate")
                    return False
                
            # Token is still valid
            seconds_remaining = token_expires_at - current_time
            self._logger.debug(f"Access token is valid. Expires in {seconds_remaining} seconds")
            return True
            
        except Exception as e:
            self._logger.error(f"Error validating token: {str(e)}")
            return False
    
    def check_authentication(self) -> bool:
        """Check if user is authenticated and handle login if not."""
        # First check if we have an access token
        if "access_token" not in st.session_state:
            # Check if we're in the middle of OAuth flow (have authorization code)
            query_params = st.query_params
            code = query_params.get("code", None)
            
            if code:
                # We're processing the OAuth callback - show processing message
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.title("🔐 Processing Login...")
                    st.info("Completing authentication, please wait...")
                self.handle_login()
                st.stop()  # This stops execution here
                return False
            else:
                # No token and no code - show login screen
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.title("🔐 Login Required")
                    st.warning("You must log in to access this app.")
                    self.handle_login()
                st.stop()  # This stops execution here
                return False
        
        # We have an access token, now validate if it's still valid
        if not self.is_token_valid():
            self._logger.info("Token has expired, clearing session and requiring re-login")
            # Token is expired, clear session and require login
            st.session_state.clear()
            st.query_params.clear()
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.title("🔐 Session Expired")
                st.warning("Your session has expired. Please log in again.")
                self.handle_login()
            st.stop()
            return False
            
        return True
    
    def handle_logout(self) -> None:
        """Handle user logout by clearing local session only."""
        try:
            # Log the logout event
            user_info = st.session_state.get("user_info", {})
            self._logger.info(f"User logged out: {user_info.get('userPrincipalName', 'Unknown')}")
            
            # Clear all session state
            st.session_state.clear()
            
            # Clear URL parameters to prevent stale authorization code processing
            st.query_params.clear()
            
            # Show logout message and redirect back to clean login
            st.success("Successfully logged out!")
            st.info("Redirecting to login page...")
            
            # Redirect back to login page without Azure AD logout
            st.rerun()
            
        except Exception as e:
            self._logger.error(f"Error during logout: {str(e)}")
            # Clear session and URL params even if something fails
            st.session_state.clear()
            st.query_params.clear()
            st.error("Error during logout. Please refresh the page.")
            st.rerun()
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get the current authenticated user's information.
        
        Returns:
            Optional[Dict[str, Any]]: User information dict if authenticated, None otherwise
        """
        return st.session_state.get("user_info")
    
    def get_access_token(self) -> Optional[str]:
        """
        Get the current access token.
        
        Returns:
            Optional[str]: Access token if available and valid, None otherwise
        """
        if self.is_token_valid():
            return st.session_state.get("access_token")
        return None
    
    def show_user_info_sidebar(self) -> None:
        """
        Display user information and logout button in the Streamlit sidebar.
        
        This is a convenience method for showing authenticated user details
        and providing logout functionality in the sidebar.
        """
        user_info = self.get_user_info()
        if user_info:
            st.divider()
            st.subheader("👤 User")
            st.write(f"**Logged in as:**")
            st.write(f"{user_info.get('name', 'Unknown User')}")
            st.write(f"{user_info.get('userPrincipalName', 'Unknown UserId')}")
            
            if st.button("🚪 Logout", help="Sign out and clear session", use_container_width=True):
                self.handle_logout()
            
            st.divider()