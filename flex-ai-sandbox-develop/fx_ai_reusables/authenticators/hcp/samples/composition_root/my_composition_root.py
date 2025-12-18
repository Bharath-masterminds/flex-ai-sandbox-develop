from pathlib import Path
from typing import List

from dependency_injector import containers, providers

from fx_ai_reusables.authenticators import IHcpAuthenticator
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.configmaps.concretes.local_file.local_file_config_map_retriever import LocalFileConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.secrets.concretes.env_variable.environment_variable_secret_retriever import EnvironmentVariableSecretRetriever
from fx_ai_reusables.environment_loading.interfaces.azure_llm_config_and_secrets_holder_wrapper_reader_interface import (
    IAzureLlmConfigAndSecretsHolderWrapperReader,
)
from fx_ai_reusables.environment_loading.concretes.azure_llm_config_and_secrets_holder_wrapper_reader import (
    AzureLlmConfigAndSecretsHolderWrapperReader,
)
from fx_ai_reusables.authenticators.hcp.concretes.hcp_authenticator import HcpAuthenticator

BASE_DIR: Path = Path(__file__).resolve().parents[5]
CONFIG_MAP_FILES: List[str] = [
    "hcp.authentication.configmaps.txt",
    "fx_ai_reusables/authenticators/hcp/samples/hcp.authentication.subfolder.optional.configmaps.txt",
]


class MyCompositionRoot(containers.DeclarativeContainer):
    config_map_retriever: providers.Provider[IConfigMapRetriever] = providers.Factory(
        LocalFileConfigMapRetriever,
        properties_file_names=CONFIG_MAP_FILES,
        base_directory=BASE_DIR,
        lazy_load=True,
    )  # type: providers.Provider[IConfigMapRetriever]

    secret_retriever: providers.Provider[ISecretRetriever] = providers.Factory(
        EnvironmentVariableSecretRetriever
    )  # type: providers.Provider[ISecretRetriever]

    azure_llm_config_and_secrets_holder_wrapper_reader: providers.Provider[IAzureLlmConfigAndSecretsHolderWrapperReader] = providers.Factory(
        AzureLlmConfigAndSecretsHolderWrapperReader,
        config_map_retriever=config_map_retriever,
        secrets_retriever=secret_retriever,
    )  # type: providers.Provider[IAzureLlmConfigAndSecretsHolderWrapperReader]

    hcp_authenticator: providers.Provider[HcpAuthenticator] = providers.Factory(
        HcpAuthenticator,
        azure_llm_configmap_and_secrets_holder_wrapper_retriever=azure_llm_config_and_secrets_holder_wrapper_reader,
    )  # type: providers.Provider[HcpAuthenticator]


def get_container() -> MyCompositionRoot:
    container: MyCompositionRoot = MyCompositionRoot()
    return container


def get_hcp_authenticator() -> IHcpAuthenticator:
    container: MyCompositionRoot = get_container()
    authenticator: IHcpAuthenticator = container.hcp_authenticator()
    return authenticator
