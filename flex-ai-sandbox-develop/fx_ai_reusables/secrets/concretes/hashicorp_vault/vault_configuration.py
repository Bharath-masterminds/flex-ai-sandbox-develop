from dataclasses import dataclass, field
from typing import List, Optional
import os

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever


@dataclass
class VaultConfiguration:
    """Configuration for HashiCorp Vault connection."""
    
    vault_url: str
    vault_namespace: str
    vault_token: str = field(repr=False)  # Don't display token in logs
    secret_paths: List[str] = field(default_factory=list)
    timeout: int = 30
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.vault_url or not self.vault_url.strip():
            raise ValueError("Vault URL is required")
        if not self.vault_namespace or not self.vault_namespace.strip():
            raise ValueError("Vault namespace is required")
        if not self.vault_token or not self.vault_token.strip():
            raise ValueError("Vault token is required")
        if not self.secret_paths:
            raise ValueError("At least one secret path is required")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
            
        # Clean up vault URL
        self.vault_url = self.vault_url.rstrip('/')
    
    def __str__(self) -> str:
        """String representation without exposing the token."""
        return (f"VaultConfiguration(vault_url='{self.vault_url}', "
                f"vault_namespace='{self.vault_namespace}', "
                f"vault_token='***', "
                f"secret_paths={self.secret_paths}, "
                f"timeout={self.timeout}")


@dataclass 
class VaultConfigurationBuilder:
    """Builder pattern for VaultConfiguration to make it easier to construct."""
    
    _vault_url: Optional[str] = None
    _vault_namespace: Optional[str] = None
    _vault_token: Optional[str] = None
    _secret_paths: List[str] = field(default_factory=list)
    _timeout: int = 30
    
    def vault_url(self, url: str) -> 'VaultConfigurationBuilder':
        """Set the Vault URL."""
        self._vault_url = url
        return self
    
    def vault_namespace(self, namespace: str) -> 'VaultConfigurationBuilder':
        """Set the Vault namespace."""
        self._vault_namespace = namespace
        return self
    
    def vault_token(self, token: str) -> 'VaultConfigurationBuilder':
        """Set the Vault token."""
        self._vault_token = token
        return self
    
    def add_secret_path(self, path: str) -> 'VaultConfigurationBuilder':
        """Add a secret path to load from."""
        if path and path.strip():
            self._secret_paths.append(path.strip())
        return self
    
    def add_secret_paths(self, *paths: str) -> 'VaultConfigurationBuilder':
        """Add multiple secret paths to load from."""
        for path in paths:
            self.add_secret_path(path)
        return self
    
    def timeout(self, timeout_seconds: int) -> 'VaultConfigurationBuilder':
        """Set the HTTP timeout in seconds."""
        self._timeout = timeout_seconds
        return self
    
    def build(self) -> VaultConfiguration:
        """Build the VaultConfiguration."""
        return VaultConfiguration(
            vault_url=self._vault_url or "",
            vault_namespace=self._vault_namespace or "",
            vault_token=self._vault_token or "",
            secret_paths=self._secret_paths.copy(),
            timeout=self._timeout
        )


