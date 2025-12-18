"""
Unit tests for LlmCreatorCacheAsideDecorator
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fx_ai_reusables.llm.creators.cache_aside_decorators.llm_creator_cache_aside_decorator import (
    LlmCreatorCacheAsideDecorator
)
from fx_ai_reusables.environment_loading.constants import DEFAULT_LLM_CACHE_TTL_SECONDS


class TestLlmCreatorCacheAsideDecorator:
    """Test suite for LLM creator cache-aside decorator."""

    @pytest.fixture
    def mock_inner_creator(self):
        """Create a mock inner LLM creator."""
        mock = AsyncMock()
        # Return a new mock LLM each time
        mock.create_llm.side_effect = lambda **kwargs: MagicMock()
        return mock

    @pytest.fixture
    def mock_config_retriever(self):
        """Create a mock config retriever."""
        mock = AsyncMock()
        # By default, return None (use default TTL)
        mock.retrieve_optional_config_map_value.return_value = None
        return mock

    @pytest.fixture
    def decorator(self, mock_inner_creator):
        """Create a decorator instance with mocked inner creator (no config retriever)."""
        return LlmCreatorCacheAsideDecorator(mock_inner_creator)

    @pytest.fixture
    def decorator_with_config(self, mock_inner_creator, mock_config_retriever):
        """Create a decorator instance with config retriever."""
        return LlmCreatorCacheAsideDecorator(mock_inner_creator, mock_config_retriever)

    @pytest.mark.asyncio
    async def test_first_call_creates_llm(self, decorator, mock_inner_creator):
        """Test that first call creates a new LLM."""
        llm = await decorator.create_llm()
        
        assert llm is not None
        mock_inner_creator.create_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_second_call_returns_cached_llm(self, decorator, mock_inner_creator):
        """Test that second call returns cached LLM."""
        llm1 = await decorator.create_llm()
        llm2 = await decorator.create_llm()
        
        # Should be the same object
        assert llm1 is llm2
        # Inner creator should only be called once
        assert mock_inner_creator.create_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_parameter_change_invalidates_cache(self, decorator, mock_inner_creator):
        """Test that changing parameters invalidates the cache."""
        tool1 = MagicMock()
        tool2 = MagicMock()
        
        llm1 = await decorator.create_llm(tools=[tool1])
        llm2 = await decorator.create_llm(tools=[tool2])
        
        # Should be different objects
        assert llm1 is not llm2
        # Inner creator should be called twice
        assert mock_inner_creator.create_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_same_tools_returns_cached_llm(self, decorator, mock_inner_creator):
        """Test that same tools list returns cached LLM."""
        tools = [MagicMock(), MagicMock()]
        
        llm1 = await decorator.create_llm(tools=tools)
        llm2 = await decorator.create_llm(tools=tools)
        
        # Should be the same object
        assert llm1 is llm2
        # Inner creator should only be called once
        assert mock_inner_creator.create_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_ttl_expiration_creates_new_llm(self, decorator, mock_inner_creator, monkeypatch):
        """Test that TTL expiration creates a new LLM."""
        # First call
        llm1 = await decorator.create_llm()
        
        # Mock time to simulate TTL expiration
        original_time = time.time
        monkeypatch.setattr(time, 'time', lambda: original_time() + DEFAULT_LLM_CACHE_TTL_SECONDS + 1)
        
        # Second call after TTL expiration
        llm2 = await decorator.create_llm()
        
        # Should be different objects
        assert llm1 is not llm2
        # Inner creator should be called twice
        assert mock_inner_creator.create_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_flush_cache_invalidates_cache(self, decorator, mock_inner_creator):
        """Test that manual flush invalidates the cache."""
        llm1 = await decorator.create_llm()
        
        # Flush cache
        await decorator.flush_cache_aside()
        
        # Create again
        llm2 = await decorator.create_llm()
        
        # Should be different objects
        assert llm1 is not llm2
        # Inner creator should be called twice
        assert mock_inner_creator.create_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_structured_output_parameter_invalidates_cache(self, decorator, mock_inner_creator):
        """Test that changing structured output parameter invalidates cache."""
        schema = {"type": "object"}
        
        llm1 = await decorator.create_llm(with_structured_output=False)
        llm2 = await decorator.create_llm(with_structured_output=True, output_schema=schema)
        
        # Should be different objects
        assert llm1 is not llm2
        # Inner creator should be called twice
        assert mock_inner_creator.create_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_tool_choice_parameter_invalidates_cache(self, decorator, mock_inner_creator):
        """Test that changing tool_choice parameter invalidates cache."""
        tools = [MagicMock()]
        
        llm1 = await decorator.create_llm(tools=tools, tool_choice="any")
        llm2 = await decorator.create_llm(tools=tools, tool_choice="auto")
        
        # Should be different objects
        assert llm1 is not llm2
        # Inner creator should be called twice
        assert mock_inner_creator.create_llm.call_count == 2

    def test_get_cache_key_with_none_tools(self, decorator):
        """Test cache key generation with None tools."""
        key = decorator._get_cache_key(None, "any", False, None)
        assert key == (None, "any", False, None)

    def test_get_cache_key_with_tools(self, decorator):
        """Test cache key generation with tools."""
        tool1 = MagicMock()
        tool2 = MagicMock()
        tools = [tool1, tool2]
        
        key = decorator._get_cache_key(tools, "any", False, None)
        
        # Should include length and ids
        assert key[0] == (2, (id(tool1), id(tool2)))
        assert key[1] == "any"
        assert key[2] is False
        assert key[3] is None

    @pytest.mark.asyncio
    async def test_get_ttl_with_no_config_retriever(self, decorator):
        """Test that default TTL is used when no config retriever provided."""
        ttl = await decorator._get_ttl_seconds()
        assert ttl == DEFAULT_LLM_CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_get_ttl_from_config(self, decorator_with_config, mock_config_retriever):
        """Test that TTL is loaded from config retriever."""
        # Configure mock to return custom TTL
        mock_config_retriever.retrieve_optional_config_map_value.return_value = "3000"
        
        ttl = await decorator_with_config._get_ttl_seconds()
        assert ttl == 3000

    @pytest.mark.asyncio
    async def test_get_ttl_default_when_config_returns_none(self, decorator_with_config, mock_config_retriever):
        """Test that default TTL is used when config returns None."""
        mock_config_retriever.retrieve_optional_config_map_value.return_value = None
        
        ttl = await decorator_with_config._get_ttl_seconds()
        assert ttl == DEFAULT_LLM_CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_get_ttl_default_on_invalid_config(self, decorator_with_config, mock_config_retriever):
        """Test that default TTL is used when config value is invalid."""
        mock_config_retriever.retrieve_optional_config_map_value.return_value = "not_a_number"
        
        ttl = await decorator_with_config._get_ttl_seconds()
        assert ttl == DEFAULT_LLM_CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_ttl_cached_after_first_load(self, decorator_with_config, mock_config_retriever):
        """Test that TTL is only loaded once and then cached."""
        mock_config_retriever.retrieve_optional_config_map_value.return_value = "2500"
        
        # First call
        ttl1 = await decorator_with_config._get_ttl_seconds()
        # Second call
        ttl2 = await decorator_with_config._get_ttl_seconds()
        
        assert ttl1 == 2500
        assert ttl2 == 2500
        # Config retriever should only be called once
        assert mock_config_retriever.retrieve_optional_config_map_value.call_count == 1
