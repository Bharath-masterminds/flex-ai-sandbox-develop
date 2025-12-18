from abc import ABC, abstractmethod
from typing import Callable


class IRetryDecoratorFactory(ABC):
    """Interface for producing Tenacity retry decorators.

    Implementations should return a callable (decorator) compatible with Tenacity's @retry
    usage and configured according to the provided parameters.
    """

    @abstractmethod
    def build(self, max_attempts: int, wait_seconds: float, policy_name: str) -> Callable:
        """Build and return a retry decorator.

        Parameters:
            max_attempts: Maximum retry attempts (including the first call attempt).
            wait_seconds: Base wait multiplier / interval (interpretation is up to implementation).
            policy_name: Name of the retry policy for logging/diagnostics.
        Returns:
            A decorator wrapping a callable with retry logic when applied.
        """
        raise NotImplementedError()

