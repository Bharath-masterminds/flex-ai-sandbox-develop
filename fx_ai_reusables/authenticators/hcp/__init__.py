"""
HCP (Healthcare Cloud Platform) authentication module.
"""

from .interfaces.hcp_authenticator_interface import IHcpAuthenticator
from .concretes.hcp_authenticator import HcpAuthenticator
from .cache_aside_decorators.hcp_authenticator_cache_aside_decorator import HcpAuthenticatorCacheAsideDecorator

__all__ = [
    "IHcpAuthenticator",
    "HcpAuthenticator", 
    "HcpAuthenticatorCacheAsideDecorator"
]