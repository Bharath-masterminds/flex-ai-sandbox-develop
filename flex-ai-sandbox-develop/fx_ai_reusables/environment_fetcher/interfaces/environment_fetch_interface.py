from abc import ABC, abstractmethod


class IEnvironmentFetcher(ABC):
    """Interface to load environment variables. """

    @abstractmethod
    def load_environment(self, dotenv_path: str | None = None, override: bool = True, current_working_directory: bool = True):
        pass
