"""Constants for vectorizers module.

This module contains all constants related to vector store operations,
chunking, merging, and batch processing.
"""

# Chunk processing constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_INTERMEDIATE_PERSIST_LENGTH = 2000
PIECE_MEAL_INTERMEDIATE_CHUNK_LENGTH = 100

# Vector store merging constants
DEFAULT_SIMILARITY_SEARCH_K = 1000

# Retry and timeout constants
DEFAULT_HTTP_TIMEOUT = 60

# File processing constants
DEFAULT_ENCODING = "utf-8"