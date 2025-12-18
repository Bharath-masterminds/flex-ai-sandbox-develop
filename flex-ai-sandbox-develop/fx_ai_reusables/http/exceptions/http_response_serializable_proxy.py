from __future__ import annotations

from typing import Iterable, Optional, Tuple, List, Any, overload


class HttpResponseSerializableProxy:
    status_code: int
    uri: str
    body: Optional[str]
    detail_codes: Tuple[int, ...]
    information_fragments: Tuple[str, ...]

    def __init__(
        self,
        status_code: int,
        uri: str,
        detail_codes: Optional[Iterable[int]] = None,
        information_fragments: Optional[Iterable[str]] = None,
        body: Optional[str] = None,
    ) -> None:
        # Normalize collections to immutable tuples
        detail_codes_list: List[int] = list(detail_codes) if detail_codes is not None else []
        information_fragments_list: List[str] = list(information_fragments) if information_fragments is not None else []
        self.status_code = status_code
        self.uri = uri
        self.body = body
        self.detail_codes = tuple(detail_codes_list)
        self.information_fragments = tuple(information_fragments_list)

    # Factory/overload convenience (simulate Java constructor overloading)
    @classmethod
    def from_status_uri(cls, status_code: int, uri: str) -> "HttpResponseSerializableProxy":
        instance: HttpResponseSerializableProxy = cls(status_code, uri)
        return instance

    @classmethod
    def from_status_uri_body(cls, status_code: int, uri: str, body: str) -> "HttpResponseSerializableProxy":
        instance: HttpResponseSerializableProxy = cls(status_code, uri, None, None, body)
        return instance

    @classmethod
    def from_status_uri_detail_codes(
        cls, status_code: int, uri: str, detail_codes: Iterable[int]
    ) -> "HttpResponseSerializableProxy":
        instance: HttpResponseSerializableProxy = cls(status_code, uri, detail_codes, None, None)
        return instance

    @classmethod
    def from_status_uri_detail_codes_info(
        cls,
        status_code: int,
        uri: str,
        detail_codes: Iterable[int],
        information_fragments: Iterable[str],
    ) -> "HttpResponseSerializableProxy":
        instance: HttpResponseSerializableProxy = cls(status_code, uri, detail_codes, information_fragments, None)
        return instance

    # Getters mirroring Java API
    def get_status_code(self) -> int:
        value: int = self.status_code
        return value

    def get_uri(self) -> str:
        value: str = self.uri
        return value

    def get_body(self) -> Optional[str]:
        value: Optional[str] = self.body
        return value

    def get_detail_codes(self) -> Tuple[int, ...]:
        value: Tuple[int, ...] = self.detail_codes
        return value

    def get_information_fragments(self) -> Tuple[str, ...]:
        value: Tuple[str, ...] = self.information_fragments
        return value

    def __repr__(self) -> str:
        repr_str: str = (
            f"{self.__class__.__name__}(status_code={self.status_code}, uri='{self.uri}', "
            f"detail_codes={self.detail_codes}, information_fragments={self.information_fragments}, body={self.body!r})"
        )
        return repr_str

