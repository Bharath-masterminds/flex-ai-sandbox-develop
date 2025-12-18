"""
Interfaces for Streamlit Azure AD authentication.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging


class IStreamlitAzureAuth(ABC):
    """
    Interface for Streamlit Azure AD authentication functionality.
    
    This interface defines the contract for implementing Azure AD authentication
    in Streamlit applications, including login, logout, token management, and
    user session validation.
    """
    
    @abstractmethod
    def check_authentication(self) -> bool:
        """
        Check if the user is authenticated and handle login if not.
        
        Returns:
            bool: True if user is authenticated, False otherwise.
                  Note: This method may stop Streamlit execution if auth is required.
        """
        pass
    
    @abstractmethod
    def handle_login(self) -> None:
        """
        Handle the Azure AD login flow.
        
        This method manages the OAuth2 authorization code flow, including
        generating login URLs and processing authentication callbacks.
        """
        pass
    
    @abstractmethod
    def handle_logout(self) -> None:
        """
        Handle user logout by clearing the session state.
        
        This method clears all authentication-related session data and
        redirects the user to the login page.
        """
        pass
    
    @abstractmethod
    def is_token_valid(self) -> bool:
        """
        Validate if the stored access token is still valid.
        
        Returns:
            bool: True if token is valid, False if expired or invalid
        """
        pass
    
    @abstractmethod
    def refresh_access_token(self) -> bool:
        """
        Attempt to refresh the access token using the refresh token.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get the current authenticated user's information.
        
        Returns:
            Optional[Dict[str, Any]]: User information dict if authenticated, None otherwise
        """
        pass
    
    @abstractmethod
    def get_access_token(self) -> Optional[str]:
        """
        Get the current access token.
        
        Returns:
            Optional[str]: Access token if available and valid, None otherwise
        """
        pass
    
    @abstractmethod
    def show_user_info_sidebar(self) -> None:
        """
        Display user information and logout button in the Streamlit sidebar.
        
        This is a convenience method for showing authenticated user details
        and providing logout functionality in the sidebar.
        """
        pass