"""Constants for authenticators module.

This module contains all constants related to authentication operations,
HCP token management, and JWT token handling.
"""

# Token expiry and caching constants
TOKEN_EXPIRY_BUFFER_SECONDS = 300

# HTTP timeout constants
DEFAULT_AUTH_TIMEOUT = 60

# JWT token constants
JWT_VERIFY_SIGNATURE = False

# Environment variable names for authentication
ENV_HCP_CLIENT_ID = "HCP_CLIENT_ID"
ENV_HCP_CLIENT_SECRET = "HCP_CLIENT_SECRET"
ENV_HCP_TOKEN_URL = "HCP_TOKEN_URL"
ENV_HCP_TOKEN_SCOPE = "HCP_TOKEN_SCOPE"
ENV_HCP_GRANT_TYPE = "HCP_GRANT_TYPE"

# Default grant type
DEFAULT_CLIENT_CREDENTIALS_GRANT_TYPE = "client_credentials"