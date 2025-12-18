"""
Streamlit Azure AD Authentication Module

This module provides reusable Azure AD authentication functionality for Streamlit applications.
"""

from .interfaces import IStreamlitAzureAuth
from .streamlit_azure_auth import StreamlitAzureAuth

__all__ = [
    'IStreamlitAzureAuth',
    'StreamlitAzureAuth'
]