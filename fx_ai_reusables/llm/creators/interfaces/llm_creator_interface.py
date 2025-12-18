from abc import ABC, abstractmethod
from typing import Optional, List

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig


class ILlmCreator(ABC):
    """Interface defining the contract for LLM creation services."""

    @abstractmethod
    async def create_llm(
            self,
            config: Optional[RunnableConfig] = None,
            tools: Optional[List] = None,
            tool_choice: str = "any",
            with_structured_output: bool = False,
            output_schema=None,
    ) -> BaseChatModel:
        """Initialize an LLM with HCP token authentication.

        Args:
            hcp_token: authorization token for HCP
            config: Optional configuration for the runnable
            tools: Optional list of tools to bind to the LLM
            tool_choice: Strategy for tool selection
            with_structured_output: Whether to enable structured output
            output_schema: Schema for structured output

        Returns:
            Configured LLM instance
        """
        pass