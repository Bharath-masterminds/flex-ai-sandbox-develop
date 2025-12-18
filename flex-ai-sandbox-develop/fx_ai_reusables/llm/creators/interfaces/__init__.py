"""
LLM creator interfaces.

Defines interfaces for LLM and embedding creator implementations.
"""

from .llm_creator_interface import ILlmCreator
from .llm_embedding_creator_interface import ILlmEmbeddingCreator

__all__ = [
    "ILlmCreator",
    "ILlmEmbeddingCreator"
]