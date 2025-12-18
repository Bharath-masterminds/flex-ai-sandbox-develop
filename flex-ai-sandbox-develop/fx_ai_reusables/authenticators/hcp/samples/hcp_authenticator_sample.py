import asyncio
import logging

from fx_ai_reusables.authenticators import IHcpAuthenticator
from fx_ai_reusables.authenticators.hcp.samples.composition_root.my_composition_root import (
    get_hcp_authenticator,
    HcpAuthenticator,
)
from fx_ai_reusables.environment_fetcher import StaticEnvironmentFetcher

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    env_seed: None = None
    override_env: bool = True
    StaticEnvironmentFetcher.load_environment(env_seed, override=override_env)

    authenticator: IHcpAuthenticator = get_hcp_authenticator()

    token: str
    try:
        token = await authenticator.get_hcp_token()
    except Exception as ex:
        error: Exception = ex
        logging.error("Failed to retrieve HCP token (expected in sample without real creds): %s", error)
        token = "SOMETHING_FAILED_CHECK_YOUR_CONFIGMAPS_AND_SECRETS"

    logging.info("Retrieved (or fallback) HCP token: %s", token)


if __name__ == "__main__":
    asyncio.run(main())
