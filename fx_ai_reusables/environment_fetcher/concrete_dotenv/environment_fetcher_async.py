import logging

from dotenv import load_dotenv, find_dotenv

from fx_ai_reusables.environment_fetcher.interfaces.environment_fetch_async_interface import IEnvironmentFetcherAsync


class EnvironmentFetcherAsync (IEnvironmentFetcherAsync):

    async def load_environment(self, dotenv_path: str | None = None, override: bool = True, current_working_directory: bool = True):
        """Load environment variables from a .env file.

        By default this will search for a .env file starting from the current working
        directory and walk up parent directories. override=True ensures variables in
        the file are written into os.environ (useful for tests).
        """

        logging.debug("EnvironmentFetcherAsync.load_environment called.  Looking for .env file.")

        path = dotenv_path or find_dotenv(usecwd=current_working_directory)
        if not path:
            # No .env found; nothing to load
            logging.info("No .env file found to load")
            return

        loaded = load_dotenv(path, override=override)
        if loaded:
            logging.debug("Environment variables loaded from .env file")
        else:
            logging.info("Failed to load .env file or no variables were set")