def create_vault_config_from_env() -> VaultConfiguration:
    """
    Create VaultConfiguration from environment variables.
    
    Expected environment variables:
    - HASHIVAULT_URL: Vault URL
    - HASHIVAULT_NAMESPACE: Vault namespace  
    - HASHIVAULT_TOKEN: Vault token
    - HASHIVAULT_SECRET_PATHS: Comma-separated list of secret paths
    - HASHIVAULT_TIMEOUT: Optional timeout in seconds (default: 30)
    
    Returns:
        VaultConfiguration instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    import os
    
    vault_url = os.getenv("HASHIVAULT_URL")
    vault_namespace = os.getenv("HASHIVAULT_NAMESPACE")
    vault_token = os.getenv("HASHIVAULT_TOKEN")
    secret_paths_str = os.getenv("HASHIVAULT_SECRET_PATHS")
    timeout_str = os.getenv("HASHIVAULT_TIMEOUT", "30")
    
    if not vault_url:
        raise ValueError("Environment variable HASHIVAULT_URL is required")
    if not vault_namespace:
        raise ValueError("Environment variable HASHIVAULT_NAMESPACE is required")
    if not vault_token:
        raise ValueError("Environment variable HASHIVAULT_TOKEN is required")
    if not secret_paths_str:
        raise ValueError("Environment variable HASHIVAULT_SECRET_PATHS is required")
    
    try:
        timeout = int(timeout_str)
    except ValueError:
        raise ValueError(f"Invalid timeout value in HASHIVAULT_TIMEOUT: {timeout_str}")
    
    # Parse comma-separated secret paths
    secret_paths = [path.strip() for path in secret_paths_str.split(',') if path.strip()]
    
    if not secret_paths:
        raise ValueError("No valid secret paths found in HASHIVAULT_SECRET_PATHS")
    
    return VaultConfiguration(
        vault_url=vault_url,
        vault_namespace=vault_namespace,
        vault_token=vault_token,
        secret_paths=secret_paths,
        timeout=timeout
    )


def create_vault_config_from_env() -> VaultConfiguration:
    """
    Create VaultConfiguration directly from environment variables.
    
    This is a synchronous function that reads configuration values directly
    from environment variables without needing async/await.
    
    Environment variables:
    - HASHIVAULT_TOKEN: Vault token (required)
    - HASHIVAULT_URL: Vault URL (required)
    - HASHIVAULT_NAMESPACE: Vault namespace (required)
    - HASHIVAULT_SECRET_PATHS: Comma-separated list of secret paths (required)
    - HASHIVAULT_TIMEOUT: Optional timeout in seconds (default: 30)
    
    Returns:
        VaultConfiguration instance
        
    Raises:
        ValueError: If required configuration values are missing
    """
    # Get all required values from environment variables
    vault_token = os.getenv("HASHIVAULT_TOKEN")
    if not vault_token:
        raise ValueError("Environment variable HASHIVAULT_TOKEN is required")
    
    vault_url = os.getenv("HASHIVAULT_URL")
    if not vault_url:
        raise ValueError("Environment variable HASHIVAULT_URL is required")
        
    vault_namespace = os.getenv("HASHIVAULT_NAMESPACE")
    if not vault_namespace:
        raise ValueError("Environment variable HASHIVAULT_NAMESPACE is required")
        
    secret_paths_str = os.getenv("HASHIVAULT_SECRET_PATHS")
    if not secret_paths_str:
        raise ValueError("Environment variable HASHIVAULT_SECRET_PATHS is required")
    
    timeout_str = os.getenv("HASHIVAULT_TIMEOUT") or "30"
    
    # Validate and parse timeout
    try:
        timeout = int(timeout_str)
    except ValueError:
        raise ValueError(f"Invalid timeout value in HASHIVAULT_TIMEOUT: {timeout_str}")
    
    # Parse comma-separated secret paths
    secret_paths = [path.strip() for path in secret_paths_str.split(',') if path.strip()]
    
    if not secret_paths:
        raise ValueError("No valid secret paths found in HASHIVAULT_SECRET_PATHS")
    
    return VaultConfiguration(
        vault_url=vault_url,
        vault_namespace=vault_namespace,
        vault_token=vault_token,
        secret_paths=secret_paths,
        timeout=timeout
    )


async def create_vault_config_from_configmap(config_retriever: IConfigMapRetriever) -> VaultConfiguration:
    """
    Create VaultConfiguration from config map retriever and environment variables.
    
    Config map values:
    - HASHIVAULT_URL: Vault URL
    - HASHIVAULT_NAMESPACE: Vault namespace
    - HASHIVAULT_SECRET_PATHS: Comma-separated list of secret paths
    - HASHIVAULT_TIMEOUT: Optional timeout in seconds (default: 30)
    
    Environment variable:
    - HASHIVAULT_TOKEN: Vault token (kept as env var for security)
    
    Args:
        config_retriever: The config map retriever to use for configuration values
        
    Returns:
        VaultConfiguration instance
        
    Raises:
        ValueError: If required configuration values are missing
    """
    # Get token from environment variable (for security)
    vault_token = os.getenv("HASHIVAULT_TOKEN")
    if not vault_token:
        raise ValueError("Environment variable HASHIVAULT_TOKEN is required")
    
    # Get configuration values from config map
    try:
        vault_url = await config_retriever.retrieve_mandatory_config_map_value("HASHIVAULT_URL")
        vault_namespace = await config_retriever.retrieve_mandatory_config_map_value("HASHIVAULT_NAMESPACE")
        secret_paths_str = await config_retriever.retrieve_mandatory_config_map_value("HASHIVAULT_SECRET_PATHS")
        timeout_str = await config_retriever.retrieve_optional_config_map_value("HASHIVAULT_TIMEOUT") or "30"
    except Exception as e:
        raise ValueError(f"Failed to retrieve required configuration from config map: {str(e)}")
    
    # Validate and parse timeout
    try:
        timeout = int(timeout_str)
    except ValueError:
        raise ValueError(f"Invalid timeout value in HASHIVAULT_TIMEOUT: {timeout_str}")
    
    # Parse comma-separated secret paths
    secret_paths = [path.strip() for path in secret_paths_str.split(',') if path.strip()]
    
    if not secret_paths:
        raise ValueError("No valid secret paths found in HASHIVAULT_SECRET_PATHS")
    
    return VaultConfiguration(
        vault_url=vault_url,
        vault_namespace=vault_namespace,
        vault_token=vault_token,
        secret_paths=secret_paths,
        timeout=timeout
    )