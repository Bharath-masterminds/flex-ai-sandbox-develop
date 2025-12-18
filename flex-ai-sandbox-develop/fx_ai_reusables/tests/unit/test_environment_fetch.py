import os

import pytest

from fx_ai_reusables.environment_fetcher.concrete_dotenv.environment_fetcher_async import EnvironmentFetcherAsync
from fx_ai_reusables.environment_fetcher.interfaces import IEnvironmentFetcherAsync


@pytest.mark.asyncio
async def test_load_environment_from_dotenv(tmp_path, monkeypatch):
    # create a temporary .env file and change cwd so load_dotenv picks it up
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_ENV_FETCH_VAR=hello_world\n")

    monkeypatch.chdir(tmp_path)

    # ensure the variable is not present before loading
    os.environ.pop("TEST_ENV_FETCH_VAR", None)

    # call loader
    env_file_env_fetcher: IEnvironmentFetcherAsync = EnvironmentFetcherAsync()
    await env_file_env_fetcher.load_environment()

    assert os.getenv("TEST_ENV_FETCH_VAR") == "hello_world"
