"""
Example usage of HashiCorp Vault Secret Retriever with ConfigMap Retriever.

This example demonstrates how to use the HashiCorp Vault secret retriever
with a ConfigMap retriever for configuration values while keeping the
token as an environment variable for security.
"""

import asyncio
import logging
import os
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever, ConfigMapDto
from fx_ai_reusables.secrets.concretes.hashicorp_vault import (
    HashiCorpVaultSecretRetrieverFactory,
    create_vault_config_from_configmap
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockConfigMapRetriever(IConfigMapRetriever):
    """Mock ConfigMap retriever for demonstration purposes."""
    
    def __init__(self):
        # Mock configuration data
        self.config_data = {
            "HASHIVAULT_URL": "https://vault.example.com",
            "HASHIVAULT_NAMESPACE": "my-namespace",
            "HASHIVAULT_SECRET_PATHS": "app/config,app/database,shared/certificates",
            "HASHIVAULT_TIMEOUT": "60"
        }
    
    async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
        """Retrieve a config map by name."""
        value = self.config_data.get(configuration_item_name)
        if value:
            return ConfigMapDto(name=configuration_item_name, value=value)
        return None
    
    async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
        """Retrieve a mandatory config map value by name."""
        value = self.config_data.get(configuration_item_name)
        if not value:
            raise ValueError(f"Required configuration item '{configuration_item_name}' not found")
        return value
    
    async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
        """Retrieve an optional config map value by name."""
        return self.config_data.get(configuration_item_name)


async def example_configmap_creation():
    """Example: Creating HashiCorp Vault secret retriever with ConfigMap."""
    print("\n=== ConfigMap Creation Example ===")
    
    # Set the token as environment variable (for security)
    os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"
    
    try:
        # Create mock config map retriever
        config_retriever = MockConfigMapRetriever()
        
        # Create vault secret retriever using config map
        vault_retriever = await HashiCorpVaultSecretRetrieverFactory.create_from_configmap(
            config_retriever=config_retriever,
            logger=logger
        )
        
        print("✅ Successfully created HashiCorp Vault secret retriever from ConfigMap")
        
        # Example usage
        try:
            secret_value = await vault_retriever.retrieve_optional_secret_value("database_password")
            if secret_value:
                print(f"Retrieved secret successfully: {'*' * len(secret_value)}")
            else:
                print("Secret not found (expected since this is a demo)")
        except Exception as e:
            print(f"Expected error when trying to connect to mock vault: {type(e).__name__}")
        
    except Exception as e:
        print(f"Error in configmap creation: {e}")


async def example_direct_config_creation():
    """Example: Creating VaultConfiguration directly from ConfigMap."""
    print("\n=== Direct Config Creation Example ===")
    
    # Set the token as environment variable (for security)
    os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"
    
    try:
        # Create mock config map retriever
        config_retriever = MockConfigMapRetriever()
        
        # Create vault configuration from config map
        vault_config = await create_vault_config_from_configmap(config_retriever)
        
        print(f"✅ Successfully created vault configuration: {vault_config}")
        
        # Create retriever from configuration
        vault_retriever = HashiCorpVaultSecretRetrieverFactory.create_from_config(
            config=vault_config,
            logger=logger
        )
        
        print("✅ Successfully created HashiCorp Vault secret retriever from configuration")
        
    except Exception as e:
        print(f"Error in direct config creation: {e}")


async def example_config_validation():
    """Example: Demonstrating configuration validation."""
    print("\n=== Configuration Validation Example ===")
    
    # Test with missing token
    if "HASHIVAULT_TOKEN" in os.environ:
        del os.environ["HASHIVAULT_TOKEN"]
    
    try:
        config_retriever = MockConfigMapRetriever()
        vault_config = await create_vault_config_from_configmap(config_retriever)
        print("❌ Should have failed without token")
    except ValueError as e:
        print(f"✅ Correctly validated missing token: {e}")
    
    # Test with missing config map values
    try:
        class EmptyConfigMapRetriever(IConfigMapRetriever):
            async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
                return None
            
            async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
                raise ValueError(f"Configuration item '{configuration_item_name}' not found")
            
            async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
                return None
        
        empty_retriever = EmptyConfigMapRetriever()
        os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"  # Set token back
        
        vault_config = await create_vault_config_from_configmap(empty_retriever)
        print("❌ Should have failed without config values")
    except ValueError as e:
        print(f"✅ Correctly validated missing config values: {e}")


async def main():
    """Run all examples."""
    print("HashiCorp Vault Secret Retriever with ConfigMap Examples")
    print("=" * 60)
    
    await example_configmap_creation()
    await example_direct_config_creation()
    await example_config_validation()
    
    print("\n=== Examples completed ===")
    print("Note: Vault connection examples fail because no real Vault instance is configured.")
    print("Configuration retrieval examples demonstrate the API usage patterns.")
    
    print("\n=== Configuration Summary ===")
    print("Values retrieved from ConfigMap:")
    print("- HASHIVAULT_URL")
    print("- HASHIVAULT_NAMESPACE") 
    print("- HASHIVAULT_SECRET_PATHS")
    print("- HASHIVAULT_TIMEOUT (optional)")
    print("")
    print("Value retrieved from Environment Variable:")
    print("- HASHIVAULT_TOKEN (for security)")


if __name__ == "__main__":
    asyncio.run(main())