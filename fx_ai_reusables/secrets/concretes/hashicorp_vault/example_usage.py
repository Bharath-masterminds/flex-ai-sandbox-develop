"""
Example usage of the HashiCorp Vault Secret Retriever.

This example demonstrates how to use the HashiCorp Vault secret retriever
in different ways: directly, with a factory, from environment variables,
and with a builder pattern.
"""

import asyncio
import logging
import os
from fx_ai_reusables.secrets.concretes.hashicorp_vault import (
    HashiCorpVaultSecretRetriever,
    HashiCorpVaultSecretRetrieverFactory,
    VaultConfiguration,
    VaultConfigurationBuilder,
    create_vault_config_from_env
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_direct_creation():
    """Example: Direct creation of the secret retriever."""
    print("\n=== Direct Creation Example ===")
    
    try:
        retriever = HashiCorpVaultSecretRetriever(
            vault_url="https://vault.example.com",
            vault_namespace="my-namespace",
            vault_token="hvs.AQAAAQAAAAAAA",
            secret_paths=["app/config", "app/database"],
            timeout=30,
            logger=logger
        )
        
        # Example usage
        secret_value = await retriever.retrieve_optional_secret_value("database_password")
        if secret_value:
            print("Retrieved secret successfully")
        else:
            print("Secret not found")
            
    except Exception as e:
        print(f"Error in direct creation: {e}")


async def example_factory_creation():
    """Example: Using the factory to create the secret retriever."""
    print("\n=== Factory Creation Example ===")
    
    try:
        retriever = HashiCorpVaultSecretRetrieverFactory.create(
            vault_url="https://vault.example.com",
            vault_namespace="my-namespace", 
            vault_token="hvs.AQAAAQAAAAAAA",
            secret_paths=["app/config", "app/database"],
            timeout=45,
            logger=logger
        )
        
        # Example usage
        mandatory_secret = await retriever.retrieve_mandatory_secret_value("api_key")
        print("Retrieved mandatory secret")
        
    except Exception as e:
        print(f"Error in factory creation: {e}")


async def example_env_creation():
    """Example: Creating from environment variables."""
    print("\n=== Environment Variables Creation Example ===")
    
    # Set example environment variables (in real usage, these would be set externally)
    os.environ["HASHIVAULT_URL"] = "https://vault.example.com"
    os.environ["HASHIVAULT_NAMESPACE"] = "my-namespace"
    os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA" 
    os.environ["HASHIVAULT_SECRET_PATHS"] = "app/config,app/database,shared/certificates"
    os.environ["HASHIVAULT_TIMEOUT"] = "60"
    
    try:
        retriever = HashiCorpVaultSecretRetrieverFactory.create_from_env(
            logger=logger
        )
        
        # Example usage
        secret_dto = await retriever.retrieve_secret("ssl_certificate")
        if secret_dto:
            print("Retrieved secret DTO")
        else:
            print("Secret not found")
            
    except Exception as e:
        print(f"Error in env creation: {e}")


async def example_builder_creation():
    """Example: Using the builder pattern."""
    print("\n=== Builder Pattern Creation Example ===")
    
    try:
        retriever = HashiCorpVaultSecretRetrieverFactory.create_with_builder(logger) \
            .vault_url("https://vault.example.com") \
            .vault_namespace("my-namespace") \
            .vault_token("hvs.AQAAAQAAAAAAA") \
            .add_secret_path("app/config") \
            .add_secret_path("app/database") \
            .add_secret_paths("shared/certificates", "shared/keys") \
            .timeout(90) \
            .build_retriever()
        
        # Example usage - get list of available secrets
        print("Secrets loaded")
        secret_names = retriever.get_cached_secret_names()
        
    except Exception as e:
        print(f"Error in builder creation: {e}")


async def example_configuration_object():
    """Example: Using VaultConfiguration object."""
    print("\n=== Configuration Object Example ===")
    
    try:
        config = VaultConfiguration(
            vault_url="https://vault.example.com",
            vault_namespace="my-namespace",
            vault_token="hvs.AQAAAQAAAAAAA",
            secret_paths=["app/config", "app/database"],
            timeout=120
        )
        
        print(f"Configuration: {config}")
        
        retriever = HashiCorpVaultSecretRetrieverFactory.create_from_config(
            config=config,
            logger=logger
        )
        
        # Force reload secrets (useful if secrets change in Vault)
        await retriever.reload_secrets()
        print("Secrets reloaded successfully")
        
    except Exception as e:
        print(f"Error in configuration creation: {e}")


async def main():
    """Run all examples."""
    print("HashiCorp Vault Secret Retriever Examples")
    print("=" * 50)
    
    # Note: These examples will fail because we don't have a real Vault instance
    # They are provided to show the API usage patterns
    
    await example_direct_creation()
    await example_factory_creation() 
    await example_env_creation()
    await example_builder_creation()
    await example_configuration_object()
    
    print("\n=== Examples completed ===")
    print("Note: Examples failed because no real Vault instance is configured.")
    print("In real usage, configure proper Vault URL, namespace, token, and secret paths.")


if __name__ == "__main__":
    asyncio.run(main())