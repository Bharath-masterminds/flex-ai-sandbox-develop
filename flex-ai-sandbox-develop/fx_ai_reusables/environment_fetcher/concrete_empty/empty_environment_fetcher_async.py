import logging

from fx_ai_reusables.environment_fetcher.interfaces.environment_fetch_async_interface import IEnvironmentFetcherAsync

class EmptyEnvironmentFetcherAsync (IEnvironmentFetcherAsync):

    async def load_environment(self, dotenv_path: str | None = None, override: bool = True, current_working_directory: bool = True):
        """ an "empty" implementation.
        this will be used to satisfy IoC/DI needs when environment variables do NOT come from .env file.
        """
        logging.info("EmptyEnvironmentFetcherAsync.load_environment called - no action taken.")
