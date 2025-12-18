"""
Async helper utilities for bridging async and sync code.
"""

import asyncio
import concurrent.futures
from typing import Any, Awaitable, Callable, TypeVar


T = TypeVar('T')


def run_async_in_sync_context(async_func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    """
    Run an async function in a synchronous context, handling event loop conflicts.
    
    This function is designed to solve the common problem of calling async functions
    from synchronous code, especially in environments like Streamlit that already
    have a running event loop.
    
    Args:
        async_func: The async function to execute
        *args: Positional arguments to pass to the async function
        **kwargs: Keyword arguments to pass to the async function
        
    Returns:
        The result of the async function
        
    Raises:
        Any exception raised by the async function
        
    Examples:
        >>> async def fetch_data():
        ...     return "data"
        >>> 
        >>> # In sync context (like Streamlit)
        >>> result = run_async_in_sync_context(fetch_data)
        >>> print(result)  # "data"
        >>>
        >>> # With arguments
        >>> async def fetch_user(user_id, timeout=10):
        ...     return f"user_{user_id}"
        >>> 
        >>> result = run_async_in_sync_context(fetch_user, 123, timeout=5)
        >>> print(result)  # "user_123"
    """
    try:
        # Check if we're in a running event loop (like Streamlit, Jupyter, etc.)
        loop = asyncio.get_running_loop()
        
        # We're in an event loop, so we need to use threading to avoid conflicts
        def run_in_thread():
            """Create a new event loop in a separate thread."""
            return asyncio.run(async_func(*args, **kwargs))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()
            
    except RuntimeError:
        # No event loop running, safe to use asyncio.run directly
        return asyncio.run(async_func(*args, **kwargs))