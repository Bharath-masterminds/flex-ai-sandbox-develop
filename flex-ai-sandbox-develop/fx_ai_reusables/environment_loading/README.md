
The "top level" DTO... 
reusables/environment_loading/domain/AzureLlmConfigAndSecretsHolderWrapper.py
has the configuration values as inner classes.
  Note that ".EmbeddingModelConfig" is "optional" hydrated.

.....

An interface to read the above object is:
  reusables/environment_loading/interfaces/IAzureLlmConfigAndSecretsHolderWrapperReader.py

and the concrete implementation:
reusables/environment_loading/concretes/AzureLlmConfigAndSecretsHolderWrapper.py 
is the core functionality.

.....

reusables/environment_loading/cache_aside_decorators/AzureLlmConfigAndSecretsHolderWrapperCacheAsideDecorator.py
is a cache aside decorator for IAzureLlmConfigAndSecretsHolderWrapperReader.

.....

The concrete:
reusables/environment_loading/concretes/AzureLlmConfigAndSecretsHolderWrapper.py 
uses:
reusables/configmaps/interfaces/IConfigMapRetriever.py
and
reusables/secrets/interfaces/ISecretRetriever.py

.....

There are currently 2 simple implementations of these interfaces:
  IConfigMapRetriever : 
      reusables/configmaps/concretes/EnvironmentConfigMapRetriever.py
and
    ISecretRetriever : 
      reusables/secrets/concretes/EnvironmentSecretRetriever.py

Obviously, these are environment variable based implementations.

But they are behind interfaces, so coding to ISecretRetriever and IConfigMapRetriever allows better implementations,
especially in regards to secrets.  (A kubernetes secrets based implementation is a good example, and/or HashiCorp Vault, or Azure Key Vault, etc.)


.....

A sample is provided in:
reusables/environment_loading/Samples/AzureLlmConfigAndSecretsHolderWrapper_Sample.py

Note, the sample will not work until you create a .env file, that should never be checked in.
