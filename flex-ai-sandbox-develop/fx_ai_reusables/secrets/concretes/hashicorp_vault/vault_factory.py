import logging
from typing import List, Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from .hashicorp_vault_secret_retriever import HashiCorpVaultSecretRetriever
from .sync_hashicorp_vault_secret_retriever import SyncHashiCorpVaultSecretRetriever
from .vault_configuration import VaultConfiguration, VaultConfigurationBuilder, create_vault_config_from_env, create_vault_config_from_configmap


class HashiCorpVaultSecretRetrieverFactory:
    """Factory class for creating HashiCorp Vault secret retrievers."""
    
    @staticmethod
    def create_from_config(
        config: VaultConfiguration,
        logger: Optional[logging.Logger] = None
    ) -> HashiCorpVaultSecretRetriever:
        """
        Create a HashiCorp Vault secret retriever from configuration.
        
        Args:
            config: VaultConfiguration instance
            logger: Optional logger
            
        Returns:
            HashiCorpVaultSecretRetriever instance
        """
        return HashiCorpVaultSecretRetriever(
            vault_url=config.vault_url,
            vault_namespace=config.vault_namespace,
            vault_token=config.vault_token,
            secret_paths=config.secret_paths,
            logger=logger,
            timeout=config.timeout
        )
    
    @staticmethod
    def create_from_env(
        logger: Optional[logging.Logger] = None
    ) -> HashiCorpVaultSecretRetriever:
        """
        Create a HashiCorp Vault secret retriever from environment variables.
        
        Expected environment variables:
        - HASHIVAULT_URL: Vault URL
        - HASHIVAULT_NAMESPACE: Vault namespace  
        - HASHIVAULT_TOKEN: Vault token
        - HASHIVAULT_SECRET_PATHS: Comma-separated list of secret paths
        - HASHIVAULT_TIMEOUT: Optional timeout in seconds (default: 30)
        
        Args:
            logger: Optional logger
            
        Returns:
            HashiCorpVaultSecretRetriever instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        config = create_vault_config_from_env()
        return HashiCorpVaultSecretRetrieverFactory.create_from_config(config, logger)
    
    @staticmethod
    async def create_from_configmap(
        config_retriever: IConfigMapRetriever,
        logger: Optional[logging.Logger] = None
    ) -> HashiCorpVaultSecretRetriever:
        """
        Create a HashiCorp Vault secret retriever from config map retriever.
        
        Config map values:
        - HASHIVAULT_URL: Vault URL
        - HASHIVAULT_NAMESPACE: Vault namespace
        - HASHIVAULT_SECRET_PATHS: Comma-separated list of secret paths
        - HASHIVAULT_TIMEOUT: Optional timeout in seconds (default: 30)
        
        Environment variable:
        - HASHIVAULT_TOKEN: Vault token (kept as env var for security)
        
        Args:
            config_retriever: The config map retriever to use for configuration values
            logger: Optional logger
            
        Returns:
            HashiCorpVaultSecretRetriever instance
            
        Raises:
            ValueError: If required configuration values are missing
        """
        config = await create_vault_config_from_configmap(config_retriever)
        return HashiCorpVaultSecretRetrieverFactory.create_from_config(config, logger)
    
    @staticmethod
    def create_sync_from_env(logger: Optional[logging.Logger] = None) -> ISecretRetriever:
        """
        Create a synchronous HashiCorp Vault secret retriever from environment variables.
        
        This method returns a synchronous wrapper that handles async operations internally,
        making it suitable for use in dependency injection containers and synchronous code.
        
        Environment variables:
        - HASHIVAULT_TOKEN: Vault token (required)
        - HASHIVAULT_URL: Vault URL (required)
        - HASHIVAULT_NAMESPACE: Vault namespace (required)
        - HASHIVAULT_SECRET_PATHS: Comma-separated list of secret paths (required)
        - HASHIVAULT_TIMEOUT: Optional timeout in seconds (default: 30)
        
        Args:
            logger: Optional logger
            
        Returns:
            ISecretRetriever instance (synchronous wrapper)
            
        Raises:
            ValueError: If required configuration values are missing (on first use)
        """
        return SyncHashiCorpVaultSecretRetriever(logger=logger)

    @staticmethod 
    def create_sync_from_configmap(
        config_retriever: IConfigMapRetriever,
        logger: Optional[logging.Logger] = None
    ) -> ISecretRetriever:
        """
        Create a synchronous HashiCorp Vault secret retriever from config map retriever.
        
        DEPRECATED: Use create_sync_from_env() instead for simpler configuration.
        This method is kept for backward compatibility but just reads from env vars.
        
        Args:
            config_retriever: The config map retriever (ignored, kept for compatibility)
            logger: Optional logger
            
        Returns:
            ISecretRetriever instance (synchronous wrapper)
        """
        # Just delegate to the env-based method since it's simpler
        return HashiCorpVaultSecretRetrieverFactory.create_sync_from_env(logger)
    
    @staticmethod
    def create_with_builder(logger: Optional[logging.Logger] = None) -> VaultConfigurationBuilder:
        """
        Create a builder for configuring and creating a HashiCorp Vault secret retriever.
        
        Args:
            logger: Optional logger
            
        Returns:
            VaultConfigurationBuilder instance
            
        Example:
            retriever = HashiCorpVaultSecretRetrieverFactory.create_with_builder() \\
                .vault_url("https://vault.example.com") \\
                .vault_namespace("my-namespace") \\
                .vault_token("hvs.AQAAAQAAAAAAA") \\
                .add_secret_paths("app/config", "app/database") \\
                .timeout(45) \\
                .build_retriever()
        """
        
        class BuilderWithRetrieverFactory(VaultConfigurationBuilder):
            def build_retriever(self) -> HashiCorpVaultSecretRetriever:
                """Build the VaultConfiguration and create the secret retriever."""
                config = self.build()
                return HashiCorpVaultSecretRetrieverFactory.create_from_config(config, logger)
        
        return BuilderWithRetrieverFactory()
    
    @staticmethod
    def create(
        vault_url: str,
        vault_namespace: str,
        vault_token: str,
        secret_paths: List[str],
        timeout: int = 30,
        logger: Optional[logging.Logger] = None
    ) -> HashiCorpVaultSecretRetriever:
        """
        Create a HashiCorp Vault secret retriever with direct parameters.
        
        Args:
            vault_url: The base URL of the HashiCorp Vault instance
            vault_namespace: The namespace to use for Vault operations
            vault_token: The authentication token for Vault
            secret_paths: List of secret paths to load from Vault
            timeout: HTTP request timeout in seconds (default: 30)
            logger: Optional logger
            
        Returns:
            HashiCorpVaultSecretRetriever instance
        """
        return HashiCorpVaultSecretRetriever(
            vault_url=vault_url,
            vault_namespace=vault_namespace,
            vault_token=vault_token,
            secret_paths=secret_paths,
            logger=logger,
            timeout=timeout
        )