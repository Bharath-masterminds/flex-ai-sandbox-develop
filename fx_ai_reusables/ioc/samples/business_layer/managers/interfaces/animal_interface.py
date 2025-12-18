from abc import abstractmethod, ABC


class IAnimalManager(ABC):
    @abstractmethod
    def speak(self) -> str:
        pass
