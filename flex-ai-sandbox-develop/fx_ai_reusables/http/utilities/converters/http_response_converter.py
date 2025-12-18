import httpx
from typing import Optional

from fx_ai_reusables.http.exceptions.http_response_serializable_proxy import HttpResponseSerializableProxy


class HttpResponseConverter:
    @staticmethod
    def from_http_response(response: httpx.Response) -> HttpResponseSerializableProxy:
        status_code: int = response.status_code
        uri: str = str(response.request.url) if response.request is not None else ""
        body_text: Optional[str] = response.text if response.content is not None else None
        proxy: HttpResponseSerializableProxy = HttpResponseSerializableProxy(
            status_code=status_code,
            uri=uri,
            detail_codes=None,
            information_fragments=None,
            body=body_text
        )
        return proxy

