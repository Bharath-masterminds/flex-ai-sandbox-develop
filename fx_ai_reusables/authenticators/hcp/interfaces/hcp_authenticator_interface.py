from abc import ABC, abstractmethod

class IHcpAuthenticator(ABC):
    """Interface for Hcp Token Retrieval. """


    @abstractmethod
    async def get_hcp_token(self) -> str:
        pass

