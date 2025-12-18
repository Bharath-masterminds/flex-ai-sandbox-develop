import logging
import json
from typing import List, Optional, Any

import httpx

from fx_ai_reusables.http.domain.dictionaries.http_status_codes_bounds_dictionary import HttpStatusCodesBoundsDictionary
from fx_ai_reusables.http.exceptions.http_client_send_exception import HttpClientSendException
from fx_ai_reusables.http.utilities.converters.http_response_converter import HttpResponseConverter
from fx_ai_reusables.http.exceptions.http_response_serializable_proxy import HttpResponseSerializableProxy
from fx_ai_reusables.http.validators.interfaces.http_response_validator_interface import IHttpResponseValidator


class HttpResponseDefaultValidator(IHttpResponseValidator):
    ERROR_MSG_HTTP_STATUS_CODE_OUT_OF_RANGE: str = 'HttpResponse Status Code Out of Bounds. (CurrentValue="{0}", LowerBound="{1}", UpperBound="{2}")'
    LOG_MSG_HTTP_STATUS_CODE_IN_RANGE: str = 'HttpResponse Status is in bounds. (CurrentValue="{0}", LowerBound="{1}", UpperBound="{2}")'
    _logger: logging.Logger = logging.getLogger(__name__)

    def validate_http_response(self, response: httpx.Response) -> None:
        if response is None:
            return
        status_code: int = response.status_code
        lower_bound: int = HttpStatusCodesBoundsDictionary.DEFAULT_HTTP_STATUS_SUCCESSFUL_LOWER_BOUND
        upper_bound: int = HttpStatusCodesBoundsDictionary.DEFAULT_HTTP_STATUS_SUCCESSFUL_UPPER_BOUND
        if lower_bound <= status_code <= upper_bound:
            self._logger.debug(self.LOG_MSG_HTTP_STATUS_CODE_IN_RANGE.format(status_code, lower_bound, upper_bound))
        else:
            error_message: str = self.ERROR_MSG_HTTP_STATUS_CODE_OUT_OF_RANGE.format(status_code, lower_bound, upper_bound)
            index_out_of_bounds_exception: IndexError = IndexError(error_message)
            self._logger.error(error_message)
            # Build full proxy (enriched)
            raw_body_text: Optional[str] = response.text if response.content is not None else None
            detail_codes: List[int] = []
            information_fragments: List[str] = []
            # Headers-based extraction
            detail_codes_header: Optional[str] = response.headers.get("X-Detail-Codes")
            if detail_codes_header:
                for part in detail_codes_header.split(","):
                    part_stripped: str = part.strip()
                    if part_stripped.isdigit():
                        detail_codes.append(int(part_stripped))
            info_frags_header: Optional[str] = response.headers.get("X-Information-Fragments")
            if info_frags_header:
                for frag in info_frags_header.split(","):
                    information_fragments.append(frag.strip())
            # JSON body extraction (if applicable)
            json_obj: Optional[Any] = None
            if raw_body_text:
                try:
                    json_obj = json.loads(raw_body_text)
                except Exception:
                    json_obj = None
            if isinstance(json_obj, dict):
                json_detail_codes: Any = json_obj.get("detailCodes")
                if isinstance(json_detail_codes, list):
                    for dc in json_detail_codes:
                        if isinstance(dc, int):
                            detail_codes.append(dc)
                json_information_fragments: Any = json_obj.get("informationFragments")
                if isinstance(json_information_fragments, list):
                    for inf in json_information_fragments:
                        if isinstance(inf, str):
                            information_fragments.append(inf)
            response_proxy: HttpResponseSerializableProxy = HttpResponseSerializableProxy(
                status_code=status_code,
                uri=str(response.request.url) if response.request is not None else "",
                detail_codes=detail_codes if detail_codes else None,
                information_fragments=information_fragments if information_fragments else None,
                body=raw_body_text
            )
            raise HttpClientSendException(error_message, response_proxy) from index_out_of_bounds_exception
