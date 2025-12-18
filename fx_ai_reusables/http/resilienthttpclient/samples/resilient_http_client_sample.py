import asyncio
import logging
from typing import Dict, Callable

import httpx

from fx_ai_reusables.http.domain.enums.http_method_enum import HttpMethodEnum
from fx_ai_reusables.http.exceptions.http_client_send_exception import HttpClientSendException
from fx_ai_reusables.http.resilienthttpclient.concrete_default.resilient_http_client_default_concrete import \
    ResilientHttpClient
from fx_ai_reusables.http.resilienthttpclient.resilient_policies.concretes.retry_decorator_factory_default import \
    RetryDecoratorFactoryDefault
from fx_ai_reusables.http.resilienthttpclient.interfaces.resilient_http_client_interface import IResilientHttpClient
from fx_ai_reusables.http.resilienthttpclient.resilient_policies.interfaces.retry_decorator_factory_interface import \
    IRetryDecoratorFactory
from fx_ai_reusables.http.validators.http_response_default_validator import HttpResponseDefaultValidator
from fx_ai_reusables.http.validators.interfaces.http_response_validator_interface import IHttpResponseValidator


def show_outer_to_inner_exception_chain(outer: Exception) -> None:
    logging.error("Top caught: %s", outer)
    if outer.__cause__ is not None:
        logging.error("Cause (explicit): %s", outer.__cause__)
    if outer.__context__ is not None:
        logging.error("Context (implicit): %s", outer.__context__)
    idx: int = 0
    current: Exception | None = outer
    logging.error("\nChain (if any):")
    while current is not None:
        idx += 1
        logging.error("Exception[%d] START", idx)
        logging.error(
            "Exception[%d] type=%s message=%s args=%s",
            idx,
            type(current).__name__,
            current,
            current.args,
        )
        logging.error("- %s: %s", current.__class__.__name__, current)
        current = current.__cause__
        logging.error("Exception[%d] END", idx)


def show_http_client_send_exception(exc: HttpClientSendException) -> None:
    logging.error("HttpClientSendException (swallowed) START")
    show_outer_to_inner_exception_chain(exc)
    logging.error("HttpClientSendException (swallowed) END")


async def main() -> None:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

    # Dependency instances (explicit types)
    http_response_validator: IHttpResponseValidator = HttpResponseDefaultValidator()
    retry_factory: IRetryDecoratorFactory = RetryDecoratorFactoryDefault()
    empty_named_retry_policies: Dict[str, Callable] = {}
    http_client_1500_ms_timeout: httpx.Client = httpx.Client(timeout=1.5)

    resilient_client_no_explicit_retry_policies: IResilientHttpClient = ResilientHttpClient(
        http_client_1500_ms_timeout,
        http_response_validator,
        retry_factory,
        empty_named_retry_policies
    )

    # AAA block
    logging.info("AAA:++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    request_get: httpx.Request = httpx.Request(HttpMethodEnum.GET, "http://localhost:8798/get")
    current_response_string: str = resilient_client_no_explicit_retry_policies.execute_http_request(
        "does_not_exist_in_named_retry_policies_retry_policy_instance_name_001", request_get)
    logging.info(current_response_string)

    # BBB block
    logging.info("BBB:++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    request_delay1: httpx.Request = httpx.Request(HttpMethodEnum.GET, "http://localhost:8798/delay/1")
    current_response_string: str = resilient_client_no_explicit_retry_policies.execute_http_request(
        "does_not_exist_in_named_retry_policies_retry_policy_instance_name_002", request_delay1)
    logging.info(current_response_string)

    # CCC block
    logging.info("CCC:++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    try:
        request_delay2: httpx.Request = httpx.Request(HttpMethodEnum.GET, "http://localhost:8798/delay/2")
        current_response_string: str = resilient_client_no_explicit_retry_policies.execute_http_request(
            "does_not_exist_in_named_retry_policies_retry_policy_instance_name_003", request_delay2)
        logging.info(current_response_string)
    except HttpClientSendException as hcse:
        show_http_client_send_exception(hcse)

    # DDD block
    logging.info("DDD:++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    try:
        request_status500: httpx.Request = httpx.Request(HttpMethodEnum.GET, "http://localhost:8798/status/500")
        response_status500: str = resilient_client_no_explicit_retry_policies.execute_http_request(
            "does_not_exist_in_named_retry_policies_retry_policy_instance_name_004", request_status500)
        logging.info("Should not reach here due to server error handling.")
        logging.info(response_status500)
    except HttpClientSendException as hcse:
        show_http_client_send_exception(hcse)

    # EEE block
    logging.info("EEE:++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    factory_for_fast_policy: IRetryDecoratorFactory = RetryDecoratorFactoryDefault()
    fast_retry_policy_instance_name_005: str = "fast_retry_policy_instance_name_005"
    explicit_defined_retry_injected_policies: Dict[str, Callable] = {
        fast_retry_policy_instance_name_005: factory_for_fast_policy.build(10, 0.001, fast_retry_policy_instance_name_005)
    }
    resilient_client_injected: IResilientHttpClient = ResilientHttpClient(
        http_client_1500_ms_timeout,
        http_response_validator,
        retry_factory,
        named_retry_policies=explicit_defined_retry_injected_policies
    )

    try:
        request_status444: httpx.Request = httpx.Request(HttpMethodEnum.GET, "http://localhost:8798/status/444")
        current_response_string: str = resilient_client_injected.execute_http_request(
            fast_retry_policy_instance_name_005,
            request_status444
        )
        logging.info("Fast retry response body=%s", current_response_string)
    except HttpClientSendException as hcse:
        show_http_client_send_exception(hcse)

    logging.info("SAMPLE_COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
