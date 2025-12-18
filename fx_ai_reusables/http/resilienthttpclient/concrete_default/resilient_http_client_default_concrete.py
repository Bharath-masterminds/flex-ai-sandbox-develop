import logging
from logging import error, info
from threading import Lock
from typing import Dict, Callable

import httpx

from fx_ai_reusables.http.exceptions.http_client_send_exception import HttpClientSendException
from fx_ai_reusables.http.resilienthttpclient.interfaces.resilient_http_client_interface import IResilientHttpClient
from fx_ai_reusables.http.resilienthttpclient.resilient_policies.interfaces.retry_decorator_factory_interface import IRetryDecoratorFactory
from fx_ai_reusables.http.validators.interfaces.http_response_validator_interface import IHttpResponseValidator


class ResilientHttpClient(IResilientHttpClient):
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_WAIT_DURATION_SECONDS = 0.25
    DEFAULT_RETRY_POLICY_NAME = "DefaultRetryPolicyName"

    _default_retry_lock = Lock()
    _default_retry_decorator = None

    def __init__(self,
                 http_client: httpx.Client,
                 http_response_validator: IHttpResponseValidator,
                 retry_factory: IRetryDecoratorFactory,
                 named_retry_policies: Dict[str, Callable]):
        """Initialize the resilient client (all dependencies required).

        Parameters:
            http_client: An externally managed httpx.Client instance.
            http_response_validator: Implementation of IHttpResponseValidator.
            retry_factory: Implementation of IRetryDecoratorFactory used to build retry decorators.
            named_retry_policies: Mapping of name->retry decorator injected at construction (immutable afterwards).

        Notes:
            - No opinionated default concretes are created internally.
            - All parameters must be provided (non-None) or a ValueError is raised.
            - Provide an empty dict if you do not wish to pre-register any policies.
        """
        if http_client is None:
            raise ValueError("http_client is required and cannot be None")
        if http_response_validator is None:
            raise ValueError("http_response_validator is required and cannot be None")
        if retry_factory is None:
            raise ValueError("retry_factory is required and cannot be None")
        if named_retry_policies is None:
            raise ValueError("named_retry_policies is required (use an empty dict if none)")

        self.http_client = http_client
        self.http_response_validator = http_response_validator
        self._retry_factory: IRetryDecoratorFactory = retry_factory

        bad_items = [k for k, v in named_retry_policies.items() if not isinstance(k, str) or not callable(v)]
        if bad_items:
            raise TypeError(
                f"All named_retry_policies keys must be str and values callable. Invalid entries: {bad_items}"
            )
        # store a shallow copy to prevent external mutation
        self.named_retry_policies: Dict[str, Callable] = dict(named_retry_policies)

    def _build_retry_decorator(self, max_attempts: int, wait_seconds: float, policy_name: str) -> Callable:
        return self._retry_factory.build(max_attempts, wait_seconds, policy_name)

    def execute_raw_http_request(self, retry_policy_name: str, http_request: httpx.Request) -> httpx.Response:
        logging.debug("ENTERING_EXECUTE_RAW_HTTP_REQUEST")
        response: httpx.Response = self.internal_execute_http_request(retry_policy_name, http_request)
        self.http_response_validator.validate_http_response(response)
        return response

    def execute_no_validate_raw_http_request(self, retry_policy_name: str, http_request: httpx.Request) -> httpx.Response:
        logging.debug("ENTERING_EXECUTE_RAW_HTTP_REQUEST")
        retry_decorator: Callable = self._get_retry_decorator(retry_policy_name)

        @retry_decorator
        def send(req: httpx.Request):
            info(f"HttpClient.Send. Uri=\"{req.url}\"")
            return self.http_client.send(req)

        try:
            return send(http_request)
        except HttpClientSendException as e:
            self.generate_and_log_policy_name_info(retry_policy_name)
            raise e
        except Exception as t:
            error_msg = self.generate_and_log_policy_name_info(retry_policy_name)
            raise HttpClientSendException.from_message(error_msg) from t

    def execute_http_request(self, retry_policy_name: str, http_request: httpx.Request) -> httpx.Response:
        logging.debug("ENTERING_EXECUTE_HTTP_REQUEST")
        response: httpx.Response = self.execute_raw_http_request(retry_policy_name, http_request)
        return response

    def _get_retry_decorator(self, name: str):
        if name in self.named_retry_policies:
            logging.debug(f"Named retry policy found: {name}")
            return self.named_retry_policies[name]
        logging.debug(f"Named retry policy not found: {name}, using default")
        return self._get_default_retry_decorator()

    def _get_default_retry_decorator(self):
        with self._default_retry_lock:
            if self._default_retry_decorator is None:
                self._default_retry_decorator = self._build_retry_decorator(
                    self.DEFAULT_MAX_ATTEMPTS,
                    self.DEFAULT_WAIT_DURATION_SECONDS,
                    self.DEFAULT_RETRY_POLICY_NAME
                )
            return self._default_retry_decorator

    def internal_execute_http_request(self, retry_policy_name: str, http_request: httpx.Request):
        retry_decorator: Callable = self._get_retry_decorator(retry_policy_name)

        @retry_decorator
        def send_wrapper(req: httpx.Request):
            info(f"HttpClient.Send. Uri=\"{req.url}\"")
            response: httpx.Response = self.http_client.send(req)
            self.http_response_validator.validate_http_response(response)
            return response

        try:
            return send_wrapper(http_request)
        except HttpClientSendException as e:
            self.generate_and_log_policy_name_info(retry_policy_name)
            raise e
        except Exception as t:
            error_msg = self.generate_and_log_policy_name_info(retry_policy_name)
            raise HttpClientSendException.from_message(error_msg) from t

    def generate_and_log_policy_name_info(self, retry_policy_name: str) -> str:
        found_named_policy: bool = retry_policy_name in self.named_retry_policies
        error_msg: str = (
            f"(Retry.Name=\"{retry_policy_name}\", "
            f"PolicyExistsInNamedRetryPolicies=\"{found_named_policy}\")"
        )
        error(error_msg)
        return error_msg
