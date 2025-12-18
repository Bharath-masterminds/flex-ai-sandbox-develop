from abc import ABC, abstractmethod

import httpx  # or use `requests` if preferred


class IResilientHttpClient(ABC):

    @abstractmethod
    def execute_http_request(self, retry_policy_instance_name: str, http_request: httpx.Request) -> str:
        pass

    @abstractmethod
    def execute_raw_http_request(self, retry_policy_instance_name: str, http_request: httpx.Request) -> httpx.Response:
        pass

    @abstractmethod
    def execute_no_validate_raw_http_request(self, retry_policy_instance_name: str, http_request: httpx.Request) -> httpx.Response:
        pass

