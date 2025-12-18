from dataclasses import dataclass

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever


OPINIONATED_DEFAULT_CLIENT_CREDENTIALS_GRANT_TYPE = "client_credentials"


@dataclass(frozen=True)
class HcpConfig:
    HCP_TOKEN_URL: str
    HCP_CLIENT_ID: str
    HCP_CLIENT_SECRET: str
    HCP_TOKEN_SCOPE: str
    HCP_GRANT_TYPE: str

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "HcpConfig":
        return HcpConfig(
            HCP_TOKEN_URL=await config_map_retriever.retrieve_mandatory_config_map_value("HCP_TOKEN_URL"),

            # new code, ESRO wants oauth_client_ids to be treated as secret
            HCP_CLIENT_ID=await secrets_retriever.retrieve_mandatory_secret_value("HCP_CLIENT_ID"),
            HCP_CLIENT_SECRET=await secrets_retriever.retrieve_mandatory_secret_value("HCP_CLIENT_SECRET"),

            HCP_TOKEN_SCOPE=await config_map_retriever.retrieve_mandatory_config_map_value("HCP_TOKEN_SCOPE"),
            HCP_GRANT_TYPE=await config_map_retriever.retrieve_optional_config_map_value("HCP_GRANT_TYPE") or OPINIONATED_DEFAULT_CLIENT_CREDENTIALS_GRANT_TYPE,
        )
