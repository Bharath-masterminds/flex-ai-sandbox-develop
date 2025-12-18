"""
Phoenix Arize setup module for LangChain tracing and observability.

This module provides a centralized way to configure Phoenix tracing for the entire application.
"""

import os
from phoenix.otel import register
from dotenv import load_dotenv


def setup_phoenix_tracing(project_name: str = "flex-ai-sandbox") -> None:
    """
    Setup Phoenix tracing for LangChain observability.
    
    Args:
        project_name: Name of the project for Phoenix dashboard
    """
    # Load environment variables
    load_dotenv()
    
    # Check if Phoenix endpoint is configured
    phoenix_endpoint = os.getenv('PHOENIX_COLLECTOR_ENDPOINT')
    if not phoenix_endpoint:
        print("⚠️  PHOENIX_COLLECTOR_ENDPOINT not set. Phoenix tracing disabled.")
        return None
    
    print(f"🔍 Setting up Phoenix tracing for project: {project_name}")
    print(f"📡 Phoenix endpoint: {phoenix_endpoint}")
    
    # Configure Phoenix tracer
    tracer_provider = register(
        project_name=project_name,
        auto_instrument=True  # Auto-instrument based on installed dependencies
    )
    
    print("✅ Phoenix tracing configured successfully!")
    return tracer_provider


if __name__ == "__main__":
    # Test Phoenix setup
    setup_phoenix_tracing("test-project")
