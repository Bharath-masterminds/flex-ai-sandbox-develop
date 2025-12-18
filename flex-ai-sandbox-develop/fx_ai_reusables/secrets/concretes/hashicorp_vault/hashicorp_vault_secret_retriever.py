import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin
import aiohttp
import asyncio

from fx_ai_reusables.secrets.base.secret_validator import SecretValidator
from fx_ai_reusables.secrets.interfaces.dtos.secret_dto import SecretDto
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


class HashiCorpVaultSecretRetriever(ISecretRetriever):
    """
    HashiCorp Vault secret retriever implementation.
    
    Retrieves secrets from HashiCorp Vault using the KV v2 secrets engine.
    Configuration includes vault URL, namespace, token, and secret paths.
    """
    
    VAULT_URL_TEMPLATE = "{vault_url}/v1/kv/data/{secret_path}"
    
    def __init__(self, 
                 vault_url: str,
                 vault_namespace: str,
                 vault_token: str,
                 secret_paths: List[str],
                 logger: Optional[logging.Logger] = None,
                 timeout: int = 30):
        """
        Initialize the HashiCorp Vault secret retriever.
        
        Args:
            vault_url: The base URL of the HashiCorp Vault instance
            vault_namespace: The namespace to use for Vault operations
            vault_token: The authentication token for Vault
            secret_paths: List of secret paths to load from Vault
            logger: Optional logger instance
            timeout: HTTP request timeout in seconds (default: 30)
            
        Raises:
            ValueError: If any required configuration is missing or invalid
        """
        if not vault_url or not vault_url.strip():
            raise ValueError("Vault URL must be provided")
        if not vault_namespace or not vault_namespace.strip():
            raise ValueError("Vault namespace must be provided")
        if not vault_token or not vault_token.strip():
            raise ValueError("Vault token must be provided")
        if not secret_paths or len(secret_paths) == 0:
            raise ValueError("Secret paths must be provided")
            
        self.vault_url = vault_url.rstrip('/')
        self.vault_namespace = vault_namespace
        self.vault_token = vault_token
        self.secret_paths = secret_paths
        self.timeout = timeout
        self._logger = logger or logging.getLogger(__name__)
        
        # Cache for loaded secrets
        self._secrets_cache: Dict[str, str] = {}
        self._secrets_loaded = False
        self._load_lock = asyncio.Lock()

    async def retrieve_secret(self, name_of: str) -> Optional[SecretDto]:
        """
        Retrieve a secret by name from the cache.
        
        Args:
            name_of: The name of the secret to retrieve
            
        Returns:
            Optional SecretDto object containing the secret
        """
        self._logger.debug("Attempting secret retrieval for: %s", "***")
        
        # Ensure secrets are loaded
        await self._ensure_secrets_loaded()
        
        secret_value = self._secrets_cache.get(name_of)
        
        if not secret_value:
            self._logger.debug("Sensitive item not found in vault: %s", "***")
            return None
            
        # Validate that name and value are not the same
        SecretValidator.check_for_name_and_value_are_same(name_of, secret_value)
        
        if not secret_value.strip():
            self._logger.debug("Secret value is empty for secret: %s", "***")
            return None
            
        return SecretDto(secret_name=name_of, _secret_value=secret_value)

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
        secret_dto = await self.retrieve_secret(name_of)
        if secret_dto is None:
            raise ValueError(f"Missing mandatory secret: {name_of}")
        return secret_dto.secret_value

    async def retrieve_optional_secret_value(self, name_of: str) -> Optional[str]:
        """
        Retrieve an optional secret value by name.
        
        Args:
            name_of: The name of the secret to retrieve
            
        Returns:
            Optional string value of the secret
        """
        secret_dto = await self.retrieve_secret(name_of)
        return secret_dto.secret_value if secret_dto else None

    async def _ensure_secrets_loaded(self) -> None:
        """Ensure secrets are loaded from Vault (thread-safe)."""
        if self._secrets_loaded:
            return
            
        async with self._load_lock:
            if not self._secrets_loaded:
                await self._load_all_secrets()
                self._secrets_loaded = True

    async def _load_all_secrets(self) -> None:
        """
        Load all secrets from the configured secret paths in HashiCorp Vault.
        
        The Vault response structure for KV v2 is:
        {
            "data": {
                "data": {
                    "secretName1": "secretValue1",
                    "secretName2": "secretValue2"
                }
            }
        }
        """
        self._logger.debug("Loading secrets from %d secret paths", len(self.secret_paths))
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            
            for secret_path in self.secret_paths:
                try:
                    await self._load_secrets_from_path(session, secret_path)
                except Exception as e:
                    self._logger.error(
                        "Failed to load secrets from path '%s': %s", 
                        secret_path, str(e)
                    )
                    raise

        self._logger.info("Successfully loaded %d secrets from Vault", len(self._secrets_cache))

    async def _load_secrets_from_path(self, session: aiohttp.ClientSession, secret_path: str) -> None:
        """
        Load secrets from a specific path in Vault.
        
        Args:
            session: The aiohttp session to use
            secret_path: The vault secret path to load from
        """
        url = self.VAULT_URL_TEMPLATE.format(
            vault_url=self.vault_url,
            secret_path=secret_path
        )
        
        headers = {
            "Accept": "application/json",
            "X-Vault-Token": self.vault_token,
            "X-Vault-Namespace": self.vault_namespace
        }
        
        self._logger.debug("Making request to Vault for path: %s", secret_path)
        
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                response_data = await response.json()
                await self._process_vault_response(response_data, secret_path)
            elif response.status == 404:
                self._logger.warning("Secret path not found in Vault: %s", secret_path)
            elif response.status == 403:
                self._logger.error("Access denied to Vault path: %s (check token permissions)", secret_path)
                raise PermissionError(f"Access denied to Vault path: {secret_path}")
            else:
                error_text = await response.text()
                self._logger.error(
                    "Unexpected HTTP response from Vault: %d for path: %s. Response: %s",
                    response.status, secret_path, error_text
                )
                raise RuntimeError(
                    f"Unexpected HTTP response code from Vault: {response.status}. "
                    f"Usually this indicates an expired or invalid Vault token."
                )

    async def _process_vault_response(self, response_data: Dict, secret_path: str) -> None:
        """
        Process the JSON response from Vault and extract secrets.
        
        Args:
            response_data: The parsed JSON response from Vault
            secret_path: The secret path this response came from (for logging)
        """
        try:
            # Navigate to data.data in the response
            data_node = response_data.get("data", {})
            secrets_node = data_node.get("data", {})
            
            if not secrets_node:
                self._logger.warning("No secrets found in path: %s", secret_path)
                return
                
            # Extract each secret and add to cache
            secrets_count = 0
            for secret_name, secret_value in secrets_node.items():
                if isinstance(secret_value, str):
                    self._secrets_cache[secret_name] = secret_value
                    secrets_count += 1
                else:
                    # Convert non-string values to JSON strings
                    self._secrets_cache[secret_name] = json.dumps(secret_value)
                    secrets_count += 1
                    
            self._logger.debug("Loaded %d secrets from path: %s", secrets_count, secret_path)
            
        except Exception as e:
            self._logger.error("Error processing Vault response for path '%s': %s", secret_path, str(e))
            raise

    async def reload_secrets(self) -> None:
        """
        Force reload of all secrets from Vault.
        This can be used to refresh secrets if they have been updated in Vault.
        """
        self._logger.info("Force reloading secrets from Vault")
        async with self._load_lock:
            self._secrets_cache.clear()
            self._secrets_loaded = False
            await self._load_all_secrets()
            self._secrets_loaded = True
        self._logger.info("Successfully reloaded %d secrets from Vault", len(self._secrets_cache))

    def get_cached_secret_names(self) -> List[str]:
        """
        Get a list of all cached secret names (for debugging/monitoring).
        
        Returns:
            List of secret names currently in the cache
        """
        return list(self._secrets_cache.keys())

    def is_secrets_loaded(self) -> bool:
        """
        Check if secrets have been loaded from Vault.
        
        Returns:
            True if secrets are loaded, False otherwise
        """
        return self._secrets_loaded