import logging
from typing import Callable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryCallState

from fx_ai_reusables.http.exceptions.http_client_send_exception import HttpClientSendException
from fx_ai_reusables.http.resilienthttpclient.resilient_policies.interfaces.retry_decorator_factory_interface import \
    IRetryDecoratorFactory


class RetryDecoratorFactoryDefault(IRetryDecoratorFactory):
    """Default exponential backoff retry decorator factory using Tenacity."""

    def build(self, max_attempts: int, wait_seconds: float, policy_name: str) -> Callable:
        # simple "build" using attempts and wait_seconds.

        def _before(retry_state: RetryCallState) -> None:
            req: httpx.Request | None = retry_state.args[0] if retry_state.args else None
            url_part: str = f' Uri="{req.url}"' if req else ""
            logging.info(
                f"Retry attempt {retry_state.attempt_number} of {max_attempts} (Retry.Name=\"{policy_name}\"){url_part}"
            )
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=wait_seconds),
            retry=retry_if_exception_type(HttpClientSendException),
            reraise=True,
            before=_before
        )

