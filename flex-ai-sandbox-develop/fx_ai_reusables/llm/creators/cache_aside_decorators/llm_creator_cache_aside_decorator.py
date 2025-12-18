import time
import logging
from typing import List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.environment_loading.constants import (
    ENV_LLM_CACHE_TTL_SECONDS,
    DEFAULT_LLM_CACHE_TTL_SECONDS
)
from fx_ai_reusables.llm.creators.interfaces.llm_creator_interface import ILlmCreator


class LlmCreatorCacheAsideDecorator(ILlmCreator):
    """Cache Aside Decorator for LLM Creator.

    Caches the LLM object based on a time-to-live (TTL) mechanism.
    HCP tokens expire at 3599 seconds, so we use a configurable TTL
    (default 3500 seconds) to provide a safety buffer and prevent token expiration errors.

    The TTL can be configured via:
    - Environment variable: LLM_CACHE_TTL_SECONDS
    - Default: 3500 seconds if not configured

    The cache is invalidated when:
    1. TTL expires (configurable seconds since creation)
    2. Parameters change (tools, tool_choice, with_structured_output, output_schema)
    3. Manual flush is called

    The decorator tracks:
    - The cached LLM instance
    - Creation timestamp (for TTL calculation)
    - Last parameters used (for invalidation on parameter change)
    """

    def __init__(
        self,
        inner_item_to_decorate: ILlmCreator,
        config_map_retriever: Optional[IConfigMapRetriever] = None
    ):
        """Initialize the cache-aside decorator.

        Args:
            inner_item_to_decorate: The underlying ILlmCreator implementation to decorate
            config_map_retriever: Optional configmap retriever for fetching TTL configuration.
                                 If None, uses default TTL.
        """
        self._inner_item_to_decorate = inner_item_to_decorate
        self._config_map_retriever = config_map_retriever
        self._cached_llm: Optional[BaseChatModel] = None
        self._creation_time: Optional[float] = None
        self._cached_params: Optional[tuple] = None
        self._ttl_seconds: Optional[int] = None  # Will be loaded lazily

    async def _get_ttl_seconds(self) -> int:
        """Get the TTL from configmap or use default.

        Returns:
            TTL in seconds for the LLM cache
        """
        if self._ttl_seconds is None:
            # Try to get from configmap first
            if self._config_map_retriever is not None:
                try:
                    ttl_str = await self._config_map_retriever.retrieve_optional_config_map_value(
                        ENV_LLM_CACHE_TTL_SECONDS
                    )
                    if ttl_str is not None:
                        self._ttl_seconds = int(ttl_str)
                        logging.info(f"LLM cache TTL loaded from config: {self._ttl_seconds} seconds")
                    else:
                        self._ttl_seconds = DEFAULT_LLM_CACHE_TTL_SECONDS
                        logging.info(f"LLM cache TTL using default: {self._ttl_seconds} seconds")
                except (ValueError, KeyError) as e:
                    logging.warning(f"Failed to load TTL from config: {e}. Using default: {DEFAULT_LLM_CACHE_TTL_SECONDS}")
                    self._ttl_seconds = DEFAULT_LLM_CACHE_TTL_SECONDS
            else:
                # No config retriever provided, use default
                self._ttl_seconds = DEFAULT_LLM_CACHE_TTL_SECONDS
                logging.info(f"LLM cache TTL using default (no config retriever): {self._ttl_seconds} seconds")

        return self._ttl_seconds

    async def flush_cache_aside(self):
        """Manually flush the cache.

        Useful for testing or when you need to force recreation of the LLM.
        """
        logging.info("LlmCreatorCacheAsideDecorator: flush_cache_aside (clearing cache)")
        self._cached_llm = None
        self._creation_time = None
        self._cached_params = None

    def _get_cache_key(
        self,
        tools: Optional[List],
        tool_choice: str,
        with_structured_output: bool,
        output_schema
    ) -> tuple:
        """Generate a cache key from the parameters.

        For tools, we use identity (id) and length to detect changes.
        This is a simple heuristic that works for MVP - tools lists are
        typically stable within a session.

        Args:
            tools: List of tools to bind to the LLM
            tool_choice: Strategy for tool selection
            with_structured_output: Whether structured output is enabled
            output_schema: Schema for structured output

        Returns:
            Tuple representing the cache key
        """
        # For tools, use (length, tuple of object ids) as a proxy for equality
        # This avoids deep comparison but detects most changes
        tools_key = None
        if tools is not None:
            tools_key = (len(tools), tuple(id(tool) for tool in tools))

        return (tools_key, tool_choice, with_structured_output, id(output_schema) if output_schema else None)

    async def create_llm(
        self,
        config: Optional[RunnableConfig] = None,
        tools: Optional[List] = None,
        tool_choice: str = "any",
        with_structured_output: bool = False,
        output_schema=None,
    ) -> BaseChatModel:
        """Create or return cached LLM instance.

        Args:
            config: Optional configuration for the runnable
            tools: Optional list of tools to bind to the LLM
            tool_choice: Strategy for tool selection
            with_structured_output: Whether to enable structured output
            output_schema: Schema for structured output

        Returns:
            Configured LLM instance (cached or newly created)
        """
        current_time = time.time()
        current_params = self._get_cache_key(tools, tool_choice, with_structured_output, output_schema)
        ttl_seconds = await self._get_ttl_seconds()

        # Check if cache is valid
        cache_valid = False
        if self._cached_llm is not None and self._creation_time is not None:
            age_seconds = current_time - self._creation_time
            params_match = self._cached_params == current_params
            ttl_valid = age_seconds < ttl_seconds

            if not ttl_valid:
                logging.info(f"LLM cache expired (age: {age_seconds:.0f}s, TTL: {ttl_seconds}s)")
            elif not params_match:
                logging.info("LLM cache invalidated due to parameter change")
            else:
                cache_valid = True
                logging.info(f"Returning cached LLM (age: {age_seconds:.0f}s, remaining: {ttl_seconds - age_seconds:.0f}s)")

        if cache_valid:
            return self._cached_llm

        # Cache miss, expired, or invalidated - create new LLM
        logging.info("Creating new LLM instance with fresh HCP token")
        self._cached_llm = await self._inner_item_to_decorate.create_llm(
            config=config,
            tools=tools,
            tool_choice=tool_choice,
            with_structured_output=with_structured_output,
            output_schema=output_schema
        )
        self._creation_time = current_time
        self._cached_params = current_params

        return self._cached_llm
