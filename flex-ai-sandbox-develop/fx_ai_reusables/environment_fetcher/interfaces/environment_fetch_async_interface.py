from abc import ABC, abstractmethod


class IEnvironmentFetcherAsync(ABC):
    """Interface to load environment variables. """

    @abstractmethod
    async def load_environment(self, dotenv_path: str | None = None, override: bool = True, current_working_directory: bool = True):
        pass
