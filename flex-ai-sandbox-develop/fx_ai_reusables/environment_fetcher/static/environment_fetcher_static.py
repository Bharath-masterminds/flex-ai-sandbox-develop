import os
from dotenv import load_dotenv, find_dotenv
import logging

class StaticEnvironmentFetcher:
    @staticmethod
    def load_environment(dotenv_path: str | None = None, override: bool = True):
        """Load environment variables from a .env file.

        By default this will search for a .env file starting from the current working
        directory and walk up parent directories. override=True ensures variables in
        the file are written into os.environ (useful for tests).
        """
        path = dotenv_path or find_dotenv(usecwd=True)
        if not path:
            # No .env found; nothing to load
            logging.info("No .env file found to load")
            return

        loaded = load_dotenv(path, override=override)
        if loaded:
            logging.debug("Environment variables loaded from .env file")
        else:
            logging.info("Failed to load .env file or no variables were set")

