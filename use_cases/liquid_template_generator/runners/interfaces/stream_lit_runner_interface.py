from abc import abstractmethod, ABC


class IStreamLitRunner(ABC):
    @abstractmethod
    def do_something_with_injected_manager(self) -> str:
        # this method could be named anything.
        pass
