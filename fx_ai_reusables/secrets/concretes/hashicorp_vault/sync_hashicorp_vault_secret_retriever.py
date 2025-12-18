import asyncio
import logging
from typing import Dict, List, Optional
from threading import Lock, Thread
import concurrent.futures

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.dtos.secret_dto import SecretDto
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from .hashicorp_vault_secret_retriever import HashiCorpVaultSecretRetriever
from .vault_configuration import create_vault_config_from_env


class SyncHashiCorpVaultSecretRetriever(ISecretRetriever):
    """
    Synchronous wrapper for HashiCorp Vault secret retriever.
    
    This class provides a synchronous interface by reading configuration
    directly from environment variables (no async needed for that part).
    Only the actual Vault HTTP operations use async internally.
    
    Features:
    - Lazy initialization: Vault connection established on first use
    - Thread-safe: Uses locks to prevent race conditions  
    - Synchronous interface: Compatible with existing sync code
    - Simple configuration: Reads directly from environment variables
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the synchronous HashiCorp Vault secret retriever.
        
        Configuration is read directly from environment variables:
        - HASHIVAULT_TOKEN, HASHIVAULT_URL, HASHIVAULT_NAMESPACE, etc.
        
        Args:
            logger: Optional logger instance
        """
        self._logger = logger or logging.getLogger(__name__)
        self._vault_retriever: Optional[HashiCorpVaultSecretRetriever] = None
        self._initialization_lock = Lock()
        self._initialized = False
        
    def _ensure_initialized(self) -> None:
        """Ensure the vault retriever is initialized (thread-safe lazy initialization)."""
        if not self._initialized:
            with self._initialization_lock:
                if not self._initialized:
                    try:
                        # Read configuration synchronously from environment variables
                        config = create_vault_config_from_env()
                        
                        # Create the async vault retriever
                        self._vault_retriever = HashiCorpVaultSecretRetriever(
                            vault_url=config.vault_url,
                            vault_namespace=config.vault_namespace,
                            vault_token=config.vault_token,
                            secret_paths=config.secret_paths,
                            logger=self._logger,
                            timeout=config.timeout
                        )
                        
                        # Force load secrets to validate configuration (using async in thread)
                        self._run_async(self._vault_retriever._ensure_secrets_loaded())
                        
                        self._initialized = True
                        self._logger.info("HashiCorp Vault secret retriever initialized successfully")
                        
                    except Exception as e:
                        self._logger.error(f"Failed to initialize HashiCorp Vault secret retriever: {e}")
                        raise ValueError(f"HashiCorp Vault initialization failed: {e}")
    
    def _run_async(self, coro):
        """Run an async coroutine in a sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, we need to run in a thread
                import concurrent.futures
                import threading
                
                result = None
                exception = None
                
                def run_in_thread():
                    nonlocal result, exception
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(coro)
                        new_loop.close()
                    except Exception as e:
                        exception = e
                
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                
                if exception:
                    raise exception
                return result
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    
    async def retrieve_secret(self, name_of: str) -> Optional[SecretDto]:
        """
        Retrieve a secret by name.
        
        Args:
            name_of: The name of the secret to retrieve
            
        Returns:
            Optional SecretDto object containing the secret
        """
        self._ensure_initialized()
        return self._run_async(self._vault_retriever.retrieve_secret(name_of))
    
    async def retrieve_mandatory_secret_value(self, name_of: str) -> str:
        """
        Retrieve a mandatory secret value by name.
        
        Args:
            name_of: The name of the secret to retrieve
            
        Returns:
            The secret value as a string
            
        Raises:
            ValueError: If the secret is not found or is empty
        """
        self._ensure_initialized()
        return self._run_async(self._vault_retriever.retrieve_mandatory_secret_value(name_of))
    
    async def retrieve_optional_secret_value(self, name_of: str) -> Optional[str]:
        """
        Retrieve an optional secret value by name.
        
        Args:
            name_of: The name of the secret to retrieve
            
        Returns:
            Optional string value of the secret
        """
        self._ensure_initialized()
        return self._run_async(self._vault_retriever.retrieve_optional_secret_value(name_of))
    
    def reload_secrets(self) -> None:
        """
        Force reload of all secrets from Vault.
        This can be used to refresh secrets if they have been updated in Vault.
        """
        self._ensure_initialized()
        self._run_async(self._vault_retriever.reload_secrets())
    
    def get_cached_secret_names(self) -> List[str]:
        """
        Get a list of all cached secret names (for debugging/monitoring).
        
        Returns:
            List of secret names currently in the cache
        """
        self._ensure_initialized()
        return self._vault_retriever.get_cached_secret_names()
    
    def is_initialized(self) -> bool:
        """
        Check if the vault retriever has been initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized