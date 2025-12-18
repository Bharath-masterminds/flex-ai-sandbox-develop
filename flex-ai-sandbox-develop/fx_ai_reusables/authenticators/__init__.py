"""
Authentication module for reusables library.

Provides HCP (Healthcare Cloud Platform) authentication capabilities
with caching decorators for improved performance.
"""

from .hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator
from .hcp.concretes.hcp_authenticator import HcpAuthenticator
from .hcp.cache_aside_decorators.hcp_authenticator_cache_aside_decorator import HcpAuthenticatorCacheAsideDecorator

__all__ = [
    "IHcpAuthenticator",
    "HcpAuthenticator", 
    "HcpAuthenticatorCacheAsideDecorator"
]