from typing import Optional
from .http_response_serializable_proxy import HttpResponseSerializableProxy

# Custom exceptions
class HttpClientSendException(Exception):
    http_response_serializable_proxy: Optional[HttpResponseSerializableProxy]

    def __init__(
        self,
        error_message: str,
        http_response_serializable_proxy: Optional[HttpResponseSerializableProxy] = None
    ) -> None:
        super().__init__(error_message)
        self.http_response_serializable_proxy = http_response_serializable_proxy

    @classmethod
    def from_message(cls, error_message: str) -> "HttpClientSendException":
        instance: HttpClientSendException = cls(error_message, None)
        return instance

    @classmethod
    def from_message_and_proxy(cls, error_message: str, http_response_serializable_proxy: HttpResponseSerializableProxy) -> "HttpClientSendException":
        instance: HttpClientSendException = cls(error_message, http_response_serializable_proxy)
        return instance

    def get_http_response_serializable_proxy(self) -> Optional[HttpResponseSerializableProxy]:
        value: Optional[HttpResponseSerializableProxy] = self.http_response_serializable_proxy
        return value

    def __repr__(self) -> str:
        repr_str: str = (
            f"{self.__class__.__name__}(message={self.args[0]!r}, "
            f"http_response_serializable_proxy={self.http_response_serializable_proxy!r})"
        )
        return repr_str
