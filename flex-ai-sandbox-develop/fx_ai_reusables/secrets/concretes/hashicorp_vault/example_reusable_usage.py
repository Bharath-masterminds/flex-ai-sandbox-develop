"""
Example: Using HashiCorp Vault Secret Retriever in Any Application

This example demonstrates how to use the reusable synchronous HashiCorp Vault 
secret retriever in any Python application or dependency injection container.
"""

import logging
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever, ConfigMapDto
from fx_ai_reusables.secrets.concretes.hashicorp_vault import HashiCorpVaultSecretRetrieverFactory
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from typing import Optional
import os


class MockConfigMapRetriever(IConfigMapRetriever):
    """Mock ConfigMap retriever for demonstration."""
    
    def __init__(self):
        self.config_data = {
            "HASHIVAULT_URL": "https://vault.example.com",
            "HASHIVAULT_NAMESPACE": "my-namespace",
            "HASHIVAULT_SECRET_PATHS": "app/config,app/database",
            "HASHIVAULT_TIMEOUT": "45"
        }
    
    async def retrieve_config_map(self, configuration_item_name: str) -> Optional[ConfigMapDto]:
        value = self.config_data.get(configuration_item_name)
        if value:
            return ConfigMapDto(name=configuration_item_name, value=value)
        return None
    
    async def retrieve_mandatory_config_map_value(self, configuration_item_name: str) -> str:
        value = self.config_data.get(configuration_item_name)
        if not value:
            raise ValueError(f"Required configuration item '{configuration_item_name}' not found")
        return value
    
    async def retrieve_optional_config_map_value(self, configuration_item_name: str) -> Optional[str]:
        return self.config_data.get(configuration_item_name)


def example_simple_usage():
    """Simple usage example - direct instantiation."""
    print("=== Simple Usage Example ===")
    
    # Set up environment
    os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"
    
    # Create config retriever
    config_retriever = MockConfigMapRetriever()
    
    # Create synchronous HashiCorp Vault secret retriever
    vault_secrets: ISecretRetriever = HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap(
        config_retriever=config_retriever,
        logger=logging.getLogger("MyApp.VaultSecrets")
    )
    
    print("✅ HashiCorp Vault secret retriever created successfully")
    
    try:
        # Use it like any other secret retriever (synchronously!)
        secret_value = vault_secrets.retrieve_optional_secret_value("database_password")
        if secret_value:
            print(f"Retrieved secret: {'*' * len(secret_value)}")
        else:
            print("Secret not found (expected in demo)")
    except Exception as e:
        print(f"Expected error (no real vault): {type(e).__name__}")


def example_dependency_injection():
    """Example using dependency injection pattern."""
    print("\n=== Dependency Injection Example ===")
    
    class MyApplication:
        def __init__(self, secret_retriever: ISecretRetriever):
            self.secret_retriever = secret_retriever
        
        def get_database_config(self):
            """Get database configuration from secrets."""
            try:
                host = self.secret_retriever.retrieve_mandatory_secret_value("db_host")
                password = self.secret_retriever.retrieve_mandatory_secret_value("db_password")
                return {"host": host, "password": password}
            except Exception as e:
                print(f"Could not retrieve database config: {e}")
                return None
    
    # Set up
    os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"
    config_retriever = MockConfigMapRetriever()
    
    # Create vault secret retriever
    vault_secrets = HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap(
        config_retriever=config_retriever
    )
    
    # Inject into application
    app = MyApplication(secret_retriever=vault_secrets)
    
    # Use the application
    db_config = app.get_database_config()
    print(f"Database config retrieved: {db_config is not None}")


def example_reusable_factory():
    """Example of creating a reusable factory for your organization."""
    print("\n=== Reusable Factory Example ===")
    
    class MyOrgSecretRetrieverFactory:
        """Organization-specific secret retriever factory."""
        
        @staticmethod
        def create_for_environment(env: str, config_retriever: IConfigMapRetriever) -> ISecretRetriever:
            """Create appropriate secret retriever based on environment."""
            if env.upper() == "LOCAL":
                # Use HashiCorp Vault for local development
                return HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap(
                    config_retriever=config_retriever,
                    logger=logging.getLogger(f"MyOrg.Secrets.{env}")
                )
            elif env.upper() in ["DEV", "TEST", "PROD"]:
                # Use HashiCorp Vault for all environments
                return HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap(
                    config_retriever=config_retriever,
                    logger=logging.getLogger(f"MyOrg.Secrets.{env}")
                )
            else:
                # Fallback to environment variables
                from fx_ai_reusables.secrets import EnvironmentVariableSecretRetriever
                return EnvironmentVariableSecretRetriever()
    
    # Usage
    os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"
    config_retriever = MockConfigMapRetriever()
    
    # Create for different environments
    local_secrets = MyOrgSecretRetrieverFactory.create_for_environment("LOCAL", config_retriever)
    prod_secrets = MyOrgSecretRetrieverFactory.create_for_environment("PROD", config_retriever)
    
    print("✅ Created secret retrievers for multiple environments")


def example_with_dependency_injector():
    """Example using dependency-injector library (like in your composition root)."""
    print("\n=== Dependency Injector Library Example ===")
    
    try:
        from dependency_injector import containers, providers
        from fx_ai_reusables.configmaps import EnvironmentVariablesConfigMapRetriever
        
        class AppContainer(containers.DeclarativeContainer):
            """Application container using HashiCorp Vault for secrets."""
            
            # Configuration
            config = providers.Configuration()
            
            # Logger factory
            @staticmethod
            def create_logger(name: str) -> logging.Logger:
                return logging.getLogger(name)
            
            # ConfigMap retriever
            config_map_retriever = providers.Factory(EnvironmentVariablesConfigMapRetriever)
            
            # Secret retriever using HashiCorp Vault
            secret_retriever: ISecretRetriever = providers.Callable(
                HashiCorpVaultSecretRetrieverFactory.create_sync_from_configmap,
                config_retriever=config_map_retriever,
                logger=providers.Callable(create_logger, name="AppSecrets")
            )
            
            # Your application class
            app = providers.Factory(
                lambda secrets: {"secret_retriever": secrets},
                secrets=secret_retriever
            )
        
        # Set up environment
        os.environ["HASHIVAULT_TOKEN"] = "hvs.AQAAAQAAAAAAA"
        os.environ["HASHIVAULT_URL"] = "https://vault.example.com"
        os.environ["HASHIVAULT_NAMESPACE"] = "my-namespace"
        os.environ["HASHIVAULT_SECRET_PATHS"] = "app/config,app/database"
        
        # Create container and get application
        container = AppContainer()
        app_dict = container.app()
        
        print("✅ Successfully integrated with dependency-injector library")
        print(f"Secret retriever type: {type(app_dict['secret_retriever']).__name__}")
        
    except ImportError:
        print("ℹ️  dependency-injector not available, skipping this example")


def main():
    """Run all examples."""
    print("HashiCorp Vault Secret Retriever - Reusable Examples")
    print("=" * 60)
    
    logging.basicConfig(level=logging.INFO)
    
    example_simple_usage()
    example_dependency_injection()
    example_reusable_factory()
    example_with_dependency_injector()
    
    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("\nKey Benefits:")
    print("- Synchronous interface - works with any DI container")
    print("- Lazy initialization - connects to Vault only when needed")
    print("- Thread-safe - safe for concurrent usage")
    print("- Reusable - can be used in any Python application")
    print("- Drop-in replacement - implements ISecretRetriever interface")


if __name__ == "__main__":
    main()