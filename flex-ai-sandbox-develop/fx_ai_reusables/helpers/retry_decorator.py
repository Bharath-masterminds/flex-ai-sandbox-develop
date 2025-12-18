"""
Retry decorator utility for handling transient failures in external API calls.

This module provides a configurable retry mechanism with exponential backoff
for API calls that may experience temporary failures.
"""

import time
from functools import wraps
from typing import Callable, Any, Optional, Type, Tuple, TypeVar

T = TypeVar('T')

def retry_api_call(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    verbose: bool = True
):
    """
    Decorator to retry API calls with exponential backoff.
    
    This decorator automatically retries a function call if it raises an exception,
    with increasing delays between attempts using exponential backoff.
    
    :param max_retries: Maximum number of retry attempts (default: 3)
    :param delay: Initial delay between retries in seconds (default: 1.0)
    :param backoff: Multiplier for delay after each retry (default: 2.0)
    :param exceptions: Tuple of exception types to catch and retry. If None, catches all exceptions
    :param verbose: Whether to print retry messages (default: True)
    
    :return: Decorated function with retry logic
    
    Example:
        @retry_api_call(max_retries=3, delay=1.0, backoff=2.0)
        def fetch_data_from_api():
            return requests.get('https://api.example.com/data')
    
    Retry Timeline Example:
        - Attempt 1: Immediate (fails)
        - Attempt 2: Wait 1 second, retry (fails)
        - Attempt 3: Wait 2 seconds, retry (fails)
        - Result: Raise exception with detailed error message
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if we should retry this exception
                    if exceptions is not None and not isinstance(e, exceptions):
                        # This exception type should not be retried
                        raise
                    
                    last_exception = e
                    
                    if attempt < max_retries:
                        if verbose:
                            print(f"API call '{func.__name__}' failed (attempt {attempt}/{max_retries}): {str(e)}")
                            print(f"Retrying in {current_delay:.1f} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        if verbose:
                            print(f"API call '{func.__name__}' failed after {max_retries} attempts: {str(e)}")
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator

